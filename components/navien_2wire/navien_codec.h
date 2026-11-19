// Navien NR-series remote bus codec (heater <-> wall remote, 2-wire).
//
// This file only turns frames into pulse timings and back. It knows nothing about ESPHome,
// sensors or Home Assistant, so it can be unit-tested on a PC (tests/test_codec.cpp).
// navien.cpp uses it in two places:
//   * receiving: remote_receiver hands navien.cpp a list of pulse lengths -> decode() -> Frame
//   * sending:   navien.cpp builds a Frame with make_master() -> encode() -> pulse lengths
//                that remote_transmitter plays out on the TX pin
//
// Physical layer: Manchester, 500 us half-bit (1000 bit/s). A '1' is
// high-then-low, a '0' is low-then-high. "High" = bus pulled up (remote
// releasing its clamp, or heater stepping its current).
// Frame: start bit (1) + 32 data bits (MSB first) + end bit (1) = 34 bits.
// Data: [P|flags] [reg] [d_hi] [d_lo]. P = bit 7 of byte 0, chosen so the
// 32 data bits have even parity. flags: 0x40 = slave (heater) reply,
// 0x10 = master write.
//
// Timings use the ESPHome remote_receiver/remote_transmitter convention:
// positive = mark (bus high), negative = space (bus low), in microseconds.
// Example: {500, -1000, 500} = high 0.5 ms, low 1 ms, high 0.5 ms.
//
// Plain C++17 with no ESPHome dependencies, so it can be unit-tested on a PC.
// An identical copy lives in components/navien_2wire_b/; keep the two the same.
#pragma once
#include <cstdint>
#include <cstdlib>
#include <string>
#include <vector>

namespace esphome {
namespace navien_codec {

// Length of half a bit on the bus. Every edge of a frame falls on a multiple of this.
static const int32_t HALF_BIT_US = 500;
// Bits per frame: start bit + 32 data bits + end bit.
static const int FRAME_BITS = 34;

// One frame as 4 bytes, in the order they appear on the bus:
//   b[0] = parity bit (bit 7) + flags (bits 0-6)
//   b[1] = register number (what the frame is about: 0x1A outlet temperature, etc.)
//   b[2] = data, high byte (often 0xAA, which seems to mean "valid value follows")
//   b[3] = data, low byte (the temperature, setpoint or status bits)
// Example: heater reply "40 96 AA 79" = from heater, register 0x96 (inlet), value 0x79 = 121 °F.
struct Frame {
  uint8_t b[4] = {0, 0, 0, 0};

  // The flag bits of byte 0, without the parity bit.
  uint8_t flags() const { return b[0] & 0x7F; }
  // True for a reply from the heater (the "slave"). False for a frame from the remote (the "master").
  bool is_slave() const { return b[0] & 0x40; }
  // True when the master is writing a value (setpoint, power/preheat) rather than asking for one.
  bool is_write() const { return b[0] & 0x10; }
  // Register number, byte 1.
  uint8_t reg() const { return b[1]; }
  // Bytes 2 and 3 as one 16-bit number (used for the raw diagnostic sensors).
  uint16_t data() const { return (uint16_t(b[2]) << 8) | b[3]; }

  // Even parity: the 32 data bits must contain an even number of 1s. A single flipped bit fails this.
  bool parity_ok() const {
    uint32_t v = (uint32_t(b[0]) << 24) | (uint32_t(b[1]) << 16) | (uint32_t(b[2]) << 8) | b[3];
    return (__builtin_popcount(v) & 1) == 0;
  }
  // Set or clear bit 7 of byte 0 so that parity_ok() is true. Used when building frames to send.
  void set_parity() {
    b[0] &= 0x7F;
    if (!parity_ok()) b[0] |= 0x80;
  }
  // The frame as text, e.g. "40 96 AA 79", for log messages.
  std::string hex() const {
    static const char *h = "0123456789ABCDEF";
    std::string s;
    for (int i = 0; i < 4; i++) {
      if (i) s += ' ';
      s += h[b[i] >> 4];
      s += h[b[i] & 15];
    }
    return s;
  }
};

// Build a master frame (remote -> heater). Parity is filled in.
//   flags: 0x00 = read (ask the heater for a register), 0x10 = write (set a register)
//   reg, d_hi, d_lo: bytes 1-3 as described above. For a read they are reg, 0, 0.
inline Frame make_master(uint8_t flags, uint8_t reg, uint8_t d_hi, uint8_t d_lo) {
  Frame f;
  f.b[0] = flags & 0x7F;
  f.b[1] = reg;
  f.b[2] = d_hi;
  f.b[3] = d_lo;
  f.set_parity();
  return f;
}

// ---- Setpoint values the heater accepts ------------------------------------------------
// Navien's remotes for non-condensing heaters cover 98-140 °F. The original NR-210A remote steps
// 1 °F up to 120 °F and then 5 °F (119 -> 120 -> 125 was seen on the bus), so above 120 only
// 125, 130, 135 and 140 are sent. DIP switches 7/8 on the heater board can cap the maximum
// lower (110/120/130/140 °F); the heater doesn't report its cap, so the board can't see it.
static const uint8_t SETPOINT_MIN_F = 98;
static const uint8_t SETPOINT_MAX_F = 140;
static const uint8_t SETPOINT_FINE_MAX_F = 120;  // 1 °F steps up to here, 5 °F steps above

// Turns any requested temperature into the nearest one the original remote could send:
// clamped to 98-140 °F, and rounded to a multiple of 5 above 120 °F (122 -> 120, 123 -> 125).
inline uint8_t valid_setpoint(int deg_f) {
  if (deg_f < SETPOINT_MIN_F) return SETPOINT_MIN_F;
  if (deg_f > SETPOINT_MAX_F) return SETPOINT_MAX_F;
  if (deg_f > SETPOINT_FINE_MAX_F) deg_f = (deg_f + 2) / 5 * 5;
  return (uint8_t) deg_f;
}

// Why decode() rejected a burst of pulses. Each check runs in this order, and the first one
// that fails is returned:
//   BAD_TIMING      an edge is too far from the 500 us grid, or a pulse is too short/long
//   BAD_LENGTH      the burst isn't exactly 34 bits long (cut off, or two frames merged)
//   BAD_MANCHESTER  some bit has two equal halves (every Manchester bit must change in the middle)
//   BAD_START_END   the first or last bit isn't the required '1'
//   BAD_PARITY      the bits arrived cleanly but one of them is wrong
enum DecodeResult { OK = 0, BAD_TIMING, BAD_LENGTH, BAD_MANCHESTER, BAD_START_END, BAD_PARITY };

// Text for a DecodeResult, for log messages.
inline const char *result_str(DecodeResult r) {
  switch (r) {
    case OK: return "ok";
    case BAD_TIMING: return "bad timing";
    case BAD_LENGTH: return "bad length";
    case BAD_MANCHESTER: return "bad manchester";
    case BAD_START_END: return "bad start/end";
    case BAD_PARITY: return "bad parity";
  }
  return "?";
}

// Decode one burst of raw timings into a frame.
//
// Input: the pulse lengths remote_receiver recorded for one burst of activity on the RX pin
// (+ = high, - = low, in us). remote_receiver ends a burst after 4 ms of no edges (its `idle:`
// setting), so one burst = one frame plus some idle at either end.
// Output: on OK, `out` holds the frame; otherwise `out` is left unchanged.
//
// It works in three stages:
//   1. Timing: turn the pulse lengths into a list of half-bits (`half`, 1 = high, 0 = low).
//   2. Manchester: pair the half-bits into 34 bits (high-low = 1, low-high = 0).
//   3. Bytes: drop the start and end bits, pack the 32 data bits into 4 bytes, check parity.
//
// Each edge is placed on the frame's 500 us half-bit grid by its time since the start of
// the frame, not by the length of the pulse before it. While its burner runs, the heater
// sometimes sends one edge up to ~200 us late (the edges after it are on time again):
// measured pulse by pulse that looks like a 700/300 us pair, but on the grid it is simply
// a late edge. The grid re-anchors on every clean edge, and on any edge that sits at the
// same offset as the one before it (the grid really has moved), so clock differences between
// the two ends (the original remote runs a few % slow) don't build up. A single late edge has
// no such neighbour and doesn't move it. Parity still catches a frame that snapped wrong.
static const int32_t EDGE_TOLERANCE_US = 240;  // an edge may be this far from its grid slot
static const int32_t EDGE_CLEAN_US = 100;      // edges closer than this re-anchor the grid
static const int32_t EDGE_AGREE_US = 60;       // two edges this close in offset re-anchor it too

inline DecodeResult decode(const std::vector<int32_t> &raw, Frame &out) {
  // ---- Stage 1: pulse lengths -> half-bits --------------------------------------------
  std::vector<uint8_t> half;  // one entry per 500 us half-bit, 1 = high
  half.reserve(80);
  size_t i = 0;
  while (i < raw.size() && raw[i] <= 0) i++;  // skip leading idle/space
  int32_t t = 0;       // time of the current edge since the first one, us
  int32_t anchor = 0;  // offset of the grid, set by the last clean edge
  int slot = 0;        // grid slot of the previous edge
  int32_t prev_err = 0;  // offset of the previous edge from the grid (0 if it re-anchored)
  for (; i < raw.size(); i++) {
    int32_t d = raw[i];      // this pulse: + = high, - = low
    int32_t a = std::abs(d); // its length in us
    if (a >= 3 * HALF_BIT_US) {  // 1500 us or more: longer than any pulse with both edges late/early
      if (d < 0) break;     // long low = trailing idle: frame is over
      return BAD_TIMING;    // a high never lasts more than one bit
    }
    t += a;                                         // time of the edge that ends this pulse
    int32_t rel = t - anchor;                       // ... measured against the grid
    int n = (rel + HALF_BIT_US / 2) / HALF_BIT_US;  // nearest grid slot (rounded)
    int32_t err = rel - n * HALF_BIT_US;            // how far the edge is from that slot
    if (std::abs(err) > EDGE_TOLERANCE_US) return BAD_TIMING;
    int count = n - slot;  // half-bits this pulse covers: 1 (500 us) or 2 (1000 us)
    if (count < 1 || count > 2) return BAD_TIMING;
    if (std::abs(err) < EDGE_CLEAN_US || std::abs(err - prev_err) < EDGE_AGREE_US) {
      anchor += err;  // a trustworthy edge: move the grid onto it
      prev_err = 0;
    } else {
      prev_err = err;  // an odd edge: remember it, but leave the grid where it is
    }
    slot = n;
    for (int k = 0; k < count; k++) half.push_back(d > 0 ? 1 : 0);
  }
  // A frame ends with the end bit '1' = high then low. That last low runs straight into the
  // idle gap, so it never shows up as its own pulse: add it back.
  if (half.size() % 2) half.push_back(0);  // final low half of the end bit
  if (half.size() != FRAME_BITS * 2) return BAD_LENGTH;

  // ---- Stage 2: half-bits -> bits -------------------------------------------------------
  uint8_t bits[FRAME_BITS];
  for (int k = 0; k < FRAME_BITS; k++) {
    uint8_t h0 = half[2 * k], h1 = half[2 * k + 1];
    if (h0 == h1) return BAD_MANCHESTER;
    bits[k] = h0;  // high-then-low = 1
  }
  if (bits[0] != 1 || bits[FRAME_BITS - 1] != 1) return BAD_START_END;

  // ---- Stage 3: bits -> bytes -------------------------------------------------------------
  // bits[1] .. bits[32] are the data, most significant bit of byte 0 first.
  Frame f;
  for (int k = 0; k < 32; k++)
    if (bits[1 + k]) f.b[k / 8] |= 0x80 >> (k % 8);
  if (!f.parity_ok()) return BAD_PARITY;
  out = f;
  return OK;
}

// Encode a frame into raw timings for remote_transmitter.transmit_raw.
//
// The reverse of decode(): bytes -> 34 bits -> 68 half-bits -> pulse lengths. Neighbouring
// half-bits at the same level merge into one 1000 us pulse, so a frame is at most 68 pulses long.
// The list starts with a high (the start bit's first half) and ends with a high (the end
// bit's first half); the end bit's low half is left out because the line idles low anyway.
inline std::vector<int32_t> encode(const Frame &f) {
  uint8_t bits[FRAME_BITS];
  bits[0] = 1;  // start bit
  for (int k = 0; k < 32; k++) bits[1 + k] = (f.b[k / 8] >> (7 - k % 8)) & 1;
  bits[FRAME_BITS - 1] = 1;  // end bit

  std::vector<int32_t> out;
  out.reserve(70);
  int level = -1;    // level of the pulse being built (1 = high, 0 = low, -1 = none yet)
  int32_t run = 0;   // its length so far, us
  for (int k = 0; k < FRAME_BITS; k++) {
    uint8_t halves[2] = {bits[k], uint8_t(!bits[k])};  // '1' = high, low; '0' = low, high
    for (uint8_t h : halves) {
      if (h == level) {
        run += HALF_BIT_US;  // same level as before: the pulse just gets longer
      } else {
        if (level >= 0) out.push_back(level ? run : -run);  // level changed: emit the pulse
        level = h;
        run = HALF_BIT_US;
      }
    }
  }
  if (level == 1) out.push_back(run);  // the trailing low is just idle: omit it
  return out;
}

}  // namespace navien_codec
}  // namespace esphome
