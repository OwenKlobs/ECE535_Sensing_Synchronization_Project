#pragma once
// Shared settings. If you change a value that the Pi also uses
// (ports, sample rate, packet layout), change gateway/config.py in the same commit.

// Wi-Fi: the same 2.4 GHz network the Pi is on
// note: (home router or phone hotspot; the ESP32 cannot use 5 GHz or eduroam)
#define WIFI_SSID "JacksIPhone"
#define WIFI_PASSWORD "Lexington419"
#define GATEWAY_HOST "rp4"
#define GATEWAY_IP ""
#define DATA_PORT 5005 // node -> Pi: sensor data and PPS edges
#define PROBE_PORT 5006 // Pi -> node -> Pi: delay probes

#ifndef NODE_ID
#define NODE_ID 1 // set per node in platformio.ini
#endif

//  Sampling 
#define SAMPLE_RATE_HZ 1000
#define BATCH_SAMPLES 50 // samples per UDP packet (50 ms at 1 kHz)
#define SAMPLE_QUEUE_LEN 2000 // 2 s of buffering if Wi-Fi stalls

//  Pins 
#define PIN_LIGHT 34 // TEMT6000 SIG 
#define PIN_PPS 4 // ground-truth pulse from Pi GPIO18 (through 330 ohm)
