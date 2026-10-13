# ATF r1 assembly and bring-up

The r1 fabrication files are in `manufacturing/`; `solderdemon_m68k-gpio-fab.zip` is the archive for the board house. The CPLDs need a JTAG programmer for ATF15xx (for example Microchip ATDH1150USB); a TL866/T48 cannot program them.

1. Check the fabrication files against the final r1 schematic and board revision.
2. Install C1–C12, D2 BAT85 (band to cathode K), and RN1–RN4 (common pin 1 at the square pad).
3. Fit three PLCC-44 sockets with their pin-1 marks aligned to U1–U3. Install C13 47 µF with correct polarity, J4 JTAG and right-angle GPIO headers J2/J3.
4. Fit J1 at the bus edge. With U1–U3 absent, check for a short between +5 V and GND and verify +5 V reaches J4 pin 4 and all CPLD VCC pins.
5. Insert the three ATF1502AS devices with pin 1 aligned. Program `cpld/bin/gpio_decode.jed`, `gpio_ab.jed` and `gpio_cd.jed` through the J4 chain in U1–U3 order. These CPLDs need JTAG; a TL866 cannot program them.
6. With no external circuit on J2/J3, reset the host and confirm all four ports are inputs. Check the register addresses and GPIO pinout using the driver self-test, then check /DTACK on a scope: low level below 0.6 V (calculated ≈ 0.5 V, see [TIMING.md](TIMING.md)) and clean release after /LDS.

Use only 5 V for this board. Size external loads to the ATF1502AS output current specification. Disconnect power before moving any CPLD or header wiring.
