"""SolderDemon m68k GPIO r2: 5 V ATF1504AS schematic and PCB generator."""
from pathlib import Path
import re, subprocess, sys, xml.etree.ElementTree as ET
import gpiolib as g
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[1]
CLI = 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
g.LIB = Path('C:/Program Files/KiCad/10.0/share/kicad')
NAME = 'solderdemon_m68k-gpio'
BASE = 0xF40000
W, H = 105.0, 96.0

d = g.Design(NAME, 'SolderDemon m68k GPIO / 32 x 5V, ATF1504AS', 'r2', '2026-10-13', paper='A2', libname=NAME, ns='solderdemon-gpio-r2/')
FP_PLCC = 'Package_LCC:PLCC-84_THT-Socket'
FP_JTAG = 'Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical'
FP_C = 'Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm'
FP_CP = 'Capacitor_THT:CP_Radial_D6.3mm_P2.50mm'
FP_RN = 'Resistor_THT:R_Array_SIP9'
FP_D = 'Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal'
FP_BUS = NAME + ':PinSocket_2x32_P2.54mm_Horizontal_CardEdge'   # stock socket, silkscreen trimmed at the card edge
LOCAL_FP = ROOT / (NAME + '.pretty')
FP_GPIO = 'Connector_PinHeader_2.54mm:PinHeader_2x10_P2.54mm_Horizontal'

VCC_PINS = {3, 13, 26, 38, 43, 53, 66, 78}
GND_PINS = {7, 19, 32, 42, 47, 59, 72, 82}
JTAG_PINS = {14: 'TDI', 23: 'TMS', 62: 'TCK', 71: 'TDO'}
DEDICATED_PINS = {1, 2, 83, 84}


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

# ---- U1: one 5 V ATF1504AS implements decode, direction, latches and readback ----
# Pin assignments come from the CUPL source, so the PCB follows any fitter pin changes.
src = (ROOT / 'cpld' / 'gpio_u1.pld').read_text(encoding='utf-8')
src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
pins = {}
for numbers, names in re.findall(r'PIN\s+(\[[^;]+?\]|\d+)\s*=\s*(\[[^;]+?\]|[A-Za-z_]\w*)\s*;', src, re.I):
    nums = [int(n) for n in numbers.strip('[]').split(',')]
    names = names.strip('[]')
    m = re.fullmatch(r'([A-Za-z_]+)(\d+)\.\.(\d+)', names)
    labels = [f'{m.group(1)}{i}' for i in range(int(m.group(2)), int(m.group(3)) + 1)] if m else [names]
    assert len(nums) == len(labels), (numbers, names)
    for num, label in zip(nums, labels):
        assert num not in pins, num
        pins[num] = label
assert not set(pins) & (VCC_PINS | GND_PINS | set(JTAG_PINS))
assert set(DEDICATED_PINS) <= set(pins)

def cpld_pin(p):
    if p in VCC_PINS: return (p, 'VCC', 'power_in')
    if p in GND_PINS: return (p, 'GND', 'power_in')
    if p in JTAG_PINS: return (p, JTAG_PINS[p], 'bidirectional')
    n = pins.get(p)
    if n is None: return (p, f'NC{p}', 'no_connect')
    if p in DEDICATED_PINS or n.startswith('A'): return (p, n, 'input')
    return (p, n, 'tri_state' if n.startswith(('P', 'D')) else 'output')

k = d.custom('ATF1504AS_GPIO', [cpld_pin(p) for p in range(1, 43)],
             [cpld_pin(p) for p in range(84, 42, -1)], FP_PLCC, width=58.42)
special = {'RESET_N': '~{RESET}', 'IOSEL_N': '~{IOSEL}', 'LDS_N': '~{LDS}',
           'RW': 'RWB', 'CARD_N': '~{CARD}'}
cnets = {}
for p in range(1, 85):
    if p in VCC_PINS: cnets[p] = '+5V'
    elif p in GND_PINS: cnets[p] = 'GND'
    elif p in JTAG_PINS: cnets[p] = 'JTAG_' + JTAG_PINS[p]
    else:
        n = pins.get(p)
        cnets[p] = special.get(n, n) if n else None
d.add('U1', k, 'ATF1504AS-10JU84', cnets, (130, 150))

# D2 preserves the bus's diode-isolated active-low DTACK.
k = d.standard('Device', 'D_Schottky', FP_D)
d.add('D2', k, 'BAT85', {1: '~{CARD}', 2: '~{DTACK}'}, (125, 210))

# Atmel 10-pin JTAG header, powered only by the bus 5 V rail.
k = d.standard('Connector_Generic', 'Conn_02x05_Odd_Even', FP_JTAG)
d.add('J4', k, 'JTAG 5V', {1: 'JTAG_TCK', 2: 'GND', 3: 'JTAG_TDO', 4: '+5V',
                          5: 'JTAG_TMS', 6: None, 7: None, 8: None,
                          9: 'JTAG_TDI', 10: 'GND'}, (255, 175))

PORTS = 'ABCD'
RN = d.standard('Device', 'R_Network08', FP_RN)
for i, p in enumerate(PORTS):
    d.add(f'RN{i + 1}', RN, '8x10k',
          {1: '+5V'} | {b + 2: f'P{p}{b}' for b in range(8)}, (340 + 25 * i, 250))

GPIO = d.standard('Connector_Generic', 'Conn_02x10_Odd_Even', FP_GPIO)
for ref, lo, hi, y in [('J2', 'A', 'B', 70), ('J3', 'C', 'D', 160)]:
    gpio_pins = {bit + 1: f'P{lo}{bit}' for bit in range(8)}
    gpio_pins.update({bit + 9: f'P{hi}{bit}' for bit in range(8)})
    gpio_pins.update({17: 'GND', 18: '+5V', 19: 'GND', 20: 'GND'})
    d.add(ref, GPIO, f'16 GPIO 5V {lo}/{hi}', gpio_pins, (385, y))

# ---- power ---------------------------------------------------------------------
C = d.standard('Device', 'C', FP_C); CP = d.standard('Device', 'C_Polarized', FP_CP)
FLG = d.standard('power', 'PWR_FLAG', '')
for i in range(1, 9):                                                          # eight CPLD supply pairs
    d.add(f'C{i}', C, '100nF', {1: '+5V', 2: 'GND'}, (45 + 19.05 * (i - 1), 340))
d.add('C9', CP, '47uF 10V', {1: '+5V', 2: 'GND'}, (45, 365))
d.add('#FLG01', FLG, 'PWR_FLAG', {1: '+5V'}, (125, 360))
d.add('#FLG02', FLG, 'PWR_FLAG', {1: 'GND'}, (145, 360))

d.note(f'Window ${BASE:06X}..${BASE + 0x1FFF:06X}, byte access (LDS) only; registers repeat every 16 bytes. D2 acknowledges every LDS cycle in the window.', 20, 385, 2)
d.note(f'${BASE + 1:06X} port A, ${BASE + 3:06X} port B, ${BASE + 7:06X} port C, ${BASE + 9:06X} port D: write = output latch, read = pin levels.', 20, 391, 2)
d.note(f'${BASE + 5:06X}: write direction b0..b3 = ports A..D (1 = output). System reset: all inputs. Latches are random until written.', 20, 397, 2)

d.write(ROOT, [(NAME, '${KIPRJMOD}/' + NAME + '.pretty')])
subprocess.run([sys.executable, str(Path(__file__).with_name('build_docs.py'))], check=True)

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


# J1 retains its bus mating position on the right edge.
BX = W - 6.0
place('J1', BX, 87.37, 180, pin1=True); ref_at('J1', BX + 1.27, 91.2)
MID = H / 2
place('U1', 65.0, MID, 0); ref_at('U1', 65.0, MID + 19.0)
place('J4', 47.0, 10.0, 0); ref_at('J4', 55.0, 9.0)
place('D2', 52.0, 80.0, 0); ref_at('D2', 52.0, 75.0)
place('C9', 74.0, 80.0, 0); ref_at('C9', 74.0, 75.0)
# Bypass parts surround U1 and remain close to the 84-pin socket.
for i, (x, y) in enumerate([(45, 25), (55, 25), (75, 25), (86, 25),
                             (45, 70), (55, 70), (75, 70), (86, 70)], 1):
    place(f'C{i}', x, y, 90); ref_at(f'C{i}', x, y - 4.5)

# Keep the established two-header topology at the left edge.
CONNECTOR_SHIFT = H / 2 - ((40.0 + 86.0) / 2 - 11.43)
J_PIN1 = {'J2': 40.0 + CONNECTOR_SHIFT, 'J3': 86.0 + CONNECTOR_SHIFT}
for jref in ('J2', 'J3'):
    y1 = J_PIN1[jref]
    place(jref, 16.5, y1, 180, pin1=True); ref_at(jref, 10.0, y1 - 26.0)
# Four pull-up networks stay in one vertical column.
for i in range(4):
    rn, y = f'RN{i + 1}', 12.35 + 23.75 * i
    place(rn, 28.0, y, 90); ref_at(rn, 32.2, y, 90)


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
        if row < 4:
            names = f'{lo}{row * 2} {lo}{row * 2 + 1}'
        elif row < 8:
            names = f'{hi}{(row - 4) * 2} {hi}{(row - 4) * 2 + 1}'
        else:
            names = 'GND 5V' if row == 8 else 'GND GND'
        text(names, 20.5, y1 - row * 2.54, .8)
text('SolderDemon GPIO r2', 48.0, 91.0, 1.2, bold=True)
text('ATF1504AS  5V', 48.0, 93.0, .8)
text('BUS', BX + 1.27, 5, 1.0, left=False)

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
