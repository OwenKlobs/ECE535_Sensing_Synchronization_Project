// Stage 1 sensing node: TEMT6000 light sensor -> timestamped samples -> Pi over Wi-Fi UDP.
//
// What runs where:
//   sampler (esp_timer, 1 kHz)  : timestamp + analogRead -> sampleQ
//   PPS ISR (GPIO4 rising edge)  : timestamp -> ppsQ
//   AsyncUDP callback            : answers delay probes immediately
//   loop()                       : drains queues, sends DATA and PPS packets
//
// The node never synchronizes anything. It only stamps data with its own clock,
// exactly like a HAEST sensing device.

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <AsyncUDP.h>
#include <ESPmDNS.h>
#include "esp_timer.h"
#include "config.h"
#include "packets.h"

static QueueHandle_t sampleQ;
static QueueHandle_t ppsQ;
static volatile uint32_t samplesDropped = 0;
static volatile uint32_t samplesTaken = 0;
static volatile uint32_t ppsCount = 0;
static volatile uint16_t lastValue = 0;
static uint32_t sendFailures = 0;

static WiFiUDP   dataUdp;
static AsyncUDP  probeUdp;
static IPAddress gatewayIp;
static uint32_t  dataSeq = 0, ppsSeq = 0;

// Sampling (runs every 1/SAMPLE_RATE_HZ seconds) 
static void sampleCallback(void*) {
  Sample s;
  s.t_us = (uint64_t)esp_timer_get_time(); // timestamp at capture, not at send
  s.value = (uint16_t)analogRead(PIN_LIGHT);
  lastValue = s.value;
  samplesTaken++;
  if (xQueueSend(sampleQ, &s, 0) != pdTRUE) samplesDropped++;
}

// Ground-truth pulse 
static void IRAM_ATTR ppsIsr() {
  uint64_t t = (uint64_t)esp_timer_get_time();
  BaseType_t woke = pdFALSE;
  xQueueSendFromISR(ppsQ, &t, &woke);
  ppsCount++;
  if (woke) portYIELD_FROM_ISR();
}

// Delay probes
// Echos straight from the network callback 
static void onProbe(AsyncUDPPacket packet) {
  uint64_t tRx = (uint64_t)esp_timer_get_time();
  if (packet.length() < sizeof(ProbePkt)) return;
  ProbePkt pr;
  memcpy(&pr, packet.data(), sizeof(pr));
  if (pr.h.type != PKT_PROBE || pr.h.version != PROTO_VERSION) return;

  EchoPkt e;
  e.h = PktHeader{PKT_ECHO, PROTO_VERSION, NODE_ID, CH_NONE, pr.h.seq};
  e.t_pi_tx_ns  = pr.t_pi_tx_ns;
  e.t_esp_rx_us = tRx;
  e.t_esp_tx_us = (uint64_t)esp_timer_get_time();
  packet.write((uint8_t*)&e, sizeof(e)); // reply to the sender
}

//  Networking helpers 
static void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false); // modem sleep adds large, variable delay
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Node %d connecting to %s", NODE_ID, WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print('.');
  }
  WiFi.setSleep(false);
  Serial.printf("\nConnected. Node IP: %s  (use this with probes.py)\n",
                WiFi.localIP().toString().c_str());
}

// Uses GATEWAY_IP if one is set; otherwise look up <GATEWAY_HOST>.local on the network.
static void resolveGateway() {
  if (strlen(GATEWAY_IP) > 0) {
    gatewayIp.fromString(GATEWAY_IP);
  } else {
    char me[16];
    snprintf(me, sizeof(me), "node%d", NODE_ID);
    MDNS.begin(me);
    Serial.printf("Looking up %s.local", GATEWAY_HOST);
    do {
      gatewayIp = MDNS.queryHost(GATEWAY_HOST, 2000);
      Serial.print('.');
    } while (gatewayIp == IPAddress(0, 0, 0, 0));
  }
  Serial.printf("\nGateway (Pi) at %s\n", gatewayIp.toString().c_str());
}

static void sendData(DataPkt& pkt, uint16_t n) {
  pkt.h = PktHeader{PKT_DATA, PROTO_VERSION, NODE_ID, CH_LIGHT, dataSeq++};
  pkt.n = n;
  pkt.dropped = samplesDropped;
  size_t len = sizeof(PktHeader) + sizeof(uint16_t) + sizeof(uint32_t) + n * sizeof(Sample);
  dataUdp.beginPacket(gatewayIp, DATA_PORT);
  dataUdp.write((const uint8_t*)&pkt, len);
  if (!dataUdp.endPacket()) sendFailures++;
}

static void sendPps(uint64_t t) {
  PpsPkt p;
  p.h = PktHeader{PKT_PPS, PROTO_VERSION, NODE_ID, CH_NONE, ppsSeq++};
  p.t_us = t;
  dataUdp.beginPacket(gatewayIp, DATA_PORT);
  dataUdp.write((const uint8_t*)&p, sizeof(p));
  if (!dataUdp.endPacket()) sendFailures++;
}

static void printStats() {
  static uint32_t lastMs = 0, lastTaken = 0;
  uint32_t now = millis();
  if (now - lastMs < 5000) return;
  uint32_t taken = samplesTaken;
  float rate = (taken - lastTaken) * 1000.0f / (now - lastMs);
  Serial.printf("[node %d] %.1f samples/s  light=%u  dropped=%lu  sendFail=%lu  pps=%lu  rssi=%d dBm\n",
                NODE_ID, rate, (unsigned)lastValue, (unsigned long)samplesDropped,
                (unsigned long)sendFailures, (unsigned long)ppsCount, WiFi.RSSI());
  lastMs = now;
  lastTaken = taken;
}

// Setup / loop 
void setup() {
  Serial.begin(115200);
  delay(200);
  pinMode(PIN_PPS, INPUT_PULLDOWN); // stays low if the Pi is not driving it
  analogReadResolution(12); // 0-4095; default attenuation covers ~0-3.1 V

  sampleQ = xQueueCreate(SAMPLE_QUEUE_LEN, sizeof(Sample));
  ppsQ    = xQueueCreate(16, sizeof(uint64_t));

  connectWiFi();
  resolveGateway();
  dataUdp.begin(DATA_PORT);
  if (probeUdp.listen(PROBE_PORT)) probeUdp.onPacket(onProbe);

  attachInterrupt(digitalPinToInterrupt(PIN_PPS), ppsIsr, RISING);

  esp_timer_create_args_t args = {};
  args.callback = &sampleCallback;
  args.name = "sampler";
  esp_timer_handle_t timer;
  ESP_ERROR_CHECK(esp_timer_create(&args, &timer));
  ESP_ERROR_CHECK(esp_timer_start_periodic(timer, 1000000ULL / SAMPLE_RATE_HZ));
  Serial.printf("Sampling GPIO%d at %d Hz\n", PIN_LIGHT, SAMPLE_RATE_HZ);
}

void loop() {
  static DataPkt pkt;
  static uint16_t n = 0;
  Sample s;

  // Block briefly for the next sample instead of spinning.
  if (xQueueReceive(sampleQ, &s, pdMS_TO_TICKS(5)) == pdTRUE) {
    do {
      pkt.s[n++] = s;
      if (n == BATCH_SAMPLES) { sendData(pkt, n); n = 0; }
    } while (xQueueReceive(sampleQ, &s, 0) == pdTRUE);
  }

  uint64_t t;
  while (xQueueReceive(ppsQ, &t, 0) == pdTRUE) sendPps(t);

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi lost, reconnecting");
    connectWiFi();
  }
  printStats();
}
