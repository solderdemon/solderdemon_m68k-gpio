# ATF1504AS GPIO card design

The 5 V ATF1504AS-10JU84 in U1 replaces the twelve 74HCT logic ICs of r1. Its CUPL source, `cpld/gpio_u1.pld`, is the source of truth for the address decode, register behavior and pin assignments. `tools/build_card.py` reads those pin assignments when generating the KiCad schematic and PCB.

J1 supplies only +5 V and GND. All eight CPLD supply pins connect to +5 V; its eight ground pins connect to GND. J4 is the 5 V JTAG programming header. D2 isolates U1's active-low card select from the motherboard's open-drain /DTACK line. Four SIP-9 networks pull every GPIO pin up with 10 kΩ.

| Address | Write | Read |
|---|---|---|
| `$F40001` | Port A latch | Port A pins |
| `$F40003` | Port B latch | Port B pins |
| `$F40005` | Direction bits 0..3, A..D | Undefined |
| `$F40007` | Port C latch | Port C pins |
| `$F40009` | Port D latch | Port D pins |

The bus uses lower-byte access only. The address decoder checks /IOSEL, /LDS and A19..A13; A1..A3 select a register. Each port has an 8-bit registered output and one direction bit. Reset clears the direction bits, leaving all GPIO pins as inputs. Reads sample the physical pins, including externally driven levels. The CPLD drives D0..D7 only during a selected read. The existing software register interface is retained.

The two right-angle 2×10 GPIO headers keep the r1 pinout. J2 carries ports A/B, J3 carries ports C/D. Pins 17, 19 and 20 are GND; pin 18 is +5 V. The four pull-up networks remain one straight column beside them.

This r2 design has a clean schematic ERC and routed-board DRC, but its CUPL has not yet passed the WinCUPL/Atmel fitter. It is not ready for manufacture until `cpld/build.sh` produces a JEDEC file, confirms the exact fitted pinout, and timing and register behavior are verified. The CPLD's guaranteed output source current is 4 mA at the datasheet VOH test point, lower than the former 74HCT574 driver.
