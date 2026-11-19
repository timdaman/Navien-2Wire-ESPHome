#include "navien.h"
#include "esphome/core/log.h"

namespace esphome {
namespace navien_2wire_b {

static const char *const TAG = "navien_2wire_b";
static const uint32_t SETTINGS_HASH = 0x4E415631;  // "NAV1"
static const uint32_t LINK_TIMEOUT_MS = 5000;
static const uint32_t STATS_INTERVAL_MS = 60000;
// The original remote's poll order.
static const uint8_t POLL_ORDER[6] = {REG_OUTLET, REG_SETPOINT, REG_D3, REG_INLET, REG_MODE, REG_STATUS};

void NavienComponent::setup() {
  this->pref_ = global_preferences->make_preference<Settings>(SETTINGS_HASH);
  Settings loaded;
  if (this->pref_.load(&loaded)) {
    this->settings_ = loaded;
    this->settings_.setpoint = valid_setpoint(this->settings_.setpoint);  // in case the flash holds an old/odd value
    if (this->settings_.mode > MODE_MASTER)
      this->settings_.mode = MODE_LISTEN;
  }
  this->publish_controls_();
}

void NavienComponent::publish_controls_() {
  if (this->mode_select_ != nullptr)
    this->mode_select_->publish_state((size_t) this->settings_.mode);
  if (this->setpoint_number_ != nullptr)
    this->setpoint_number_->publish_state(this->settings_.setpoint);
  if (this->power_switch_ != nullptr)
    this->power_switch_->publish_state(this->settings_.power);
  if (this->preheat_switch_ != nullptr)
    this->preheat_switch_->publish_state(this->settings_.preheat);
}

void NavienComponent::save_() { this->pref_.save(&this->settings_); }

void NavienComponent::set_mode(BusMode mode) {
  ESP_LOGI(TAG, "Bus mode -> %s", mode == MODE_MASTER ? "Master" : "Listen");
  this->settings_.mode = mode;
  this->save_();
  if (this->mode_select_ != nullptr)
    this->mode_select_->publish_state((size_t) mode);
}

void NavienComponent::set_setpoint(uint8_t deg_f) {
  deg_f = valid_setpoint(deg_f);  // e.g. 123 from HA becomes 125 (see navien_codec.h)
  this->settings_.setpoint = deg_f;
  this->save_();
  if (this->setpoint_number_ != nullptr)
    this->setpoint_number_->publish_state(deg_f);
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

void NavienComponent::loop() {
  const uint32_t now = millis();

  if (this->settings_.mode == MODE_MASTER && now - this->last_tx_ms_ >= this->poll_interval_) {
    this->last_tx_ms_ = now;
    this->send_next_();
  }

  const bool link = this->last_heater_ms_ != 0 && now - this->last_heater_ms_ < LINK_TIMEOUT_MS;
  if (link != this->link_up_) {
    this->link_up_ = link;
    if (link)
      ESP_LOGI(TAG, "Heater link up");
    else
      ESP_LOGW(TAG, "Heater link lost (no reply for %u s)", (unsigned) (LINK_TIMEOUT_MS / 1000));
  }
  if (this->heater_link_ != nullptr)
    this->heater_link_->publish_state(link);

  if (now - this->last_stats_ms_ >= STATS_INTERVAL_MS) {
    this->last_stats_ms_ = now;
    publish_if_changed_(this->frames_ok_sensor_, this->frames_ok_);
    publish_if_changed_(this->frames_bad_sensor_, this->frames_bad_);
  }
}

void NavienComponent::send_next_() {
  const uint8_t reg = POLL_ORDER[this->step_];
  this->step_ = (this->step_ + 1) % 6;

  Frame f;
  if (reg == REG_SETPOINT) {
    f = make_master(0x10, REG_SETPOINT, 0xAA, this->settings_.setpoint);
  } else if (reg == REG_MODE) {
    // Bit 6 is always set by the original remote; bit 7 = power, bit 5 = preheat now.
    uint8_t flags = 0x40 | (this->settings_.power ? 0x80 : 0) | (this->settings_.preheat ? 0x20 : 0);
    f = make_master(0x10, REG_MODE, flags, 0x00);
  } else {
    f = make_master(0x00, reg, 0x00, 0x00);
  }

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
  this->publish_master_write_(f);
}

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
    return false;
  }
  this->frames_ok_++;
  this->handle_frame_(f);
  return true;
}

void NavienComponent::handle_frame_(const Frame &f) {
  ESP_LOGV(TAG, "%s %s", f.is_slave() ? "HTR" : "RMT", f.hex().c_str());
  const uint8_t lo = f.b[3];

  if (f.is_slave()) {
    this->last_heater_ms_ = millis();
    switch (f.reg()) {
      case REG_OUTLET:
        publish_if_changed_(this->outlet_temperature_, lo);
        break;
      case REG_INLET:
        publish_if_changed_(this->inlet_temperature_, lo);
        break;
      case REG_STATUS:
        publish_if_changed_(this->status_raw_, f.data());
        if (this->burner_ != nullptr)
          this->burner_->publish_state(lo & 0x08);
        if (this->pump_ != nullptr)
          this->pump_->publish_state(lo & 0x80);
        if (this->demand_ != nullptr)
          this->demand_->publish_state(lo & 0x20);
        break;
      case REG_D3:
        publish_if_changed_(this->register_d3_, f.data());
        break;
      default:
        break;
    }
    return;
  }

  // A master write from the real remote (Listen mode).
  this->publish_master_write_(f);
}

// Updates the "on bus" entities from a master write frame: one the real remote sent (Listen mode),
// or one this board just sent (Master mode, where the board doesn't hear its own transmissions).
void NavienComponent::publish_master_write_(const Frame &f) {
  if (!f.is_write())
    return;
  const uint8_t lo = f.b[3];
  if (f.reg() == REG_SETPOINT)
    publish_if_changed_(this->setpoint_on_bus_, lo);
  if (f.reg() == REG_MODE) {
    if (this->power_on_bus_ != nullptr)
      this->power_on_bus_->publish_state(f.b[2] & 0x80);
    if (this->preheat_on_bus_ != nullptr)
      this->preheat_on_bus_->publish_state(f.b[2] & 0x20);
  }
}

void NavienComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "Navien remote bus:");
  ESP_LOGCONFIG(TAG, "  Mode: %s", this->settings_.mode == MODE_MASTER ? "Master" : "Listen");
  ESP_LOGCONFIG(TAG, "  Poll interval: %u ms", (unsigned) this->poll_interval_);
  ESP_LOGCONFIG(TAG, "  Setpoint: %u °F, power %s, preheat %s", this->settings_.setpoint,
                ONOFF(this->settings_.power), ONOFF(this->settings_.preheat));
}

}  // namespace navien_2wire_b
}  // namespace esphome
