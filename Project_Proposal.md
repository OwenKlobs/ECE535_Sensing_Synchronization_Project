# Time Synchronization Via Sensing

Gateway-side clock synchronization for two ESP32 devices, computed on a Raspberry Pi, with no extra timing packets sent by the edge devices. 

## Motivation:
Accurate time synchronization across devices is essential for distributed applications. Resource-constrained edge devices already send timestamped sensor data to a gateway, but conventional timing protocols add communication and energy overhead on top of that. Their accuracy is also limited by variable network delay, especially over BLE. 

## Problem Statement:
We propose a gateway-side synchronization protocol for two ESP32 devices that runs on a Raspberry Pi. Both devices sense the same physical events and timestamp their sensor data with their own local clocks. The gateway uses these timestamps to estimate relative clock offset and drift, with no additional timing packets.  

  **1. Network delay characterization:**
     Measure the delay between a between a Raspberry PI and each ESP32 using                 timestamped probe-and-echo packets over WiFi, reporting RTT and jitter.
     
**2. Relative drift estimation:**
     Estimate relative clock drift between two ESP32s from shared sensing events by          fitting the change in their timestamp differences over time, following the HAEST        approach.
     
**3. Validation:**
     Compare the results against a wired Ground Truth Pulse and NTP Baseline.

## Design goals:
 - No synchronization overhead: No extra timing packets on the ESP32s
 - Gateway-side computation: All synchronization computation runs on the Raspberry Pi
 - Comparable to HAEST: Uses the same hardware setup (2 ESP32s) so our data can be compared directly with their findings

## Deliverables:
- Characterization of network delay (RTT,jitter) between a Raspberry PI and each of the two ESP32s
- Estimate of relative clock drift between the ESP32s from shared sensing events
- Working source code and setup instructions.
- Final report comparing our gathered data and results to HAEST’s findings. 

## System blocks:


## Hardware/Software Requirements:

**Hardware**
- 2x ESP32 (same as HAEST, for comparable results)
- Sensors: microphone(s) and IMU(s) for same cross-type pair modality checks
- Raspberry Pi (gateway)
- Wiring for ground-truth pulse (shared GPIO line)

**Software**
- ESP32 firmware:sensor data collection and timestamping
- Bootstrapping and synchronization phases
- Streaming client (ESP32 to Gateway)
- Gateway software on Raspberry Pi: receiver, delay characterization, event matching, offset/drift estimation, logging and analysis

## Team Members and Responsibilities:
- Owen
- Jack
- Quinn

## Project Timeline:
- Week 1: Set up Raspberry Pi and ESP32 nodes; collect sensors; start developing firmware
- Week 2: Test sampling and timestamping capabilities of sensor data
- Week 3: Collect RRT and jitter data over WiFi
- Week 4:...
- Week 5:...
- Week 6:...

## References: 

1. Haest: Harvesting Ambient Events to Synchronize Time Across 
Heterogeneous IoT Devices, https://ieeexplore.ieee.org/document/10568057
