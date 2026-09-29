"""One pass: remove track stubs and vias that Freerouting leaves dangling, then refill the pours.
Run with KiCad 10 python; route_card.py calls it repeatedly until it prints 'removed: 0'.

One pass per process: removing board items breaks pcbnew's SWIG type table for the rest of the
interpreter (see make_bus_footprint.py). An item is removed only when it matches the DRC report
exactly — a track by net, a point on it and its reported length, a via by net and its centre —
so a healthy track passing through the same point is never touched.
"""
from pathlib import Path
import re, subprocess
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'solderdemon_m68k-gpio.kicad_pcb'
CLI = 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
RPT = ROOT / 'drc.rpt'

subprocess.run([CLI, 'pcb', 'drc', '-o', str(RPT), str(BOARD)], capture_output=True)
hits = re.findall(r'\[(?:track|via)_dangling\][^\n]*\n[^\n]*\n\s*@\(([-\d.]+) mm, ([-\d.]+) mm\): (Track|Via) \[([^\]]*)\][^\n]*?(?:length ([\d.]+) mm)?\n',
                  RPT.read_text(encoding='utf-8'))
doomed = {}                                      # SWIG items are unhashable; key by UUID
if hits:
    b = pcb.LoadBoard(str(BOARD))
    tracks = list(b.GetTracks())
    for x, y, kind, net, length in hits:
        p = pcb.VECTOR2I(pcb.FromMM(float(x)), pcb.FromMM(float(y)))
        for t in tracks:
            if t.GetNetname() != net: continue
            if kind == 'Via':
                ok = isinstance(t, pcb.PCB_VIA) and (t.GetPosition() - p).EuclideanNorm() < pcb.FromMM(.005)
            else:
                ok = (not isinstance(t, pcb.PCB_VIA) and length and t.HitTest(p, pcb.FromMM(.005))
                      and abs(pcb.ToMM(t.GetLength()) - float(length)) < .002)
            if ok:
                doomed[t.m_Uuid.AsString()] = t
    for t in doomed.values():
        b.Remove(t)
    if doomed:
        pcb.ZONE_FILLER(b).Fill(b.Zones()); pcb.SaveBoard(str(BOARD), b)
print('removed:', len(doomed), sorted({t.GetNetname() for t in doomed.values()}))
