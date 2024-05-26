#!/usr/bin/python3

# Original source: https://gist.github.com/JonathanThorpe/f23480c781ca62a28647
# AM and SSB support by Dhiru Kholia (VU3CER).

import quick2wire.i2c as i2c
import time
import RPi.GPIO as GPIO
import threading
import logging
import sys

#Work in progress library for Si473x for Raspberry Pi by Jonathan Thorpe <jt@jonthorpe.net>
#SiPiRadio
#
#Wiring:
# RPi                      Si473x Module
# i2s SDA                  i2c SDIO
# i2s SCL                  i2c SCLK
#
# GPIO 15                  RESET
# GPIO 4                   RCLK
#
# PCM_CLK                  DCLK
# PCM_FS                   DFS
# PCM_IN                   DOUT
#
# GPIO 4 must be set to clock mode at the appropriate rate.
# Can't find a way to do this in Python yet - use the command line:
#   gpio -g mode 4 clock
#   gpio -g clock 4 34406
#
# Before running this program, you need to load the my_loader.c kernel module from here:
# https://www.raspberrypi.org/forums/viewtopic.php?f=44&t=91237
#
# Before compiling this module, ensure daifmt is set in clock and frame slave mode (Si47xx operates in slave only mode):
# .daifmt = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_CBS_CFS
#
#
# TODO (essentially implement more of the programmer's guide):
#   1. Support AM/SW/LW
#   2. Get Status information
#   3. FM RDS information
#   4. Make sure I'm using ALSA properly - seems a bit hacky
#
# Acknowledgments:
#    https://github.com/rickeywang/Si4737_i2c was useful for seeing how to program this device over i2c

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

# ===========================================================================
# Si473x I2C / I2S Class
# ===========================================================================

class SiPiRadio():
  # GPIO pin for issuing the device reset
  GPIO_RESET = 27

  # Si473x i2c address
  I2C_ADDRESS = 0x11

  REFCLK_FREQ = 32768
  REFCLK_PRESCALE = 1

  # Constants
  SI4735_CMD_POWER_UP = 0x01
  SI4735_CMD_GET_REV = 0x10
  SI4735_CMD_POWER_DOWN = 0x11
  SI4735_CMD_SET_PROPERTY = 0x12
  SI4735_CMD_GET_PROPERTY = 0x13
  SI4735_CMD_FM_TUNE_FREQ = 0x20, 0x00
  SI4735_CMD_AM_TUNE_FREQ = 0x40, 0x00
  SI4735_CMD_FM_TUNE_STATUS = 0x22
  SI4735_CMD_GET_INT_STATUS = 0x14

  SI4735_OUT_RDSi = 0x00  # RDS only
  SI4735_OUT_ANALOG = 0x05
  SI4735_OUT_DIGITAL1 = 0x0B  # DCLK, LOUT/DFS, ROUT/DIO
  SI4735_OUT_DIGITAL2 = 0xB0  # DCLK, DFS, DIO
  # SI4735_OUT_BOTH=(SI4735_OUT_ANALOG | SI4735_OUT_DIGITAL2)

  # Statuses
  SI4735_STATUS_CTS = 0x80
  SI4735_STATUS_ERR = 0x40
  SI4735_STATUS_STCINT = 0x01

  # Properties
  SI4735_PROP_REFCLK_FREQ = 0x00, 0x02, 0x01
  SI4735_PROP_REFCLK_PRESCALE = 0x00, 0x02, 0x02
  SI4735_PROP_RX_VOLUME = 0x40, 0x00

  # Flags
  SI4735_DIGITAL_I2S = 0x01, 0x00
  SI4735_FLG_INTACK = 0x01

  # Modes
  SI4735_MODE_LW = 0
  SI4735_MODE_AM = 1
  SI4735_MODE_SW = 2
  SI4735_MODE_FM = 3
  # mode = SI4735_MODE_FM
  mode = SI4735_MODE_AM

  # AM
  AM_TUNE_FREQ = 0x40
  SSB_TUNE_FREQ = 0x40

  record_stop = threading.Event()
  record_thread = None

  def byteHigh(self, val):
    return val >> 8

  def byteLow(self, val):
    return val & 0xFF

  def sendCommand(self, cmd, *args):
    with i2c.I2CMaster() as bus:
      if (isinstance(cmd, int)):
        bytesToSend=(cmd,) + args
      else:
        bytesToSend=cmd + args

      logging.debug("Command: " + " ".join('0x%02x' % i for i in bytesToSend))
      bus.transaction(i2c.writing_bytes(self.I2C_ADDRESS, *bytesToSend))

  def getStatus(self):
    with i2c.I2CMaster() as bus:
        return bus.transaction(i2c.reading(self.I2C_ADDRESS, 1))[0][0]

  def ctsWait(self):
    status = 0
    while not status & self.SI4735_STATUS_CTS:
      status = self.getStatus()
      logging.debug("Returned status is: {0:#04x}".format(status))

  def intWait(self, interruptType):
    status = 0

    while not status & interruptType:
      self.sendCommand(self.SI4735_CMD_GET_INT_STATUS, 0x00)
      time.sleep(0.125)
      status = self.getStatus()
      if (not status & interruptType):
        logging.debug('Still waiting. Got status {0:#04x}'.format(status))

  def sendWait(self, cmd, *args):
    self.sendCommand(cmd, *args)
    self.ctsWait()

  def setProperty(self, property, *args):
    self.sendWait((self.SI4735_CMD_SET_PROPERTY,)+property+args)

  def setupCaptureDevice(self):
    logging.debug('Setting up capture device')
    self.pcm_audio_in = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, self.AUDIO_IN_DEV)
    self.pcm_audio_in.setchannels(self.AUDIO_CHANNELS)
    self.pcm_audio_in.setrate(self.AUDIO_SAMPLE_RATE)
    self.pcm_audio_in.setformat(alsaaudio.PCM_FORMAT_S16_LE)

  def setupPlaybackDevice(self):
    logging.debug('Setting up playback device')
    self.pcm_audio_out = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, alsaaudio.PCM_NONBLOCK)
    self.pcm_audio_out.setchannels(self.AUDIO_CHANNELS)
    self.pcm_audio_out.setrate(self.AUDIO_SAMPLE_RATE)
    self.pcm_audio_out.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    logging.debug('Done setting up playback device')

  def captureAudio(self, arg, stop_event):
   self.pcm_audio_in.setperiodsize(160)

   while(not self.record_stop.is_set()):
      l, data = self.pcm_audio_in.read()
      if l:
        #logging.debug("Sending output audio...")
        self.pcm_audio_out.write(data)

  def reset(self):
    GPIO.output(self.GPIO_RESET, False)
    time.sleep(0.01)
    GPIO.output(self.GPIO_RESET, True)
    time.sleep(0.01)

  def powerUp(self, mode=SI4735_MODE_AM):
    logging.debug('Powering up si473x')
    if mode == self.SI4735_MODE_AM:
        data = 0x01
    else:
        data = 0x00
    self.sendWait(self.SI4735_CMD_POWER_UP, data, self.SI4735_OUT_ANALOG)

    # Configure REFCLK
    self.setProperty(self.SI4735_PROP_REFCLK_FREQ,
                     self.byteHigh(self.REFCLK_FREQ),
                     self.byteLow(self.REFCLK_FREQ))

    self.setProperty(self.SI4735_PROP_REFCLK_PRESCALE,
                     self.byteHigh(self.REFCLK_PRESCALE),
                     self.byteLow(self.REFCLK_PRESCALE))

  def setFrequency(self, freq):
    if (self.mode == self.SI4735_MODE_FM):
      logging.debug('Setting frequency to {0} ({1:#04x} {2:#04x})'.format(freq, self.byteHigh(freq), self.byteLow(freq)))
      self.sendWait(self.SI4735_CMD_FM_TUNE_FREQ, self.byteHigh(freq), self.byteLow(freq), 0x00, 0x00)
    elif (self.mode == self.SI4735_MODE_AM):
      logging.debug('Setting AM frequency to {0} ({1:#04x} {2:#04x})'.format(freq, self.byteHigh(freq), self.byteLow(freq)))
      self.sendWait(self.AM_TUNE_FREQ, 0x00, self.byteHigh(freq), self.byteLow(freq), 0x00, 0x01)  #  ANTCAPL is 1 for AM

    logging.debug('Frequency set, just waiting for tuning to complete')
    self.intWait(self.SI4735_STATUS_STCINT)

    if (self.mode == self.SI4735_MODE_FM):
        self.sendCommand(self.SI4735_CMD_FM_TUNE_STATUS, self.SI4735_FLG_INTACK)
    elif (self.mode == self.SI4735_MODE_AM):
        self.sendCommand(0x42, self.SI4735_FLG_INTACK)

  def setVolume(self, vol):
    logging.debug('Setting volume to {0:#04x}'.format(vol))
    self.setProperty(self.SI4735_PROP_RX_VOLUME, vol)

  def init(self):
    # self.setupCaptureDevice()
    # self.setupPlaybackDevice()
    pass

  def __init__(self):
    # self.record_thread = threading.Thread(target=self.captureAudio, args=(1, self.record_stop))
    pass

radio = SiPiRadio()

GPIO.setmode(GPIO.BCM)
# GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)  # we gotta do what we gotta do..
GPIO.setup(radio.GPIO_RESET, GPIO.OUT)

radio.reset()
radio.powerUp()
radio.setVolume(0x63)
# radio.setFrequency(9500)
radio.setFrequency(792)

logging.debug("Execution Complete")

print("q=quit")
cmd = ""
while True:
   cmd = input("Command: ")
   if(cmd=="q"):
      break

# radio.record_stop.set()

GPIO.cleanup()
