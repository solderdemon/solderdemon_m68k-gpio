# ATF r2 assembly and bring-up

This procedure applies to the ATF1504AS r2 board only after the JEDEC, pinout, timing, ERC and DRC gates have passed. The r1 manufacturing files in this branch are not suitable for r2.

1. Check the fabrication files against the final r2 schematic and board revision.
2. Install C1–C8, D2 BAT85 (band to cathode K), and RN1–RN4 (common pin 1 at the square pad).
3. Fit the PLCC-84 socket with its pin-1 mark aligned to U1. Install C9 47 µF with correct polarity, then J4 JTAG and the two right-angle 2×10 GPIO headers J2/J3.
4. Fit J1 at the bus edge. With U1 absent, check for a short between +5 V and GND and verify +5 V reaches J4 pin 4 and all U1 VCC pins.
5. Insert the ATF1504AS with pin 1 aligned. Program the verified `cpld/bin/gpio_u1.jed` over J4. This CPLD needs JTAG; a TL866 cannot program it.
6. With no external circuit on J2/J3, reset the host and confirm all four ports are inputs. Check the register addresses and GPIO pinout using the driver self-test, then test /DTACK and bus timing on a scope.

Use only 5 V for this board. Size loads to the ATF1504AS output current specification. Disconnect power before moving the CPLD or any header wiring.
