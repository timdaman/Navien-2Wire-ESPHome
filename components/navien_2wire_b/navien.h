#pragma once

#include "esphome/core/component.h"
#include "esphome/core/helpers.h"
#include "esphome/core/preferences.h"
#include "esphome/components/remote_base/remote_base.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/switch/switch.h"
#include "esphome/components/number/number.h"
#include "esphome/components/select/select.h"

#include "navien_codec.h"

// navien_2wire_b: the version of the component for the untested comparator board described in
// hardware/other-ideas.md. Unlike navien_2wire it has a Listen mode (decode only, for sniffing
// alongside the original remote) and reports the master's writes in the *_on_bus entities.

namespace esphome {
namespace navien_2wire_b {

using namespace navien_codec;

// Bus mode. LISTEN only decodes; MASTER replaces the wall remote.
enum BusMode : uint8_t { MODE_LISTEN = 0, MODE_MASTER = 1 };

// Registers on the remote bus (see docs/protocol.md).
static const uint8_t REG_STATUS = 0x00;
static const uint8_t REG_OUTLET = 0x1A;
static const uint8_t REG_SETPOINT = 0x38;
static const uint8_t REG_INLET = 0x96;
static const uint8_t REG_MODE = 0xC8;
static const uint8_t REG_D3 = 0xD3;

class NavienComponent : public Component,
                        public remote_base::RemoteReceiverListener,
                        public remote_base::RemoteTransmittable {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::DATA; }
  bool on_receive(remote_base::RemoteReceiveData data) override;

  void set_poll_interval(uint32_t ms) { this->poll_interval_ = ms; }

  // Called by the entities below.
  void set_mode(BusMode mode);
  void set_setpoint(uint8_t deg_f);
  void set_power(bool on);
  void set_preheat(bool on);

  // Entity setters (all optional).
  void set_outlet_temperature_sensor(sensor::Sensor *s) { outlet_temperature_ = s; }
  void set_inlet_temperature_sensor(sensor::Sensor *s) { inlet_temperature_ = s; }
  void set_setpoint_on_bus_sensor(sensor::Sensor *s) { setpoint_on_bus_ = s; }
  void set_status_raw_sensor(sensor::Sensor *s) { status_raw_ = s; }
  void set_register_d3_sensor(sensor::Sensor *s) { register_d3_ = s; }
  void set_frames_ok_sensor(sensor::Sensor *s) { frames_ok_sensor_ = s; }
  void set_frames_bad_sensor(sensor::Sensor *s) { frames_bad_sensor_ = s; }

  void set_burner_binary_sensor(binary_sensor::BinarySensor *s) { burner_ = s; }
  void set_pump_binary_sensor(binary_sensor::BinarySensor *s) { pump_ = s; }
  void set_demand_binary_sensor(binary_sensor::BinarySensor *s) { demand_ = s; }
  void set_heater_link_binary_sensor(binary_sensor::BinarySensor *s) { heater_link_ = s; }
  void set_power_on_bus_binary_sensor(binary_sensor::BinarySensor *s) { power_on_bus_ = s; }
  void set_preheat_on_bus_binary_sensor(binary_sensor::BinarySensor *s) { preheat_on_bus_ = s; }

  void set_power_switch(switch_::Switch *s) { power_switch_ = s; }
  void set_preheat_switch(switch_::Switch *s) { preheat_switch_ = s; }
  void set_setpoint_number(number::Number *n) { setpoint_number_ = n; }
  void set_mode_select(select::Select *s) { mode_select_ = s; }

 protected:
  struct Settings {
    uint8_t mode;
    uint8_t setpoint;
    uint8_t power;
    uint8_t preheat;
  } __attribute__((packed));

  void send_next_();
  void handle_frame_(const Frame &f);
  void publish_master_write_(const Frame &f);
  void save_();
  void publish_controls_();
  template<typename T> static void publish_if_changed_(sensor::Sensor *s, T v) {
    if (s != nullptr && (std::isnan(s->state) || s->state != (float) v))
      s->publish_state(v);
  }

  uint32_t poll_interval_{400};
  uint32_t last_tx_ms_{0};
  uint32_t last_heater_ms_{0};
  uint32_t last_stats_ms_{0};
  uint8_t step_{0};
  uint32_t frames_ok_{0};
  uint32_t frames_bad_{0};
  bool link_up_{false};

  Settings settings_{MODE_LISTEN, 120, 1, 0};
  ESPPreferenceObject pref_;

  sensor::Sensor *outlet_temperature_{nullptr};
  sensor::Sensor *inlet_temperature_{nullptr};
  sensor::Sensor *setpoint_on_bus_{nullptr};
  sensor::Sensor *status_raw_{nullptr};
  sensor::Sensor *register_d3_{nullptr};
  sensor::Sensor *frames_ok_sensor_{nullptr};
  sensor::Sensor *frames_bad_sensor_{nullptr};

  binary_sensor::BinarySensor *burner_{nullptr};
  binary_sensor::BinarySensor *pump_{nullptr};
  binary_sensor::BinarySensor *demand_{nullptr};
  binary_sensor::BinarySensor *heater_link_{nullptr};
  binary_sensor::BinarySensor *power_on_bus_{nullptr};
  binary_sensor::BinarySensor *preheat_on_bus_{nullptr};

  switch_::Switch *power_switch_{nullptr};
  switch_::Switch *preheat_switch_{nullptr};
  number::Number *setpoint_number_{nullptr};
  select::Select *mode_select_{nullptr};
};

// ---- Control entities ----------------------------------------------------

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
  void control(float value) override { this->parent_->set_setpoint((uint8_t) lroundf(value)); }
};

class NavienModeSelect : public select::Select, public Parented<NavienComponent> {
 protected:
  void control(size_t index) override { this->parent_->set_mode(index == 1 ? MODE_MASTER : MODE_LISTEN); }
};

}  // namespace navien_2wire_b
}  // namespace esphome
