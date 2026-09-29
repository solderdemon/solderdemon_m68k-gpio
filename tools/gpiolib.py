"""Schematic generator for the SolderDemon m68k GPIO card.

Every part is placed on one sheet; each pin gets a short wire stub and a local
net label, so the netlist is defined entirely by the `nets` dictionaries in
build_card.py.  Standard KiCad library symbols are copied into the schematic
(with `extends` resolved); parts KiCad does not ship are built as box symbols
with explicit pin numbers.
"""
from pathlib import Path
import re, uuid, json, csv, copy

ROOT = Path(__file__).resolve().parents[1]
LIB = Path('/usr/share/kicad')

def q(s): return json.dumps(str(s), ensure_ascii=False)

class S(str):
    """A token that was quoted in the source file and must be quoted again on output."""

def parse(s):
    toks = re.findall(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()]+', s); stack = []; root = []; cur = root
    for t in toks:
        if t == '(': n = []; cur.append(n); stack.append(cur); cur = n
        elif t == ')': cur = stack.pop()
        else: cur.append(S(json.loads(t)) if t.startswith('"') else t)
    return root[0]

def sub(a, k): return [x for x in a if isinstance(x, list) and x and x[0] == k]
def one(a, k): return next(x for x in a if isinstance(x, list) and x and x[0] == k)

def dump(a):
    if isinstance(a, list):
        tag = a[0]; out = [tag]
        for i, x in enumerate(a[1:], 1):
            if isinstance(x, list): out.append(dump(x))
            elif isinstance(x, S) or (tag in ('symbol', 'name', 'number') and i == 1) or (tag == 'property' and i <= 2): out.append(q(x))
            else: out.append(str(x))
        return '(' + ' '.join(out) + ')'
    return str(a)

_libcache = {}
def _libsymbols(lib):
    if lib not in _libcache:
        _libcache[lib] = parse((LIB / 'symbols' / f'{lib}.kicad_sym').read_text(encoding='utf-8'))
    return _libcache[lib]

def library_symbol(lib, name):
    """Return a deep copy of a library symbol with any `extends` resolved."""
    a = _libsymbols(lib)
    s = copy.deepcopy(next(x for x in sub(a, 'symbol') if x[1] == name))
    ext = sub(s, 'extends')
    if ext:
        parent = library_symbol(lib, ext[0][1]); pname = ext[0][1]
        # Child keeps its own properties; graphics and pins come from the parent.
        props = {p[1]: p for p in sub(s, 'property')}
        merged = [x for x in parent if not (isinstance(x, list) and x and x[0] == 'property')]
        for p in sub(parent, 'property'):
            merged.append(props.get(p[1], p))
        for u in sub(merged, 'symbol'):
            u[1] = name + u[1][len(pname):]
        s = merged
    return s

class Design:
    def __init__(self, name, title, rev, date, paper='A2', libname='solderdemon_m68k-gpio', ns='solderdemon-gpio/'):
        self.name, self.title, self.rev, self.date, self.paper, self.libname, self.ns = name, title, rev, date, paper, libname, ns
        self.symbols = {}; self.parts = []; self.notes = []; self.footprints = {}
    def uid(self, s): return str(uuid.uuid5(uuid.NAMESPACE_URL, self.ns + self.name + '/' + s))
    def standard(self, lib, name, fp):
        key = f'{lib}:{name}'
        if key not in self.symbols:
            s = library_symbol(lib, name); s[1] = key   # embedded copy stays identical to the library; footprints live on instances
            self.symbols[key] = s
        self.footprints[key] = fp
        return key
    def custom(self, name, left, right, fp, width=25.4, ref='U'):
        """Box symbol.  left/right: lists of (number, label, electrical type).  A label of None leaves a gap."""
        key = f'{self.libname}:{name}'
        if key in self.symbols: return key
        h = (max(len(left), len(right)) + 1) * 2.54 / 2; w = width / 2
        s = ['symbol', key, ['pin_names', ['offset', '0.8']], ['in_bom', 'yes'], ['on_board', 'yes'],
             ['property', 'Reference', ref, ['at', '0', str(h + 3), '0'], ['effects', ['font', ['size', '1.27', '1.27']]]],
             ['property', 'Value', name, ['at', '0', str(h + 6), '0'], ['effects', ['font', ['size', '1.27', '1.27']]]],
             ['property', 'Footprint', fp, ['at', '0', '0', '0'], ['effects', ['font', ['size', '1.27', '1.27']], ['hide', 'yes']]]]
        s.append(['symbol', name + '_0_1', ['rectangle', ['start', str(-w), str(h)], ['end', str(w), str(-h)], ['stroke', ['width', '0.254'], ['type', 'default']], ['fill', ['type', 'background']]]])
        pins = ['symbol', name + '_1_1']
        for side, arr in ((-1, left), (1, right)):
            for i, item in enumerate(arr):
                if item is None: continue
                num, label, typ = item
                pins.append(['pin', typ, 'line', ['at', str(side * (w + 2.54)), str(h - 2.54 * (i + 1)), str(0 if side == -1 else 180)], ['length', '2.54'],
                             ['name', label, ['effects', ['font', ['size', '1', '1']]]], ['number', str(num), ['effects', ['font', ['size', '1', '1']]]]])
        s.append(pins); self.symbols[key] = s; self.footprints[key] = fp
        return key
    def add(self, ref, key, value, nets, xy, pcb=None, rot=0, fp=None):
        """nets: {pin number: net name or None (= no-connect)}.  Pins absent from `nets` raise later."""
        fp = fp or self.footprints[key]
        xy = (round(xy[0] / 1.27) * 1.27, round(xy[1] / 1.27) * 1.27)   # keep every pin on the 1.27 mm connection grid
        p = dict(ref=ref, key=key, value=value, nets={str(k): v for k, v in nets.items()}, xy=xy, pos=pcb or (0, 0), rot=rot, fp=fp, uuid=self.uid(ref))
        assert not any(x['ref'] == ref for x in self.parts), ref
        self.parts.append(p); return p
    def note(self, text, x, y, size=1.27): self.notes.append((text, x, y, size))
    def _pins(self, key):
        s = self.symbols[key]
        return [pin for ss in sub(s, 'symbol') for pin in sub(ss, 'pin')]
    def _check_overlaps(self, stubs):
        """A stub end lying on another stub (or its end) would silently merge nets in KiCad."""
        def on_segment(pt, a, b):
            (x, y), (x1, y1), (x2, y2) = pt, a, b
            return min(x1, x2) - 1e-3 <= x <= max(x1, x2) + 1e-3 and min(y1, y2) - 1e-3 <= y <= max(y1, y2) + 1e-3 and abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) < 1e-3
        for ref, num, net, a, b in stubs:
            for ref2, num2, net2, a2, b2 in stubs:
                if (ref, num) == (ref2, num2) or net == net2: continue
                for pt in (a, b):
                    assert not on_segment(pt, a2, b2), f'schematic overlap: {ref}.{num} ({net}) touches {ref2}.{num2} ({net2}) at {pt}'
    def netlist(self):
        """Return {net: [(ref, pin)]} from the part definitions (independent of KiCad)."""
        nets = {}
        for p in self.parts:
            for pin, net in p['nets'].items():
                if net: nets.setdefault(net, []).append((p['ref'], pin))
        return nets
    def write(self, outdir, fp_libs):
        out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
        els = []; stubs = []
        for p in self.parts:
            x, y = p['xy']; pins = self._pins(p['key'])
            numbers = {one(pin, 'number')[1] for pin in pins}
            missing = numbers - set(p['nets']); extra = set(p['nets']) - numbers
            assert not missing and not extra, (p['ref'], 'missing', missing, 'extra', extra)
            top = max((float(one(pin, 'at')[2]) for pin in pins), default=0)
            e = [f'(symbol (lib_id {q(p["key"])}) (at {x} {y} {p["rot"]}) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {p["uuid"]})']
            for name, val, dy, hidden in (('Reference', p['ref'], -top - 12.7, False), ('Value', p['value'], -top - 10.16, False), ('Footprint', p['fp'], 0, True)):
                px, py = x, y + dy
                if p['ref'][0] in 'RCLDQY' and name in ('Reference', 'Value'):
                    px = x + 6.35; py = y + (-1.27 if name == 'Reference' else 1.27)
                e.append(f'(property {q(name)} {q(val)} (at {px} {py} 0) (effects (font (size 1.27 1.27))' + (' (hide yes)' if hidden else '') + '))')
            e.append(f'(instances (project {q(self.name)} (path "/{self.uid("root")}" (reference {q(p["ref"])}) (unit 1)))))')
            els.append(''.join(e))
            assert p['rot'] == 0, 'rotated placement not supported by the stub generator'
            for pin in pins:
                num = one(pin, 'number')[1]; at = one(pin, 'at')
                px = round(x + float(at[1]), 4); py = round(y - float(at[2]), 4); ang = int(float(at[3])); net = p['nets'].get(num)
                if net is None:
                    els.append(f'(no_connect (at {px} {py}) (uuid {self.uid(p["ref"] + "nc" + num)}))'); continue
                dx, dy = {0: (-5.08, 0), 180: (5.08, 0), 90: (0, 5.08), 270: (0, -5.08)}[ang]; ex = round(px + dx, 4); ey = round(py + dy, 4)
                els.append(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid {self.uid(p["ref"] + "w" + num)}))')
                stubs.append((p['ref'], num, net, (px, py), (ex, ey)))
                just = 'right bottom' if ang == 0 else 'left bottom'
                els.append(f'(label {q(net)} (at {ex} {ey} 0) (effects (font (size 1 1)) (justify {just})) (uuid {self.uid(p["ref"] + "l" + num)}))')
        self._check_overlaps(stubs)
        for text, x, y, size in self.notes:
            els.append(f'(text {q(text)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left)) (uuid {self.uid("note" + text)}))')
        sch = (f'(kicad_sch (version 20250114) (generator "solderdemon_gpio") (uuid {self.uid("root")}) (paper {q(self.paper)}) '
               f'(title_block (title {q(self.title)}) (date {q(self.date)}) (rev {q(self.rev)})) (lib_symbols ' + ''.join(dump(s) for s in self.symbols.values()) + ')'
               + ''.join(els) + '(sheet_instances (path "/" (page "1"))))')
        (out / f'{self.name}.kicad_sch').write_text(sch, encoding='utf-8')
        # The KiCad project holds the authoritative DRC rules and net classes.
        project = out / f'{self.name}.kicad_pro'
        if not project.exists():
            project.write_text('{}\n')
        local = []
        for k, s in self.symbols.items():
            if k.startswith(self.libname + ':'):
                t = copy.deepcopy(s); t[1] = k.split(':', 1)[1]; local.append(t)
        (out / f'{self.libname}.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "solderdemon_gpio")' + ''.join(dump(s) for s in local) + ')', encoding='utf-8')
        (out / 'sym-lib-table').write_text(f'(sym_lib_table (lib (name {q(self.libname)}) (type "KiCad") (uri "${{KIPRJMOD}}/{self.libname}.kicad_sym") (options "") (descr "Card symbols")))')
        (out / 'fp-lib-table').write_text('(fp_lib_table ' + ''.join(f'(lib (name {q(n)}) (type "KiCad") (uri {q(u)}) (options "") (descr ""))' for n, u in fp_libs) + ')')
        (out / 'design.json').write_text(json.dumps(self.parts, indent=1) + '\n')
        with (out / 'BOM.csv').open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f); w.writerow(['Reference', 'Value', 'Footprint'])
            w.writerows((p['ref'], p['value'], p['fp']) for p in self.parts if not p['ref'].startswith('#'))
        return len(self.parts), len(self.netlist())
