#!/usr/bin/env python3

import pigpio

pi_local = pigpio.pi()

pi_local.hardware_clock(4, 32768) # 32.768 kHz clock on GPIO 4
# pi_local.hardware_clock(4, 34406)
