# Quick2Wire Python API

A Python library for controlling the hardware attached to the
Raspberry Pi's header pins.

Status: Tested on Raspberry Pi Zero 2W running Raspberry Pi OS (`bookworm`) in
May-2024.

### Process

```
sudo apt install i2c-tools vim git build-essential -y

sudo raspi-config nonint do_i2c 0

sudo raspi-config nonint get_i2c

ls /dev/i2*

sudo i2cdetect -y 1  # For modern Pis, you will need to specify 1 as the port
```

Set up this library:

```
python3 setup.py install --user  # inside the repository folder
```

Set up pigpio:

```
wget https://github.com/joan2937/pigpio/archive/master.zip

unzip master.zip
cd pigpio-master
make
sudo make install
```

Usage:

```
sudo pigpiod

python3 radio_clk.py

python3 radio.py
```

At this point the `i2cdetect` command is able to detect the Si4732.

```
pi@radio:~/quick2wire-python-api $ sudo i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- 11 -- -- -- -- -- -- -- -- 1a -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

### References

- https://github.com/kholia/ConsensusBasedTimeSync/tree/master/Si4732-BoB-v4

- https://groups.io/g/si47xx/message/376
