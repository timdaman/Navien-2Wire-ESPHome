#include "navien.h"
#include "esphome/core/log.h"

namespace esphome {
namespace navien_2wire {

// Log tag: messages show as [navien_2wire] and can be filtered with the logger's `logs:` option.
static const char *const TAG = "navien_2wire";
// Identifies settings_ in flash. Change it whenever the Settings struct changes, so old data
// in a different layout is ignored instead of being read wrongly.
static const uint32_t SETTINGS_HASH = 0x4E415632;  // "NAV2"
// The heater link counts as lost after this long without a good heater reply.
// One poll cycle is 6 frames x 400 ms = 2.4 s, so this allows for one missed cycle.
static const uint32_t LINK_TIMEOUT_MS = 5000;
// How often the frames_ok / frames_bad counters are sent to HA.
static const uint32_t STATS_INTERVAL_MS = 60000;
// The original remote's poll order. send_next_() steps through it, one register per frame.
static const uint8_t POLL_ORDER[6] = {REG_OUTLET, REG_SETPOINT, REG_D3, REG_INLET, REG_MODE, REG_STATUS};

// ---- Start-up and settings ------------------------------------------------------------

void NavienComponent::setup() {
  // Open (or create) the flash slot for settings_. If something valid is stored there, use it;
  // otherwise keep the defaults from navien.h.
  this->pref_ = global_preferences->make_preference<Settings>(SETTINGS_HASH);
  Settings loaded;
  if (this->pref_.load(&loaded))
    this->settings_ = loaded;
  this->settings_.setpoint = valid_setpoint(this->settings_.setpoint);  // in case the flash holds an old/odd value
  this->publish_controls_();
}

void NavienComponent::publish_controls_() {
  // Make HA show the stored values. publish_state() only reports a value: it doesn't call
  // write_state()/control() again, so this can't loop back into set_power() etc.
  if (this->setpoint_number_ != nullptr)
    this->setpoint_number_->publish_state(this->settings_.setpoint);
  if (this->power_switch_ != nullptr)
    this->power_switch_->publish_state(this->settings_.power);
  if (this->preheat_switch_ != nullptr)
    this->preheat_switch_->publish_state(this->settings_.preheat);
}

// ESPHome batches flash writes and only writes when the data actually changed, so saving on
// every change from HA doesn't wear the flash.
void NavienComponent::save_() { this->pref_.save(&this->settings_); }

void NavienComponent::set_setpoint(uint8_t deg_f) {
  deg_f = valid_setpoint(deg_f);  // e.g. 123 from HA becomes 125 (see navien_codec.h)
  this->settings_.setpoint = deg_f;
  this->save_();
  if (this->setpoint_number_ != nullptr)
    this->setpoint_number_->publish_state(deg_f);  // confirm the new value to HA
}

void NavienComponent::set_power(bool on) {
  this->settings_.power = on;
  this->save_();
  if (this->power_switch_ != nullptr)
    this->power_switch_->publish_state(on);
}

void NavienComponent::set_preheat(bool on) {
  this->settings_.preheat = on;
  this->save_();
  if (this->preheat_switch_ != nullptr)
    this->preheat_switch_->publish_state(on);
}

// ---- Main loop -----------------------------------------------------------------------------

void NavienComponent::loop() {
  // All the timing below uses `now - last >= interval`. With unsigned numbers that stays
  // correct when millis() wraps around to 0 (after about 49 days).
  const uint32_t now = millis();

  // 1. Send the next poll when it's due. The heater only ever talks when asked, so these
  //    polls are also what makes it send its readings.
  if (now - this->last_tx_ms_ >= this->poll_interval_) {
    this->last_tx_ms_ = now;
    this->send_next_();
  }

  // 2. Heater link: up while a good heater reply arrived in the last LINK_TIMEOUT_MS.
  //    last_heater_ms_ is set in handle_frame_(). Log only when the state changes.
  const bool link = this->last_heater_ms_ != 0 && now - this->last_heater_ms_ < LINK_TIMEOUT_MS;
  if (link != this->link_up_) {
    this->link_up_ = link;
    if (link)
      ESP_LOGI(TAG, "Heater link up");
    else
      ESP_LOGW(TAG, "Heater link lost (no reply for %u s)", (unsigned) (LINK_TIMEOUT_MS / 1000));
  }
  // Called on every loop, but a binary sensor only sends a new state to HA when it changes.
  if (this->heater_link_ != nullptr)
    this->heater_link_->publish_state(link);

  // 3. Frame counters, once a minute (they change on every frame, which would be too chatty).
  if (now - this->last_stats_ms_ >= STATS_INTERVAL_MS) {
    this->last_stats_ms_ = now;
    publish_if_changed_(this->frames_ok_sensor_, this->frames_ok_);
    publish_if_changed_(this->frames_bad_sensor_, this->frames_bad_);
  }
}

// ---- Sending -------------------------------------------------------------------------------

void NavienComponent::send_next_() {
  // Which register this frame is about, then move on to the next one for next time.
  const uint8_t reg = POLL_ORDER[this->step_];
  this->step_ = (this->step_ + 1) % 6;

  // Build the frame exactly as the original remote does (see docs/protocol.md).
  Frame f;
  if (reg == REG_SETPOINT) {
    // Write the setpoint: "10 38 AA <°F>".
    f = make_master(0x10, REG_SETPOINT, 0xAA, this->settings_.setpoint);
  } else if (reg == REG_MODE) {
    // Write power/preheat: "10 C8 <flags> 00".
    // Bit 6 is always set by the original remote; bit 7 = power, bit 5 = preheat now.
    uint8_t flags = 0x40 | (this->settings_.power ? 0x80 : 0) | (this->settings_.preheat ? 0x20 : 0);
    f = make_master(0x10, REG_MODE, flags, 0x00);
  } else {
    // Read a register: "00 <reg> 00 00". The heater answers with the value.
    f = make_master(0x00, reg, 0x00, 0x00);
  }

  // Hand the frame to remote_transmitter as a list of pulses. carrier 0 = drive the pin
  // directly (no 38 kHz IR-style modulation); mark = TX pin high, space = TX pin low.
  // perform() plays the whole 34 ms frame out on the TX pin.
  auto call = this->transmitter_->transmit();
  auto *data = call.get_data();
  data->set_carrier_frequency(0);
  for (int32_t d : encode(f)) {
    if (d > 0)
      data->mark(d);
    else
      data->space(-d);
  }
  call.perform();
  ESP_LOGV(TAG, "TX %s", f.hex().c_str());
}

// ---- Receiving -----------------------------------------------------------------------------

// remote_receiver records the RX pin's edges and, after 4 ms without an edge, calls this with
// the burst it collected. Each burst should be one heater reply, about 60-170 ms after the
// board's frame. The board's own frames aren't seen here: the interface board doesn't echo them.
bool NavienComponent::on_receive(remote_base::RemoteReceiveData data) {
  Frame f;
  DecodeResult r = decode(data.get_raw_data(), f);
  if (r != OK) {
    this->frames_bad_++;
    const auto &raw = data.get_raw_data();
    ESP_LOGD(TAG, "Decode failed: %s (%u timings)", result_str(r), (unsigned) raw.size());
    // The edge durations, for diagnosing timing problems (+ = high, - = low, in us).
    char buf[448];  // fits the logger's default 512-byte line
    size_t pos = 0;
    for (size_t i = 0; i < raw.size() && pos < sizeof(buf) - 16; i++)
      pos += snprintf(buf + pos, sizeof(buf) - pos, "%d ", (int) raw[i]);
    buf[pos] = '\0';
    ESP_LOGD(TAG, "  %s", buf);
    return false;  // false tells remote_receiver this burst wasn't a frame we could use
  }
  this->frames_ok_++;
  this->handle_frame_(f);
  return true;
}

// Turns a heater reply into sensor values. The register in byte 1 says what the reply is;
// the value is in byte 3 (`lo`) for the temperatures and the status bits.
// In the examples below, byte 0 reads 40, or C0 when the frame's parity bit is set.
void NavienComponent::handle_frame_(const Frame &f) {
  ESP_LOGV(TAG, "%s %s", f.is_slave() ? "HTR" : "RMT", f.hex().c_str());
  // Only the heater's replies matter: the board doesn't hear its own frames.
  if (!f.is_slave())
    return;
  this->last_heater_ms_ = millis();  // keeps the heater link up (see loop())
  const uint8_t lo = f.b[3];
  switch (f.reg()) {
    case REG_OUTLET:  // "40 1A AA <°F>"
      publish_if_changed_(this->outlet_temperature_, lo);
      break;
    case REG_INLET:  // "40 96 AA <°F>"
      publish_if_changed_(this->inlet_temperature_, lo);
      break;
    case REG_STATUS:  // "40 00 00 <bits>": 0x80 pump, 0x20 hot water demand, 0x08 burner
      publish_if_changed_(this->status_raw_, f.data());
      if (this->burner_ != nullptr)
        this->burner_->publish_state(lo & 0x08);
      if (this->pump_ != nullptr)
        this->pump_->publish_state(lo & 0x80);
      if (this->demand_ != nullptr)
        this->demand_->publish_state(lo & 0x20);
      break;
    case REG_D3:  // "C0 D3 00 92" so far; meaning unknown, published raw for investigation
      publish_if_changed_(this->register_d3_, f.data());
      break;
    default:
      // The heater also answers the setpoint and power/preheat writes ("D0 38 00 00",
      // "D0 C8 00 00"); those replies carry nothing new, so they're ignored.
      break;
  }
}

void NavienComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "Navien 2-wire remote bus:");
  ESP_LOGCONFIG(TAG, "  Poll interval: %u ms", (unsigned) this->poll_interval_);
  ESP_LOGCONFIG(TAG, "  Setpoint: %u °F, power %s, preheat %s", this->settings_.setpoint,
                ONOFF(this->settings_.power), ONOFF(this->settings_.preheat));
}

}  // namespace navien_2wire
}  // namespace esphome
