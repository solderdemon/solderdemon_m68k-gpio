# ATF r2 assembly and bring-up

Use this procedure after the final r2 JEDEC, pinout, timing, ERC and DRC gates pass. The r1 manufacturing files in this branch are not suitable for r2.

1. Check the fabrication files against the final r2 schematic and board revision.
2. Install C1–C12, D2 BAT85 (band to cathode K), and RN1–RN4 (common pin 1 at the square pad).
3. Fit three PLCC-44 sockets with their pin-1 marks aligned to U1–U3. Install C13 47 µF with correct polarity, J4 JTAG and right-angle GPIO headers J2/J3.
4. Fit J1 at the bus edge. With U1–U3 absent, check for a short between +5 V and GND and verify +5 V reaches J4 pin 4 and all CPLD VCC pins.
5. Insert the three ATF1502AS devices with pin 1 aligned. Program `cpld/bin/gpio_decode.jed`, `gpio_ab.jed` and `gpio_cd.jed` through the J4 chain in U1–U3 order. These CPLDs need JTAG; a TL866 cannot program them.
6. With no external circuit on J2/J3, reset the host and confirm all four ports are inputs. Check the register addresses and GPIO pinout using the driver self-test, then test /DTACK and bus timing on a scope.

Use only 5 V for this board. Size external loads to the ATF1502AS output current specification. Disconnect power before moving any CPLD or header wiring.
