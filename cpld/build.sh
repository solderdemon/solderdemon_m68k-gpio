#!/usr/bin/env bash
# Build the 5 V ATF1504AS firmware and check that the fitter kept the PCB pinout.
set -euo pipefail
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1
IMAGE=${CPLD_IMAGE:-dinoboards/cpld-toolchain:latest}
HOSTDIR=$(pwd -W 2>/dev/null || pwd)
docker run --rm -v "$HOSTDIR:/work" "$IMAGE" cupld gpio_u1
python - <<'PY'
import re
from pathlib import Path

src = re.sub(r'/\*.*?\*/', '', Path('gpio_u1.pld').read_text(), flags=re.S)
want = {}
for numbers, names in re.findall(r'PIN\s+(\[[^;]+?\]|\d+)\s*=\s*(\[[^;]+?\]|\w+)\s*;', src, re.I):
    nums = [int(n) for n in numbers.strip('[]').split(',')]
    names = names.strip('[]')
    m = re.fullmatch(r'([A-Za-z_]+)(\d+)\.\.(\d+)', names)
    labels = [f'{m[1]}{i}' for i in range(int(m[2]), int(m[3]) + 1)] if m else [names]
    assert len(nums) == len(labels)
    want.update(zip(labels, nums))
fit = Path('bin/gpio_u1.fit').read_text(encoding='latin-1')
got = {s: int(n) for s, n in re.findall(r'^(\w+) is placed at pin (\d+)', fit, re.M)}
got.update({s: int(n) for s, n in re.findall(r'^(\w+) assigned to pin\s+(\d+)', fit, re.M)})
bad = {s: (n, got.get(s)) for s, n in want.items() if got.get(s) != n}
assert not bad, f'fitter moved pins: {bad}'
assert Path('bin/gpio_u1.jed').exists(), 'no JEDEC output'
print(f'gpio_u1: {len(want)} pins kept; JEDEC ready')
PY
