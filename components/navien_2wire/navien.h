#pragma once

#include "esphome/core/component.h"
#include "esphome/core/helpers.h"
#include "esphome/core/preferences.h"
#include "esphome/components/remote_base/remote_base.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/switch/switch.h"
#include "esphome/components/number/number.h"

#include "navien_codec.h"

// navien_2wire: replaces the 2-wire wall remote of a Navien NR-series heater. The board is the
// bus master: it polls the heater like the original remote and writes setpoint, power and preheat.
//
// Data flow:
//   heater -> RX pin -> remote_receiver -> on_receive() -> decode() -> handle_frame_() -> sensors
//   HA switch/number -> write_state()/control() -> set_power()/... -> settings_ (saved in flash)
//   loop() -> send_next_() -> encode(settings_) -> remote_transmitter -> TX pin -> heater

namespace esphome {
namespace navien_2wire {

using namespace navien_codec;

// Registers on the remote bus (see docs/protocol.md). Byte 1 of every frame is one of these.
static const uint8_t REG_STATUS = 0x00;    // heater -> board: operating status bits (burner, pump, demand)
static const uint8_t REG_OUTLET = 0x1A;    // heater -> board: outlet (hot water) temperature, °F
static const uint8_t REG_SETPOINT = 0x38;  // board -> heater: setpoint, °F
static const uint8_t REG_INLET = 0x96;     // heater -> board: inlet (cold water) temperature, °F
static const uint8_t REG_MODE = 0xC8;      // board -> heater: power and preheat flags
static const uint8_t REG_D3 = 0xD3;        // heater -> board: unknown, always 00 92 so far

// The main component. ESPHome creates exactly one (MULTI_CONF = False in __init__.py).
//
// It inherits from three ESPHome classes:
//   Component              gives it setup() / loop() / dump_config(), called by ESPHome.
//   RemoteReceiverListener remote_receiver calls on_receive() with each burst of pulses it records.
//                          (The YAML's `receiver_id:` picks which receiver; see register_listener
//                          in __init__.py.)
//   RemoteTransmittable    provides `transmitter_`, a pointer to the remote_transmitter named by
//                          the YAML's `transmitter_id:`, used in send_next_().
class NavienComponent : public Component,
                        public remote_base::RemoteReceiverListener,
                        public remote_base::RemoteTransmittable {
 public:
  // Loads the saved setpoint/power/preheat from flash and shows them on the entities.
  void setup() override;
  // Sends the next poll when it's due, and keeps the heater_link sensor and frame counters up to date.
  void loop() override;
  // Prints the configuration to the log (shown when you open the device's log).
  void dump_config() override;
  // DATA = set up after the hardware components (remote_receiver/transmitter) it depends on.
  float get_setup_priority() const override { return setup_priority::DATA; }
  // Called by remote_receiver for every burst of pulses on the RX pin. Returns true if it was a frame.
  bool on_receive(remote_base::RemoteReceiveData data) override;

  // From the YAML's `poll_interval:` (default 400 ms): time between two frames the board sends.
  void set_poll_interval(uint32_t ms) { this->poll_interval_ = ms; }

  // Called by the entities below when the user changes them in Home Assistant.
  // Each one stores the new value in settings_, saves it to flash, and reports it back to HA.
  // The value reaches the heater the next time send_next_() sends that register (within ~2.4 s).
  void set_setpoint(uint8_t deg_f);
  void set_power(bool on);
  void set_preheat(bool on);

  // Entity setters (all optional). The generated code calls these once at boot to hand over
  // the entity objects created from the YAML; an entity missing from the YAML stays nullptr,
  // which is why every use below checks for nullptr first.
  void set_outlet_temperature_sensor(sensor::Sensor *s) { outlet_temperature_ = s; }
  void set_inlet_temperature_sensor(sensor::Sensor *s) { inlet_temperature_ = s; }
  void set_status_raw_sensor(sensor::Sensor *s) { status_raw_ = s; }
  void set_register_d3_sensor(sensor::Sensor *s) { register_d3_ = s; }
  void set_frames_ok_sensor(sensor::Sensor *s) { frames_ok_sensor_ = s; }
  void set_frames_bad_sensor(sensor::Sensor *s) { frames_bad_sensor_ = s; }

  void set_burner_binary_sensor(binary_sensor::BinarySensor *s) { burner_ = s; }
  void set_pump_binary_sensor(binary_sensor::BinarySensor *s) { pump_ = s; }
  void set_demand_binary_sensor(binary_sensor::BinarySensor *s) { demand_ = s; }
  void set_heater_link_binary_sensor(binary_sensor::BinarySensor *s) { heater_link_ = s; }

  void set_power_switch(switch_::Switch *s) { power_switch_ = s; }
  void set_preheat_switch(switch_::Switch *s) { preheat_switch_ = s; }
  void set_setpoint_number(number::Number *n) { setpoint_number_ = n; }

 protected:
  // What the board tells the heater. Saved to flash as one block, so it survives a reboot.
  // `packed` = no padding bytes, so the stored size is exactly 3 bytes.
  struct Settings {
    uint8_t setpoint;  // °F, sent in register 0x38
    uint8_t power;     // 1 = heater on, sent as bit 7 of register 0xC8
    uint8_t preheat;   // 1 = run recirculation now, sent as bit 5 of register 0xC8
  } __attribute__((packed));

  // Builds and transmits the next frame of the poll cycle.
  void send_next_();
  // Uses one successfully decoded frame: updates the sensors from a heater reply.
  void handle_frame_(const Frame &f);
  // Writes settings_ to flash.
  void save_();
  // Shows settings_ on the setpoint number and the power/preheat switches.
  void publish_controls_();
  // Publishes a sensor value only when it changed (or the sensor has no value yet), so HA isn't
  // sent the same temperature every 2.4 s. Does nothing for a sensor that isn't in the YAML.
  template<typename T> static void publish_if_changed_(sensor::Sensor *s, T v) {
    if (s != nullptr && (std::isnan(s->state) || s->state != (float) v))
      s->publish_state(v);
  }

  uint32_t poll_interval_{400};  // ms between two frames the board sends
  uint32_t last_tx_ms_{0};       // millis() when the last frame was sent
  uint32_t last_heater_ms_{0};   // millis() when the last good heater reply arrived (0 = never)
  uint32_t last_stats_ms_{0};    // millis() when frames_ok/frames_bad were last published
  uint8_t step_{0};              // position in POLL_ORDER (navien.cpp) of the next frame to send, 0-5
  uint32_t frames_ok_{0};        // frames decoded since boot
  uint32_t frames_bad_{0};       // bursts that failed to decode since boot
  bool link_up_{false};          // last heater-link state, so a change is logged only once

  Settings settings_{120, 1, 0};  // defaults before anything is saved: 120 °F, power on, preheat off
  ESPPreferenceObject pref_;      // handle to settings_' slot in flash, opened in setup()

  // Entities, set by the setters above (nullptr when not in the YAML).
  sensor::Sensor *outlet_temperature_{nullptr};  // from register 0x1A
  sensor::Sensor *inlet_temperature_{nullptr};   // from register 0x96
  sensor::Sensor *status_raw_{nullptr};          // register 0x00, both data bytes as one number
  sensor::Sensor *register_d3_{nullptr};         // register 0xD3, both data bytes as one number
  sensor::Sensor *frames_ok_sensor_{nullptr};    // frames_ok_, published once a minute
  sensor::Sensor *frames_bad_sensor_{nullptr};   // frames_bad_, published once a minute

  binary_sensor::BinarySensor *burner_{nullptr};       // register 0x00, bit 3 (0x08)
  binary_sensor::BinarySensor *pump_{nullptr};         // register 0x00, bit 7 (0x80)
  binary_sensor::BinarySensor *demand_{nullptr};       // register 0x00, bit 5 (0x20)
  binary_sensor::BinarySensor *heater_link_{nullptr};  // on while the heater has replied in the last 5 s

  switch_::Switch *power_switch_{nullptr};
  switch_::Switch *preheat_switch_{nullptr};
  number::Number *setpoint_number_{nullptr};
};

// ---- Control entities ----------------------------------------------------
//
// These are the HA controls. Each is an ESPHome entity class with one method overridden:
// ESPHome calls write_state() (switch) or control() (number) when HA asks for a new value.
// They don't store anything themselves; they pass the value to the component.
// Parented<NavienComponent> provides `parent_`, set by cg.register_parented() in the Python files.

class NavienPowerSwitch : public switch_::Switch, public Parented<NavienComponent> {
 protected:
  void write_state(bool state) override { this->parent_->set_power(state); }
};

class NavienPreheatSwitch : public switch_::Switch, public Parented<NavienComponent> {
 protected:
  void write_state(bool state) override { this->parent_->set_preheat(state); }
};

class NavienSetpointNumber : public number::Number, public Parented<NavienComponent> {
 protected:
  // HA sends a float; the bus carries whole °F, so round it.
  void control(float value) override { this->parent_->set_setpoint((uint8_t) lroundf(value)); }
};

}  // namespace navien_2wire
}  // namespace esphome
