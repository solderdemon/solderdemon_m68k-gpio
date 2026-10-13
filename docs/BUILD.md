# Regenerating the files

The schematic, PCB, BOM and local libraries are not edited by hand: the scripts in `tools/` create them. To change the schematic or placement, edit `tools/build_card.py` and rerun the pipeline.

## Requirements

- KiCad 10 (its bundled Python and `kicad-cli`)
- Docker Desktop with `dinoboards/cpld-toolchain:latest` to compile `cpld/gpio_u1.pld` for the ATF1504AS PLCC-84 and verify locked pins
- **Java 25+**. Freerouting 2.4.1 lives in the workspace `tools/` directory and `tools/route_card.py` finds it itself; `FREEROUTING_JAR` overrides it. Routing goes through `tools/route_swarm.py`, which runs several differently-tuned routers at once and keeps the first result KiCad DRC calls clean -- see [AGENTS.md](../../AGENTS.md) section 6.
- clang or gcc for the driver test

## Pipeline

```sh
K="/c/Program Files/KiCad/10.0/bin"

"$K/python.exe" tools/make_logo.py                    # SolderDemon_Logo footprint from logo.png (only when the logo changes)
cd cpld && ./build.sh && cd ..                         # ATF1504AS JEDEC and pin lock
"$K/python.exe" tools/build_card.py                   # schematic, symbols, BOM and an unrouted PCB with silkscreen
"$K/python.exe" tools/route_card.py                   # routing, GND pours, clean-up

# build_card.py --schematic-only regenerates the schematic, symbols and BOM and keeps the routed PCB.

"$K/kicad-cli.exe" sch erc -o erc.rpt solderdemon_m68k-gpio.kicad_sch
"$K/kicad-cli.exe" pcb drc --schematic-parity --severity-error --severity-warning -o drc.rpt solderdemon_m68k-gpio.kicad_pcb

clang -std=c99 -Wall -Wextra -DGPIO_HOST_TEST -Isoftware tests/test_driver.c software/gpio.c -o tests/test_driver
./tests/test_driver > driver-verification.txt
```

`build_card.py` preserves `solderdemon_m68k-gpio.kicad_pro`; it holds the DRC rules: 0.2 mm minimum track, 0.2 mm clearance, 0.6/0.3 mm vias. Do not run the full build on the existing routed board unless a new routing run is intended.

The r2 board is not ready for manufacturing until the CUPL fitter has emitted a JEDEC with the specified pin assignments, the board is routed, and ERC/DRC are clean. Existing files under `manufacturing/` and existing render PNGs are from r1.

## Manufacturing files

```sh
mkdir -p manufacturing
"$K/kicad-cli.exe" pcb export gerbers --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts -o manufacturing/ solderdemon_m68k-gpio.kicad_pcb
"$K/kicad-cli.exe" pcb export drill -o manufacturing/ solderdemon_m68k-gpio.kicad_pcb
"$K/kicad-cli.exe" pcb export pos --format csv --units mm -o manufacturing/solderdemon_m68k-gpio-pos.csv solderdemon_m68k-gpio.kicad_pcb
"$K/kicad-cli.exe" sch export pdf -o manufacturing/solderdemon_m68k-gpio-schematic.pdf solderdemon_m68k-gpio.kicad_sch
"$K/kicad-cli.exe" pcb render --side top --width 1600 --height 1000 -o solderdemon_m68k-gpio-top.png solderdemon_m68k-gpio.kicad_pcb
"$K/kicad-cli.exe" pcb render --side bottom --width 1600 --height 1000 -o solderdemon_m68k-gpio-bottom.png solderdemon_m68k-gpio.kicad_pcb
"$K/kicad-cli.exe" pcb render --side top --perspective --rotate -40,0,-20 --background transparent --light-camera 0.2 --light-top 0.8 --light-side 0 --light-bottom 0 --width 1600 --height 1000 -o solderdemon_m68k-gpio-3d.png solderdemon_m68k-gpio.kicad_pcb
cp BOM.csv manufacturing/solderdemon_m68k-gpio-bom.csv
```

Fab parameters: 2 layers, 1.6 mm FR-4, 1 oz copper, 0.2 mm minimum track and clearance, 0.3 mm minimum hole.

## Changing the address

The address decode is in `cpld/gpio_u1.pld`. `BASE` in `tools/build_card.py` controls only the schematic notes. After changing the address:

1. regenerate the board;
2. update `GPIO_CARD_BASE` in `software/gpio.h`;
3. update `BASE` in `tools/build_card.py` for matching notes and silkscreen;
4. rebuild the JEDEC and recheck the fitted pins.
