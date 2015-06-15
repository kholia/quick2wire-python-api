def revision():
    """Returns a board revision number which corresponds to a partuclar
    change in compatibility for the functions in this module.
    E.g. where i2c bus numbering or GPIO pin definitions change. """
    try:
        with open('/proc/cpuinfo','r') as f:
            for line in f:
                if line.startswith('Revision'):
                    code = int(line.rstrip()[-4:], 16)
                    if code <= 3:
                        return 1 # PCB rev 1.0, model B, 256MB, default i2c bus 0, 26 pin
                    elif code < 16:
                        return 2 # PCB rev 2.0, model A/B, default i2c bus 1, 26 pin
                    else:
                        return 3 # A+/B+/Model 2 B, 40 pin
            else:
                return 0
    except:
        return 0

