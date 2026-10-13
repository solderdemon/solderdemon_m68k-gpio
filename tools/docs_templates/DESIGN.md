# Three ATF1502AS GPIO card design

Three 5 V ATF1502AS-10JU44 CPLDs in PLCC-44 sockets replace the twelve 74HCT ICs of the earlier version. `cpld/gpio_decode.pld`, `gpio_ab.pld` and `gpio_cd.pld` define logic and pin assignments; `tools/build_card.py` reads the pins to generate the KiCad design. All three use the same 44-pin family as SolderDemon 6502.

- U1 decodes /IOSEL, /LDS, A19..A13 and A1..A3, generating five write strobes, four read enables and /CARD.
- U2 holds ports A/B; U3 holds ports C/D. Each has 16 registered GPIO outputs, two direction bits and eight bidirectional CPU data pins.
- Reset clears all four direction bits, leaving all GPIO pins as inputs. Reads sample the physical header pins. U2 and U3 drive D0..D7 only for their selected read cycles.
- D2 BAT85 diode couples /CARD to the motherboard's open-drain /DTACK line. Four SIP-9 networks provide 10 kΩ pull-ups on every GPIO line.
- U1–U3 share +5 V and GND from J1. J4 connects them in one JTAG chain: TDI → U1 → U2 → U3 → TDO.

| Address | Write | Read |
|---|---|---|
| `$F40001` | Port A latch | Port A pins |
| `$F40003` | Port B latch | Port B pins |
| `$F40005` | Direction bits 0..3, A..D | Undefined |
| `$F40007` | Port C latch | Port C pins |
| `$F40009` | Port D latch | Port D pins |

The two right-angle 2×10 GPIO headers keep the pinout of the 74HCT version: J2 carries A/B and J3 carries C/D. Pins 17, 19 and 20 are GND; pin 18 is +5 V. RN1–RN4 remain one straight column beside them.

All three CUPL sources fit with pin assignments kept and emit JEDEC files. The routed board passes KiCad ERC/DRC with schematic parity. Timing and physical behavior still require final verification before manufacturing. Check output current against the ATF1502AS datasheet rather than assuming the previous 74HCT574 limits.
