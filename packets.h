#pragma once
#include <stdint.h>

// Packet layout shared with gateway/packets.py. All little-endian, packed.
#define PROTO_VERSION 1

enum : uint8_t { PKT_DATA = 1, PKT_PPS = 2, PKT_PROBE = 3, PKT_ECHO = 4 };
enum : uint8_t { CH_NONE = 0, CH_LIGHT = 1, CH_IMU = 2, CH_MIC = 3, CH_PIEZO = 4 };

struct __attribute__((packed)) PktHeader {   // 8 bytes  ("<BBBBI")
  uint8_t  type;
  uint8_t  version;
  uint8_t  node_id;
  uint8_t  channel; // sensor channel for DATA packets, 0 otherwise
  uint32_t seq; // per packet type, lets the Pi count lost packets
};

struct __attribute__((packed)) Sample { // 10 bytes  ("<QH")
  uint64_t t_us; // esp_timer_get_time() when the sample was taken
  uint16_t value; // raw 12-bit ADC reading
};

struct __attribute__((packed)) DataPkt {// header "<BBBBIHI" + n samples
  PktHeader h;
  uint16_t  n; // samples in this packet
  uint32_t  dropped; // cumulative samples lost on the node (queue full)
  Sample    s[BATCH_SAMPLES];
};

struct __attribute__((packed)) PpsPkt { // "<BBBBIQ"
  PktHeader h;
  uint64_t  t_us; // node time of the PPS rising edge
};

struct __attribute__((packed)) ProbePkt { // "<BBBBIQ"  (Pi -> node)
  PktHeader h;
  uint64_t  t_pi_tx_ns; // Pi send time, echoed back untouched
};

struct __attribute__((packed)) EchoPkt { // "<BBBBIQQQ"  (node -> Pi)
  PktHeader h;
  uint64_t  t_pi_tx_ns;
  uint64_t  t_esp_rx_us; // node time when the probe arrived
  uint64_t  t_esp_tx_us; // node time just before the echo was sent
};
