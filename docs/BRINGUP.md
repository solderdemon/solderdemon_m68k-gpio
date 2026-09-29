# Assembly and first power-up

## Assembly

1. Low parts first: R1, C1–C12, D2 BAT85 (black ring = cathode, towards the square pad), D1 LED (flat side, square pad).
2. RN1–RN4: the dot (common pin 1) goes to the square pad.
3. DIP-16/20 sockets, notch as shown on the silkscreen.
4. C13 47 µF (negative lead away from the square pad), J2, J3.
5. J1 last: press the socket flat against the board, body overhanging the right edge.

Do not insert the ICs yet.

## Checks without ICs

| What | Expected |
|---|---|
| Resistance +5V–GND (C13) | > 1 kΩ, no short |
| D2 with a diode tester, red on J1.57 (/DTACK) | 0.2–0.4 V forward, open the other way |
| Powered from the mainboard, J2.18 and J3.18 | 4.75–5.25 V, D1 lit |
| Every J2/J3 signal pin (1–16) to GND | about 5 V through RN1–RN4 |
| U1–U12 sockets, VCC pin | 5 V |

The SolderDemon m68k should boot with the card inserted and no ICs: D2 only conducts when U1 pulls /CARD low.

## ICs

| Ref | Part | Package |
|---|---|---|
| U1 | 74HCT688 | DIP-20 |
| U2 | 74HCT238 | DIP-16 |
| U3 | 74HCT138 | DIP-16 |
| U4 | 74HCT175 | DIP-16 |
| U5, U7, U9, U11 | 74HCT574 | DIP-20 |
| U6, U8, U10, U12 | 74HCT541 | DIP-20 |

Power off and insert them. U2 (238) and U3 (138) have the same pinout but opposite output polarity: swapping them makes the 541s drive the data bus all the time and hangs the boot. U4 is the third DIP-16. 74HC parts work only if the bus levels are good; HCT is the safe choice.

After power-on the SolderDemon m68k should boot as usual. If boot hangs, check that U3 pins 15, 14, 12 and 11 are high at rest, then that /DTACK (J1.57) is not stuck low.

## Software check

```sh
cd software
make                 # needs the SolderDemon m68k SDK in ../../solderdemon_m68k (or SOLDERDEMON_M68K_DIR)
```

**Unplug anything from J2 and J3**, then load `software.bin` the usual way (Kermit/SD). Expected output:

```
GPIO card at $F40001: self-test OK
Inputs D..A: FFFFFFFF
```

`FFFFFFFF` means every input is pulled up. Short J2.1 (A0) to J2.17 (GND) and read again: you should see `FFFFFFFE`.

If the self-test reports bad pins (bits 0–7 A, 8–15 B, 16–23 C, 24–31 D):

- all 32 bad: probe U2 (pins 15, 14, 13, 12, 11 = WR_A, B, DIR, C, D) for short high pulses during writes, and U3 for low pulses during reads;
- one whole port bad: that port's 574 or 541, or its U4 output (/Q0..3 = U4 pins 3, 6, 11, 14 must go low when the port is an output);
- the same pattern on two ports: an A1–A3 fault on U2/U3;
- a single pin: solder joint, RN pin, or a damaged 574/541.

## What to measure on the first prototype

- /DTACK low level during a card cycle: must be below 0.8 V.
- Rising edge of WR_A (U2.15) relative to D0..D7 being stable during a write.
- /DTACK release after /LDS negates.
- 541 data-bus release after /LDS negates on a read.
- Card supply current (a few mA expected with no load).
