"""Shared settings for the Pi side. Keep in sync with firmware/include/config.h."""

DATA_PORT = 5005 # nodes -> Pi
PROBE_PORT = 5006 # Pi -> node delay probes
SAMPLE_RATE_HZ = 1000
BATCH_SAMPLES = 50

# Pi GPIO (BCM numbering)
PIN_PPS = 18 # hardware PWM0, set up by dtoverlay=pwm 
PIN_LED = 23
PIN_BUZZER = 24
PIN_SOLENOID = 25
