# r1 bus timing

Worst-case check of the three ATF1502AS-10 against the MC68010 bus at 10 MHz (100 ns clock). Numbers come from the M68000 User's Manual, section 10.10 (10 MHz column, which also covers the MC68010), the ATF1502AS(L) datasheet (Atmel-0995L, -10 grade, table 11-4) and the Nexperia BAT85 datasheet. Times are counted from the rising edge that starts S0 of the bus cycle.

## Parameters used

| Source | Parameter | Value |
|---|---|---|
| 68000 #9 | clock high to AS/DS asserted | ≤ 50 ns |
| 68000 #11 | address valid to AS/DS asserted | ≥ 20 ns |
| 68000 #13 | AS/DS negated to address invalid | ≥ 30 ns |
| 68000 #14A | DS width asserted (write) | ≥ 95 ns |
| 68000 #25 | DS negated to data-out invalid (write) | ≥ 30 ns |
| 68000 #26 | data-out valid to DS asserted (write) | ≥ 30 ns |
| 68000 #27 | data-in valid to clock low (read setup) | ≥ 10 ns |
| 68000 #28 | DS negated to DTACK negated | ≤ 190 ns |
| 68000 #29A | DS negated to data-in high impedance | ≤ 150 ns |
| 68000 #47 | asynchronous input setup (DTACK) | ≥ 10 ns |
| ATF1502AS-10 | tPD1 pin to combinational output | ≤ 10 ns |
| ATF1502AS-10 | tSU / tH, global clock pin | 7 ns / 0 ns |
| ATF1502AS-10 | tIN + tLAC + tIOE + tZX1, pin to output enabled | ≤ 12.5 ns |
| ATF1502AS-10 | tIN + tLAC + tIOE + tXZ, pin to output disabled | ≤ 12.5 ns |
| ATF1502AS-10 | VOL | ≤ 0.45 V at 12 mA |
| BAT85 | VF | ≤ 320 mV at 1 mA, ≤ 400 mV at 10 mA |
| host | /DTACK pull-up R21 | 1.2 kΩ; host /IOSEL from an ATF1502AS-10, address only |

The host does not acknowledge the I/O window itself: its /DTACK covers only ROM, RAM and (with JP4) the expansion space, so in `$F40000–$F41FFF` only D2 answers.

## Read cycle: zero wait states

| Event | Worst case |
|---|---|
| /LDS asserted (S2 + #9) | 150 ns |
| host /IOSEL valid (address + 10 ns, ≥ 10 ns before /LDS by #11) | before 140 ns |
| U1 /CARD and RD_x valid (+ tPD1) | 160 ns |
| /DTACK low through D2 (diode and bus edge ≈ 5 ns) | 165 ns |
| **/DTACK required** (S4 falling edge 250 ns − #47) | **240 ns — margin 75 ns** |
| U2/U3 drive D0..D7 (RD_x + 12.5 ns, data path tPD1 10 ns) | 173 ns |
| **data required** (S6 falling edge 350 ns − #27) | **340 ns — margin 167 ns** |

Because #47 is met for /DTACK, #31 (DTACK to data valid) does not apply (manual note 5).

After /LDS rises, RD_x falls within 10 ns and U2/U3 release D0..D7 within a further 12.5 ns: **≤ 23 ns against #29A 150 ns**. Hold (#29 = 0 ns) is met because the outputs only start to turn off after /LDS rises.

## Write cycle: one wait state at most, data latched safely

/LDS is asserted only in S4 of a write, up to 50 ns after its rising edge, which is exactly where /DTACK is sampled. /CARD therefore arrives 0–10 ns either side of the S4 falling edge: the cycle runs with zero or one wait state depending on the CPU's actual #9. Both are correct; at worst a GPIO write takes 500 ns instead of 400 ns. (The same effect is described for strobe-decoded /DTACK in `solderdemon_m68k-ramboard/docs/DESIGN.md`.)

The port registers clock on the rising edge of WR_x, which follows the falling edge of /LDS by ≤ 10 ns:

- **setup:** D0..D7 are valid ≥ 30 ns (#26) before /LDS, so ≥ 30 ns before the clock edge against tSU 7 ns;
- **hold:** data stays valid until /LDS has been low ≥ 95 ns (#14A) and 30 ns beyond (#25), i.e. > 100 ns after the edge, against tH 0 ns.

The direction register (WR_DIR on pin 44, product-term clock) has the same margins against tASU 3 ns / tAH 3 ns.

WR_x are clean single pulses: /LDS is the last input to arrive (#11: address ≥ 20 ns earlier, so host /IOSEL ≥ 10 ns earlier) and the first to leave (#13: address held ≥ 30 ns after /LDS), so only one input of the decode term changes at each edge.

## /DTACK release

When /LDS rises, /CARD goes high within 10 ns and D2 stops conducting; R21 pulls /DTACK up. With 150 pF on the line (RC = 180 ns) /DTACK passes 2.0 V about 75 ns later: **≈ 85 ns against #28 190 ns.**

## /DTACK low level

R21 sinks (5 V − 0.5 V) / 1.2 kΩ ≈ 3.7 mA through D2 into U1.

- BAT85 at 3.7 mA: ≤ 0.37 V (between the 1 mA and 10 mA limits).
- ATF1502AS: VOL ≤ 0.45 V is specified at 12 mA; scaled to 3.7 mA it is about 0.14 V.
- /DTACK low ≈ **0.5 V against VIL 0.8 V** of the MC68010.

Adding the 12 mA VOL limit to the diode limit gives 0.82 V, so measuring /DTACK low on a scope at bring-up remains part of [BRINGUP.md](BRINGUP.md). If it ever reads above 0.6 V, U1 can drive /DTACK directly as an open-drain output (`CARD_N = 'b'0; CARD_N.oe = SEL;`, as the host's own decoder does) and D2 is replaced by a wire.

## Not covered

- Signal integrity on the bus (ringing, crosstalk) — not modelled.
- Even-address byte cycles get no /DTACK and end in the host watchdog's BERR after 64 clocks, as documented.
- External loads on J2/J3: ATF1502AS outputs sink 12 mA at ≤ 0.45 V and source 4 mA at ≥ 2.4 V.
