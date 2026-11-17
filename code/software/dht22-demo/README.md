# GPIO room monitor: DHT22 / AM2302

A serial-console demo for the SolderDemon m68k GPIO card r1. The pictured white
sensor resembles a DHT22/AM2302; its exact type is not visible in the photo.
The program expects the DHT22 40-bit protocol, not DHT11. It prints temperature
in °C and relative humidity every approximately three seconds. Checksum and
response timeouts are reported; press a serial key to exit.

## Connections

Power everything down before wiring. Read the labels on the sensor module:

| Sensor module | GPIO card J3 |
| --- | --- |
| `+` | pin 18 (+5 V) |
| `out` | pin 16 (D7) |
| `-` | pin 17 (GND; 19/20 also GND) |

The module pictured has a resistor marked 512 (5.1 kΩ), and the GPIO card
also pulls D7 up to +5 V. No additional pull-up should be needed. GPIO port D
is switched as an entire byte: **leave J3 pins 9–15 disconnected**, since the
program drives all of port D low during the start pulse. The demo also sets
all four port directions to input; disconnect other externally driven circuits
while trying it. J3 pin 18 is unfused +5 V; check pin orientation carefully.

## Build and run

The compiled `dht22-demo.bin` is ready for the serial-receive loader. To rebuild
with rosco CLI and Docker, from the repository root:

```sh
rosco init solderdemon_m68k-gpio/software/dht22-demo/rosco-build --board rosco_m68k --language c --docker --target hardware --yes
cp solderdemon_m68k-gpio/software/dht22-demo/dht22.c solderdemon_m68k-gpio/software/dht22-demo/rosco-build/kmain.c
rosco -C solderdemon_m68k-gpio/software/dht22-demo/rosco-build build --docker
cp solderdemon_m68k-gpio/software/dht22-demo/rosco-build/rosco-build.bin solderdemon_m68k-gpio/software/dht22-demo/dht22-demo.bin
```

Start the serial-receive loader and upload the binary with your usual serial
workflow. The program expects the standard 10 MHz system and supervisor-mode
serial loader. The polling algorithm compares pulse lengths, but actual timing,
interrupts, and hardware have not yet been verified on the board. If it reports
timeouts or checksum errors, check the wiring and exact sensor model before
treating values as measurements.

Protocol reference: [Aosong AM2302 technical manual](https://www.aosong.com/uploadfiles/2025/04/20250417105409216.pdf).
