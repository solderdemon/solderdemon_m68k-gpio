"""SolderDemon m68k GPIO r1: schematic + PCB placement generator. Run with KiCad 10 python.

Direct-mapped card, 32 GPIO at 5 V on two IDC headers, 12 stock 74HCT DIPs. 74HCT688
decodes the card window qualified by /LDS; 74HCT238 makes write strobes and 74HCT138
read enables. Each of the four ports is a 74HCT574 latch whose tri-state outputs drive
the pins (direction per port from a 74HCT175) and a 74HCT541 that reads the pins back.
A Schottky diode from /CARD pulls the open-drain /DTACK line. Nothing to program.
"""
from pathlib import Path
import subprocess, sys, xml.etree.ElementTree as ET
import gpiolib as g
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[1]
CLI = 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
g.LIB = Path('C:/Program Files/KiCad/10.0/share/kicad')
NAME = 'solderdemon_m68k-gpio'
BASE = 0xF40000
W, H = 153.0, 96.0

d = g.Design(NAME, 'SolderDemon m68k GPIO / 32 x 5V, 74HCT', 'r1', '2026-09-30', paper='A2', libname=NAME, ns='solderdemon-gpio-r1/')
DIP = lambda n: f'Package_DIP:DIP-{n}_W7.62mm_Socket_LongPads'
FP_C = 'Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm'
FP_CP = 'Capacitor_THT:CP_Radial_D6.3mm_P2.50mm'
FP_R = 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'
FP_RN = 'Resistor_THT:R_Array_SIP9'
FP_D = 'Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal'
FP_LED = 'LED_THT:LED_D3.0mm'
FP_BUS = NAME + ':PinSocket_2x32_P2.54mm_Horizontal_CardEdge'   # stock socket, silkscreen trimmed at the card edge
LOCAL_FP = ROOT / (NAME + '.pretty')
FP_IDC = 'Connector_IDC:IDC-Header_2x10_P2.54mm_Horizontal'


def named(key, m):
    """Map pins by name; every name in the symbol must be listed (None = no-connect)."""
    pins = {}
    for p in d._pins(key):
        pins[g.one(p, 'name')[1]] = (g.one(p, 'number')[1], p[1])
    assert set(m) == set(pins), (key, 'unknown', set(m) - set(pins), 'missing', set(pins) - set(m))
    for name, (num, typ) in pins.items():
        assert m[name] or typ not in ('input', 'power_in'), f'{key}: input {name} left open'
    return {num: m[name] for name, (num, typ) in pins.items()}


# ---- J1: SolderDemon m68k expansion bus (JP3 pinout, same as rosco_m68k r2) -
bus = {1 + 2 * i: f'A{i + 1}' for i in range(23)}
bus.update({2: '+5V', 4: 'CLK', 6: 'GND', 8: '~{VPA}', 10: 'E', 12: '~{VMA}', 14: '~{IRQ3}', 16: '~{IOSEL}', 18: '~{EXPSEL}',
            20: 'FC0', 22: 'FC1', 24: 'FC2', 26: '~{IRQ5}', 28: '~{IRQ2}', 30: '~{IRQ6}', 32: '~{LDS}', 34: '~{UDS}', 36: '~{RESET}',
            47: '~{AS}', 49: '~{BERR}', 51: '~{BG}', 53: '~{BGACK}', 55: '~{BR}', 57: '~{DTACK}', 59: 'RWB', 61: 'D0', 63: 'D1'})
bus.update({38 + 2 * i: f'D{15 - i}' for i in range(14)})
used = {'+5V', 'GND', '~{IOSEL}', '~{LDS}', '~{RESET}', '~{DTACK}', 'RWB', 'A1', 'A2', 'A3'} | {f'A{i}' for i in range(13, 20)} | {f'D{i}' for i in range(8)}
k = d.custom('BUS_2x32', [(i, bus[i], 'passive') for i in range(1, 65, 2)], [(i, bus[i], 'passive') for i in range(2, 65, 2)], FP_BUS, ref='J')
d.add('J1', k, 'SOLDERDEMON M68K BUS', {i: n if n in used else None for i, n in bus.items()}, (45, 105))

# ---- U1: address compare. /CARD low for LDS=0, IOSEL=0, A19..A13 = BASE ----
# /LDS (only ever asserted inside /AS) takes the eighth pair, so /CARD is already a data strobe:
# U2 needs only R/W as its second enable, which frees its third select input for A3.
k = d.standard('74xx', '74HCT688', DIP(20))
m = {'G': '~{IOSEL}', 'P=R': '~{CARD}', 'VCC': '+5V', 'GND': 'GND'}
for i, a in enumerate(range(13, 20)):
    m[f'P{i}'] = f'A{a}'; m[f'R{i}'] = '+5V' if BASE >> a & 1 else 'GND'
m['P7'] = '~{LDS}'; m['R7'] = 'GND'
d.add('U1', k, '74HCT688', named(k, m), (125, 55))

# ---- D2: /DTACK is open-drain on the SolderDemon m68k (decoder output enable only, R21 1k2 pull-up).
# The diode pulls it low for every byte cycle in the card window and blocks when /CARD is high.
k = d.standard('Device', 'D_Schottky', FP_D)
d.add('D2', k, 'BAT85', {1: '~{CARD}', 2: '~{DTACK}'}, (125, 105))

# ---- U2: write strobes, offset 1 + 2 * (A3 A2 A1). Active high: rising edge at the start of /LDS
PORTS = 'ABCD'
SLOT = {'A': 0, 'B': 1, 'DIR': 2, 'C': 3, 'D': 4}         # $F40001, $F40003, $F40005, $F40007, $F40009
k = d.standard('74xx', '74HCT238', DIP(16))
m = {'A0': 'A1', 'A1': 'A2', 'A2': 'A3', '~{E1}': '~{CARD}', '~{E2}': 'RWB', 'E3': '+5V', 'VCC': '+5V', 'GND': 'GND'}
m.update({f'Y{i}': None for i in range(8)}); m.update({f'Y{n}': f'WR_{r}' for r, n in SLOT.items()})
d.add('U2', k, '74HCT238', named(k, m), (125, 150))

# ---- U3: read enables (active low) ----------------------------------------------
k = d.standard('74xx', '74HCT138', DIP(16))
m = {'A0': 'A1', 'A1': 'A2', 'A2': 'A3', '~{E0}': '~{CARD}', '~{E1}': 'GND', 'E2': 'RWB', 'VCC': '+5V', 'GND': 'GND'}
m.update({f'~{{Y{i}}}': None for i in range(8)}); m.update({f'~{{Y{SLOT[p]}}}': f'~{{RD_{p}}}' for p in PORTS})
d.add('U3', k, '74HCT138', named(k, m), (125, 210))

# ---- U4: direction register. b0..b3 = ports A..D; 1 = output. Reset: /Q = 1 -> inputs
k = d.standard('74xx', '74LS175', DIP(16))
m = {'~{Mr}': '~{RESET}', 'Cp': 'WR_DIR', 'VCC': '+5V', 'GND': 'GND'}
for i, p in enumerate(PORTS):
    m[f'D{i}'] = f'D{i}'; m[f'Q{i}'] = None; m[f'~{{Q{i}}}'] = f'~{{OE_{p}}}'
d.add('U4', k, '74HCT175', named(k, m), (125, 270))

# ---- ports ------------------------------------------------------------------------
L574 = d.standard('74xx', '74HCT574', DIP(20))
L541 = d.standard('74xx', '74HCT541', DIP(20))
RN = d.standard('Device', 'R_Network08', FP_RN)
for i, p in enumerate(PORTS):
    y = 55 + 70 * i
    m = {'OE': f'~{{OE_{p}}}', 'Cp': f'WR_{p}', 'VCC': '+5V', 'GND': 'GND'}
    m.update({f'D{b}': f'D{b}' for b in range(8)}); m.update({f'Q{b}': f'P{p}{b}' for b in range(8)})
    d.add(f'U{5 + 2 * i}', L574, '74HCT574', named(L574, m), (205, y))
    m = {'G1': f'~{{RD_{p}}}', 'G2': 'GND', 'VCC': '+5V', 'GND': 'GND'}
    m.update({f'A{b}': f'P{p}{b}' for b in range(8)}); m.update({f'Y{b}': f'D{b}' for b in range(8)})
    d.add(f'U{6 + 2 * i}', L541, '74HCT541', named(L541, m), (285, y))
    d.add(f'RN{i + 1}', RN, '8x10k', {1: '+5V'} | {b + 2: f'P{p}{b}' for b in range(8)}, (345 + 25 * i, 250))

IDC = d.standard('Connector_Generic', 'Conn_02x10_Odd_Even', FP_IDC)
for jref, lo, hi, y, label in [('J2', 'A', 'B', 70, '16 GPIO 5V A/B'), ('J3', 'C', 'D', 160, '16 GPIO 5V C/D')]:
    d.add(jref, IDC, label, {b + 1: f'P{lo}{b}' for b in range(8)} | {b + 9: f'P{hi}{b}' for b in range(8)} | {17: 'GND', 18: '+5V', 19: 'GND', 20: 'GND'}, (385, y))

# ---- power ---------------------------------------------------------------------
C = d.standard('Device', 'C', FP_C); CP = d.standard('Device', 'C_Polarized', FP_CP); R = d.standard('Device', 'R', FP_R)
LED = d.standard('Device', 'LED', FP_LED); FLG = d.standard('power', 'PWR_FLAG', '')
for i in range(1, 13):                                                         # C1..C12 bypass U1..U12
    d.add(f'C{i}', C, '100nF', {1: '+5V', 2: 'GND'}, (45 + 19.05 * (i - 1), 340))
d.add('C13', CP, '47uF 10V', {1: '+5V', 2: 'GND'}, (45, 365))
d.add('R1', R, '1k', {1: '+5V', 2: 'LED_A'}, (70, 365))
d.add('D1', LED, 'LED 3mm', {2: 'LED_A', 1: 'GND'}, (95, 365))
d.add('#FLG01', FLG, 'PWR_FLAG', {1: '+5V'}, (125, 360))
d.add('#FLG02', FLG, 'PWR_FLAG', {1: 'GND'}, (145, 360))

d.note(f'Window ${BASE:06X}..${BASE + 0x1FFF:06X}, byte access (LDS) only; registers repeat every 16 bytes. D2 acknowledges every LDS cycle in the window.', 20, 385, 2)
d.note(f'${BASE + 1:06X} port A, ${BASE + 3:06X} port B, ${BASE + 7:06X} port C, ${BASE + 9:06X} port D: write = output latch, read = pin levels.', 20, 391, 2)
d.note(f'${BASE + 5:06X}: write direction b0..b3 = ports A..D (1 = output). System reset: all inputs. Latches are random until written.', 20, 397, 2)

d.write(ROOT, [(NAME, '${KIPRJMOD}/' + NAME + '.pretty')])

# Local bus socket with the off-card silkscreen trimmed (separate process, see make_bus_footprint.py).
subprocess.run([sys.executable, str(Path(__file__).with_name('make_bus_footprint.py'))], check=True)
if '--schematic-only' in sys.argv:
    print('Generated schematic, symbols, BOM; existing routed PCB preserved')
    sys.exit(0)

# ---- PCB -----------------------------------------------------------------------
b = pcb.BOARD(); b.SetCopperLayerCount(2)
v = lambda x, y: pcb.VECTOR2I(pcb.FromMM(x), pcb.FromMM(y))
nets = {}
for i, n in enumerate(sorted(d.netlist()), 1):
    ni = pcb.NETINFO_ITEM(b, '/' + n, i); b.Add(ni); nets[n] = ni
fps = {}
for p in d.parts:
    if p['ref'].startswith('#'): continue
    lib, name = p['fp'].split(':')
    f = pcb.FootprintLoad(str(LOCAL_FP if lib == NAME else g.LIB / 'footprints' / (lib + '.pretty')), name); assert f, p['fp']
    f.SetFPID(pcb.LIB_ID(lib, name))
    f.SetReference(p['ref']); f.SetValue(p['value']); f.SetPath(pcb.KIID_PATH('/' + d.uid('root') + '/' + p['uuid']))
    for pad in f.Pads():
        net = p['nets'].get(pad.GetNumber())
        if net: pad.SetNet(nets[net])
    f.Value().SetVisible(False)
    f.Reference().SetTextSize(v(1, 1)); f.Reference().SetTextThickness(pcb.FromMM(.15))
    b.Add(f); fps[p['ref']] = f


def place(ref, x, y, rot=0, pin1=False):
    """pin1=True: (x, y) is pad 1; otherwise the footprint body is centred on (x, y)."""
    f = fps[ref]; f.SetOrientationDegrees(rot); f.SetPosition(v(0, 0))
    if pin1:
        f.SetPosition(v(x, y)); return f
    c = f.GetBoundingBox(False).GetCenter()
    f.SetPosition(pcb.VECTOR2I(pcb.FromMM(x) - c.x, pcb.FromMM(y) - c.y))
    return f


def ref_at(ref, x, y, angle=0):
    t = fps[ref].Reference(); t.SetPosition(v(x, y)); t.SetTextAngle(pcb.EDA_ANGLE(angle, pcb.DEGREES_T))


def column(rows, left, cap_x):
    """DIPs lying horizontally with pin 1 towards the bus, left edges aligned; bypass cap to the right of each."""
    for ref, cref, y in rows:
        f = place(ref, left + 13, y, 270)
        f.Move(pcb.VECTOR2I(pcb.FromMM(left) - f.GetBoundingBox(False).GetLeft(), 0))
        ref_at(ref, left - 1.3, y, 90)
        place(cref, cap_x, y, 90); ref_at(cref, cap_x - 2.8, y, 90)


# J1 rotated so the socket body overhangs the right edge; pin 1 at the bottom.
BX = W - 6.0
place('J1', BX, 87.37, 180, pin1=True); ref_at('J1', BX + 1.27, 91.2)
# Three columns on one grid of four rows, symmetric about the board centre line (H/2):
# ports A (left) and B (middle) above it, C and D below; latch above read-back.
# Right column: decode and direction register. The band on the centre line holds the logo
# (left and middle columns) and the DTACK diode and power parts (right column).
MID = H / 2
ROW = (MID - 34.0, MID - 16.0, MID + 16.0, MID + 34.0)
column([('U5', 'C5', ROW[0]), ('U6', 'C6', ROW[1]), ('U9', 'C9', ROW[2]), ('U10', 'C10', ROW[3])], 37.0, 67.0)
column([('U7', 'C7', ROW[0]), ('U8', 'C8', ROW[1]), ('U11', 'C11', ROW[2]), ('U12', 'C12', ROW[3])], 74.0, 104.0)
column([('U1', 'C1', ROW[0]), ('U2', 'C2', ROW[1]), ('U3', 'C3', ROW[2]), ('U4', 'C4', ROW[3])], 111.0, 141.0)
RX = 126.5                                                           # centre of the right column
place('D2', RX, MID - 4.5, 0); ref_at('D2', RX, MID - 6.4)
place('C13', RX - 11.0, MID + 4.5, 0); ref_at('C13', RX - 11.0, MID + 0.1)
place('R1', RX + 0.5, MID + 4.5, 0); ref_at('R1', RX + 0.5, MID + 2.5)
place('D1', RX + 11.5, MID + 4.5, 0); ref_at('D1', RX + 11.5, MID + 1.3)
# Left edge: J2 (A/B) above J3 (C/D), cables exit left. The two
# connector bodies share a vertical centre at H/2; their pull-up pairs move
# with them. A body centre is 11.43 mm above pad 1 in this orientation.
CONNECTOR_SHIFT = H / 2 - ((40.0 + 86.0) / 2 - 11.43)
J_PIN1 = {'J2': 40.0 + CONNECTOR_SHIFT, 'J3': 86.0 + CONNECTOR_SHIFT}
for jref, (lo, hi) in {'J2': ('A', 'B'), 'J3': ('C', 'D')}.items():
    y1 = J_PIN1[jref]
    place(jref, 16.5, y1, 180, pin1=True); ref_at(jref, 9.5, y1 - 26.0)
for rn, x, y, ry in [('RN1', 28.0, 28.5, 14.8), ('RN2', 32.0, 28.5, 42.2), ('RN3', 28.0, 74.5, 60.8), ('RN4', 32.0, 74.5, 88.2)]:
    place(rn, x, y + CONNECTOR_SHIFT, 90); ref_at(rn, x, ry + CONNECTOR_SHIFT)


def seg(a, z, layer=pcb.F_SilkS, width=.15, shape=pcb.SHAPE_T_SEGMENT):
    e = pcb.PCB_SHAPE(b); e.SetShape(shape); e.SetStart(v(*a)); e.SetEnd(v(*z)); e.SetLayer(layer); e.SetWidth(pcb.FromMM(width)); b.Add(e)


def arc(start, mid, end):
    e = pcb.PCB_SHAPE(b); e.SetShape(pcb.SHAPE_T_ARC); e.SetArcGeometry(v(*start), v(*mid), v(*end))
    e.SetLayer(pcb.Edge_Cuts); e.SetWidth(pcb.FromMM(.05)); b.Add(e)


def text(s, x, y, size=1.0, layer=pcb.F_SilkS, left=True, angle=0, bold=False):
    t = pcb.PCB_TEXT(b); t.SetText(s); t.SetPosition(v(x, y)); t.SetTextSize(v(size, size))
    t.SetTextThickness(pcb.FromMM(size * (.2 if bold else .15))); t.SetLayer(layer)
    if left: t.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_LEFT)
    if angle: t.SetTextAngle(pcb.EDA_ANGLE(angle, pcb.DEGREES_T))
    if layer == pcb.B_SilkS: t.SetMirrored(True)
    b.Add(t)


# Board outline, 3 mm corner radius.
r = 3.0; k45 = r * (1 - 0.70710678)
seg((r, 0), (W - r, 0), pcb.Edge_Cuts, .05); seg((W, r), (W, H - r), pcb.Edge_Cuts, .05)
seg((W - r, H), (r, H), pcb.Edge_Cuts, .05); seg((0, H - r), (0, r), pcb.Edge_Cuts, .05)
arc((W - r, 0), (W - k45, k45), (W, r)); arc((W, H - r), (W - k45, H - k45), (W - r, H))
arc((r, H), (k45, H - k45), (0, H - r)); arc((0, r), (k45, k45), (r, 0))

for jref, (lo, hi) in {'J2': ('A', 'B'), 'J3': ('C', 'D')}.items():
    y1 = J_PIN1[jref]
    for row in range(10):
        names = f'{lo}{row * 2} {lo}{row * 2 + 1}' if row < 4 else f'{hi}{(row - 4) * 2} {hi}{(row - 4) * 2 + 1}' if row < 8 else 'GND 5V' if row == 8 else 'GND GND'
        text(names, 19.2, y1 - row * 2.54, .8)
# SolderDemon identity as on solderdemon_m68k-busboard: the pixel logo with the name beside it,
# centred in the band between the port A/B and C/D rows (left edge of U5 to C8).
LX, LOGO_W, GAP, NAME_W = (37.0 + 105.3) / 2, 16.9, 2.0, 21.0
x0 = LX - (LOGO_W + GAP + NAME_W) / 2
logo = pcb.FootprintLoad(str(LOCAL_FP), 'SolderDemon_Logo'); logo.SetFPID(pcb.LIB_ID(NAME, 'SolderDemon_Logo'))
logo.SetReference('LOGO1'); logo.SetPosition(v(x0 + LOGO_W / 2, MID)); b.Add(logo)
tx = x0 + LOGO_W + GAP
text('SolderDemon', tx, MID - 1.6, 2.0, bold=True)
text('GPIO Card', tx, MID + 1.6, 1.0)
text(f'r1   32 x 5V   ${BASE + 1:06X}', tx, MID + 3.6, .8)
text('BUS', BX + 1.27, 5, 1.0, left=False)
# Register map on the back, in the centre band behind the logo: one labelled line per register kind.
for i, line in enumerate(['GPIO REGISTERS (byte access only)',
                          f'PORT A ${BASE + 1:06X}   PORT B ${BASE + 3:06X}   PORT C ${BASE + 7:06X}   PORT D ${BASE + 9:06X}   write = outputs, read = pins',
                          f'DIRECTION ${BASE + 5:06X} (write only)   bit 0..3 = port A..D   1 = output   after reset: all inputs',
                          f'{NAME} r1 (September 2026)   Copyright ©2026 SolderDemon']):
    text(line, LX, MID - 2.7 + i * 1.8, .9, pcb.B_SilkS, left=False, bold=i == 0)   # mirrored text: left-justified runs off the left edge

# No-connect pins get 'unconnected-(...)' nets in the schematic; copy nets and pin metadata onto the pads.
netlist = ROOT / 'netlist.xml'
subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(netlist), str(ROOT / f'{NAME}.kicad_sch')], check=True, capture_output=True)
for n in ET.parse(netlist).findall('./nets/net'):
    for node in n.findall('node'):
        f = fps.get(node.get('ref'))
        pad = next((pd for pd in f.Pads() if pd.GetNumber() == node.get('pin')), None) if f else None
        if pad is None: continue
        ni = b.FindNet(n.get('name'))
        if ni is None:
            ni = pcb.NETINFO_ITEM(b, n.get('name')); b.Add(ni)
        pad.SetNet(ni)
        if node.get('pinfunction'): pad.SetPinFunction(node.get('pinfunction'))
        if node.get('pintype'): pad.SetPinType(node.get('pintype'))
netlist.unlink()

# SaveBoard of a fresh BOARD rewrites the .kicad_pro without its ERC/schematic sections; keep the project file.
project = ROOT / (NAME + '.kicad_pro'); saved = project.read_bytes()
try:
    pcb.SaveBoard(str(ROOT / (NAME + '.kicad_pcb')), b)
finally:
    project.write_bytes(saved)
pcb.ExportSpecctraDSN(b, str(ROOT / 'routing.dsn'))
print('Generated', len(d.parts), 'symbols;', len(nets), 'nets;', f'{W:g} x {H:g} mm')
