from tuning import Tuning
import usb.core
import usb.util
import time
# Accessing the Direction of Arrival and printing it every 100ms

dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
#print dev
if dev:
    Mic_tuning = Tuning(dev)
    while True:
        try:
            print Mic_tuning.direction
            time.sleep(0.1)
        except KeyboardInterrupt:
            break
