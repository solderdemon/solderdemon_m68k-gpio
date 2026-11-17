"""Write solderdemon_m68k-gpio.pretty/PinSocket_2x32_P2.54mm_Horizontal_CardEdge: the stock KiCad
right-angle 2x32 socket with the silkscreen that would lie beyond the card edge removed.

Runs as its own process: removing footprint items breaks pcbnew's SWIG type table for the
rest of the interpreter, so build_card.py must not do this in-process.
"""
from pathlib import Path
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[1]
KICAD_LIB = Path('/usr/share/kicad') if Path('/usr/share/kicad').exists() else Path('C:/Program Files/KiCad/10.0/share/kicad')
LIB = ROOT / 'design' / 'solderdemon_m68k-gpio.pretty'
NAME = 'PinSocket_2x32_P2.54mm_Horizontal_CardEdge'
EDGE_LOCAL_X = -5.5   # J1 is placed rotated 180 deg with pin 1 at x=110 on a 116 mm card

io = pcb.PCB_IO_MGR.FindPlugin(pcb.PCB_IO_MGR.KICAD_SEXP)
fp = io.FootprintLoad(str(KICAD_LIB / 'footprints/Connector_PinSocket_2.54mm.pretty'), 'PinSocket_2x32_P2.54mm_Horizontal')
fp.SetFPID(pcb.LIB_ID(LIB.stem, NAME))
fp.SetLibDescription('2x32 2.54 mm right-angle socket for SolderDemon m68k (rosco_m68k compatible) cards; silkscreen stops at the card edge')
doomed = [item for item in fp.GraphicalItems()
          if item.GetLayer() == pcb.F_SilkS and pcb.ToMM(item.GetBoundingBox().GetLeft()) < EDGE_LOCAL_X]
LIB.mkdir(exist_ok=True)
for item in doomed:
    fp.Remove(item)
io.FootprintSave(str(LIB), fp)
print(f'{NAME}: removed {len(doomed)} silkscreen items')
