"""Check the GPIO register contract directly against the three CUPL sources."""
from pathlib import Path
import cupl

root = Path(__file__).resolve().parents[1]
dev = {name: cupl.Device((root / 'cpld' / (name + '.pld')).read_text())
       for name in ('gpio_decode', 'gpio_ab', 'gpio_cd')}

# Exhaust the seven address bits, all eight slots and both bus directions.
dec = dev['gpio_decode']
base_bits = (0xF40000 >> 13) & 0x7F
slots = {0: 'A', 1: 'B', 2: 'DIR', 3: 'C', 4: 'D'}
for address in range(128):
    for slot in range(8):
        for rw in (0, 1):
            for ioselect in (0, 1):
                for lds in (0, 1):
                    p = {'IOSEL_N': ioselect, 'LDS_N': lds, 'RW': rw}
                    p.update({f'A{i}': address >> (i - 13) & 1 for i in range(13, 20)})
                    p.update({f'A{i}': slot >> (i - 1) & 1 for i in range(1, 4)})
                    out = dec.outputs(p, {})
                    selected = address == base_bits and not ioselect and not lds
                    assert out['CARD_N'] == (not selected)
                    for n, port in slots.items():
                        assert out['WR_' + port] == (selected and not rw and slot == n)
                        if port != 'DIR':
                            assert out['RD_' + port] == (selected and rw and slot == n)

for name, ports, direction_bits in [('gpio_ab', 'AB', (0, 1)),
                                     ('gpio_cd', 'CD', (2, 3))]:
    chip = dev[name]
    q = chip.reset_state()
    p = {n: 1 for n in chip.pins.values()}
    p.update({f'WR_{port}': 0 for port in ports})
    p.update({f'RD_{port}': 0 for port in ports})
    p['WR_DIR'] = 0
    p['RESET_N'] = 0
    out = chip.outputs(p, q)
    assert all(out[f'P{port}{i}'] is None for port in ports for i in range(8))
    p['RESET_N'] = 1

    # Direction changes do not alter the output latches; writes use each port's own strobe.
    for port in ports:
        for value in (0, 1, 0x55, 0xAA, 0xFF):
            p.update({f'D{i}': value >> i & 1 for i in range(8)})
            q = chip.clock_edge(p, q, {f'WR_{port}'})
            p.update({f'D{i}': int(i in direction_bits) for i in range(8)})
            q = chip.clock_edge(p, q, {'WR_DIR'})
            out = chip.outputs(p, q)
            assert [out[f'P{port}{i}'] for i in range(8)] == [value >> i & 1 for i in range(8)]

            # Return to input mode, then read externally driven pin levels.
            p.update({f'D{i}': 0 for i in range(8)})
            q = chip.clock_edge(p, q, {'WR_DIR'})
            assert all(chip.outputs(p, q)[f'P{port}{i}'] is None for i in range(8))
            p.update({f'P{port}{i}': (value ^ 0xA5) >> i & 1 for i in range(8)})
            p[f'RD_{port}'] = 1
            out = chip.outputs(p, q)
            assert [out[f'D{i}'] for i in range(8)] == [(value ^ 0xA5) >> i & 1 for i in range(8)]
            p[f'RD_{port}'] = 0
            assert all(chip.outputs(p, q)[f'D{i}'] is None for i in range(8))

    p['RESET_N'] = 0
    out = chip.outputs(p, q)
    assert all(out[f'P{port}{i}'] is None for port in ports for i in range(8))

print('CUPL simulation: address decode, port writes, direction reset and pin readback PASS')
