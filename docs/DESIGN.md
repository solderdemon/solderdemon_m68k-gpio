# How the card works

## Block diagram

```
J1 (SolderDemon m68k bus)
 ├─ /IOSEL, /LDS, A19..A13 ─► U1 74HCT688 ─ /CARD ─┬─► D2 BAT85 ─► /DTACK (open drain, R21 1k2 on the mainboard)
 │                                                 ├─► U2 74HCT238 /E1 ─ WR_A, WR_B, WR_DIR, WR_C, WR_D (active high)
 ├─ A1, A2, A3, R/W ──────────────────────────────►┤
 │                                                 └─► U3 74HCT138 /E0 ─ /RD_A, /RD_B, /RD_C, /RD_D (active low)
 ├─ /RESET ─► U4 /MR
 └─ D0..D7 ◄─► U5/U7/U9/U11 D (write), U6/U8/U10/U12 Y (read), U4 D0..D3 (write)

Port A:  D0..D7 ─► U5 74HCT574 ─ PA0..7 ─► J2 1..8     RN1 8×10k pulls PA0..7 to +5V
                   OE ← U4 /Q0
         D0..D7 ◄─ U6 74HCT541 ◄─ PA0..7
Port B:  U7, U8, RN2, U4 /Q1 ─► J2 9..16
Port C:  U9, U10, RN3, U4 /Q2 ─► J3 1..8
Port D:  U11, U12, RN4, U4 /Q3 ─► J3 9..16
```

## Addressing

In the mainboard PLD, `/IOSEL = CPUSP * A23 * A22 * A21 * A20`. The signal is **not qualified by /AS** and is inactive in CPU space. The eighth pair of comparator U1 takes **/LDS** (P7 against GND); the CPU only asserts /LDS inside /AS, so `/CARD` is a qualified byte strobe. /IOSEL goes to U1's enable input.

U1 compares A19..A13 with `0100000`. The card occupies the **$F40000–$F41FFF** window. U2 and U3 decode A3..A1; A12..A4 are not decoded, so the registers repeat every 16 bytes.

| A3 A2 A1 | Address | Write (U2 Yn, R/W=0) | Read (U3 /Yn, R/W=1) |
|---|---|---|---|
| 000 | $F40001 | `WR_A` → U5 | `/RD_A` → U6 |
| 001 | $F40003 | `WR_B` → U7 | `/RD_B` → U8 |
| 010 | $F40005 | `WR_DIR` → U4 | — (bus floats) |
| 011 | $F40007 | `WR_C` → U9 | `/RD_C` → U10 |
| 100 | $F40009 | `WR_D` → U11 | `/RD_D` → U12 |
| 101–111 | $F4000B–$F4000F | — | — |

A and B keep the addresses of the 16-pin version, so its software still works on ports A/B.

D2 acknowledges every **/LDS** cycle in the window, including unused register addresses. A cycle with only /UDS (even address) is not acknowledged and ends in a bus error from the mainboard watchdog; the card is byte-access only. Reads that nothing drives return garbage; the driver never does them.

The on-board DUART sits at $F00000–$F0003F; the usual Xosera/IDE cards live at $F80000 and up. Two GPIO cards in one system need a different mask on U1's R inputs (change `BASE` in `tools/build_card.py`).

## Direction

U4 (74HCT175) holds four bits, 1 = output: D0..D3 → ports A..D. The 574's OE is active low, so it takes the flip-flop's /Q. /RESET clears U4: `/Q = 1`, all 574 outputs are high-Z, every pin is an input pulled high by RN1..RN4.

The 74HCT574 has no reset, so its latch holds random data after power-up. This is harmless while the port is an input; `gpio_init()` and `gpio_config()` always write the latches **before** the direction, so a port never turns on with garbage.

Neither the direction register nor the latches can be read back; the driver keeps copies. A read returns the **pin** levels through the 541s, which for an output is the level actually on the pin (useful to spot a short).

## Bus cycles

**Write.** The MC68010 drives the data bus and R/W before asserting /LDS (S3 → S4). `/CARD` falls one 688 delay after /LDS; U2 is enabled by it and its output **rises** — that edge clocks U4 or the 574, while the data is already stable. Hold time after the edge is the whole active /LDS period, since R/W stays low until after /LDS negates. A 138 (active low) would clock at the *end* of /LDS instead, where the 68010's 15 ns data hold is shorter than the decoder delay — that is why the card has both decoders.

**Read.** On a read /AS and /LDS are asserted together (S2). U1 → U3 → 541 enable is three HCT delays, about 80 ns worst case; the CPU latches data at the falling edge of S6, about 200 ns later at 10 MHz. The 541 releases D0..D7 about two delays after /LDS negates.

**DTACK.** On the SolderDemon m68k mainboard (as on rosco_m68k r2), /DTACK is open drain: the address decoder only enables its output low (GAL: `DTACK.T = GND`, `DTACK.E = /PPDTACK`; CPLD r2.14: `DTACK.oe`), the XR68C681 DUART output is open drain too, and R21 (1.2 kΩ) pulls the line up. D2 (BAT85, cathode to /CARD) joins that wired-OR: when /CARD is low it sinks ≈4 mA from R21; when /CARD is high it is reverse biased.

Because /CARD follows /LDS, a write cycle is acknowledged only after S4, so the CPU may insert a wait state; that costs one clock period per write and is otherwise harmless.

Low level on /DTACK: 74HCT688 VOL ≤ 0.26 V at 4 mA + BAT85 VF ≈ 0.35–0.40 V at 4 mA → **≤ 0.66 V**, against VIL = 0.8 V for the 68010. The margin is small; use a real Schottky (BAT85, BAT43, 1N5817 — not a 1N4148, whose 0.7 V drop does not work). Release after /LDS negates is one 688 delay plus the R21 rise time, the same as any open-drain source on the bus.

Nominally everything is asynchronous and independent of the CPU clock. Actual setup/hold, the DTACK low level and its release must still be checked with a scope on the first prototype.

## Pins and levels

- All logic runs from the bus 5 V. Inputs are HCT (VIH = 2.0 V), so 3.3 V logic can drive **inputs** directly. Outputs swing to 5 V: a 3.3 V device on an output port needs its own level shifter or series resistor.
- 74HCT574 outputs: ±6 mA for guaranteed logic levels, ±35 mA absolute per pin, 70 mA through VCC/GND for the whole chip. LEDs with a resistor are fine; relays, motors and power LEDs need a transistor or ULN2803.
- The 574 outputs also feed the 541 inputs; that is just CMOS input load.
- RN1..RN4 (bussed 10 kΩ SIP-9) pull every pin to 5 V. An output driving low sinks 0.5 mA extra per pin.
- Nothing protects the pins against voltages outside 0–5 V; every IC is socketed so a damaged 574 or 541 is a quick swap.

## Power

- C1..C12 are 100 nF next to each IC; C13 is 47 µF on the 5 V input.
- J2.18 and J3.18 are the bus +5V directly, with no fuse. Keep the external load small (≈100 mA in total) and never short it. Pins 17, 19 and 20 on both headers are GND.
- Idle current of the logic is well under 1 mA.

## Mechanical

- 153 × 96 mm, 2 layers, 1.6 mm FR-4, R3 corners.
- J1 is a standard right-angle 2×32 socket, 2.54 mm pitch. The body overhangs the right edge, pin 1 at the bottom. It mates with the straight `pin-2X32` headers on the busboard (29.21 mm slot pitch).
- J2 (ports A/B, upper) and J3 (ports C/D, lower) are right-angle, unshrouded 2×10 pin headers at the same left-edge positions as the former IDC connectors. Their pins face outward. Existing IDC adapters retain the same signal mapping, but the headers are unkeyed; check cable orientation.
- No mounting holes: the card is held by the busboard socket.

## Changes from the MCP23S17 prototype (archived in `solderdemon_m68k-gpio-backups/r2-mcp23s17`)

| | MCP23S17 prototype | r1 |
|---|---|---|
| I/O | 2 × MCP23S17 on bit-banged SPI | 74HCT574 + 74HCT541 per port, 4 ports |
| Pins | 16 × 5 V + 16 × 3.3 V | 32 × 5 V |
| Direction | per pin | per 8-pin port |
| Pull-ups | software, 100 k | fixed 10 k resistor arrays |
| Interrupt-on-change | yes (polled) | no |
| Speed | ~100 bus cycles per register | 1 bus cycle per port |
| DTACK | 74AHCT126 | BAT85 diode |
| ICs | 8, incl. 2 × DIP-28 expanders and a 3.3 V LDO | 12, all stock 74HCT |
| Size | 116 × 96 mm | 153 × 96 mm |
| J2 pin 20 | INTA | GND |

A 16-pin prototype (ports A/B only, 8 ICs, 116 × 96 mm) is archived in `solderdemon_m68k-gpio-backups/r3-16pin`.
