#!/usr/bin/env python3

# znp-uart-test
#
# Use this script as a sanity check after you burn the ZNP coordinator
# firmware on your zzh stick.
#
# !! Before you run this script, make sure you flash the
#    latest Z-Stack Coordinator firmware on your zzh stick.
#
#  Get it from: https://github.com/Koenkk/Z-Stack-firmware/tree/master/coordinator/Z-Stack_3.x.0/bin
#
#  Flash it with:
#    python3 cc2538-bsl.py -P <port> -evw <coordinator-firmware>.hex
#
#  Grab this test script
#    wget https://gist.githubusercontent.com/omerk/0ee0e447a9e36786b4ff71d8f8126a23/raw/2dd88e739fe601d7c1e246b9bc117d513d47309e/znp-uart-test.py
#
#  Modify the serial port settings, if needed, and run:
#    python3 znp-uart-test.py
#
#  If you get the "ModuleNotFoundError: No module named 'serial'" error, install pyserial:
#    sudo pip3 install pyserial

import sys, serial, time

# !! Change serial port accordingly
if len(sys.argv) < 2 or sys.argv[1] is None:
    print("Missing adapter path. Usage example: %s /dev/ttyUSB0", sys.argv[0])
    exit(1)

ser = serial.Serial(sys.argv[1], 115200, timeout=2)
#ser = serial.Serial("COM5", 115200, timeout=2)

##############################################################

cmd_ping = [0xFE, 0x00, 0x21, 0x01, 0x20]  # ZNP PING command
resp_exp = b'\xfe\x02a\x01Y\x06='

time.sleep(1)

try:
    ser.flushInput()

    ser.write(serial.to_bytes(cmd_ping))
    time.sleep(1)

    resp_count = ser.in_waiting
    resp_data = ser.read(resp_count)
    print("Got {} bytes in response to PING command: {}".format(resp_count, resp_data))

    if resp_count == 7:
        if resp_data == resp_exp:
            print("PASS|OK")
            sys.exit(0)
        else:
            print("FAIL|Expected response mismatch")
            sys.exit(1)
    else:
        print("FAIL|Expected length mismatch")
        sys.exit(1)
except Exception as e:
    print("FAIL|{}".format(e))
    sys.exit(1)
