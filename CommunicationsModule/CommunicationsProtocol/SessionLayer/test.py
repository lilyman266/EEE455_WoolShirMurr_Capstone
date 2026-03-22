import sys
import SoapySDR

print(sys.executable)
print(SoapySDR.__file__)
print(SoapySDR.Device.enumerate())