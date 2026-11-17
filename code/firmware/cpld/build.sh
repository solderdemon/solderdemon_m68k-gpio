#!/usr/bin/env bash
# Build three 5 V PLCC-44 ATF1502AS images and verify fitted pin assignments.
set -euo pipefail
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1
IMAGE=${CPLD_IMAGE:-dinoboards/cpld-toolchain:latest}
HOSTDIR=$(pwd -W 2>/dev/null || pwd)
for f in gpio_decode gpio_ab gpio_cd; do
rm -f "bin/$f.jed" "bin/$f.fit"
docker run --rm -v "$HOSTDIR:/work" "$IMAGE" cupld "$f"
python - "$f" <<'PY'
import re
import sys
from pathlib import Path

name = sys.argv[1]
src = re.sub(r'/\*.*?\*/', '', Path(name + '.pld').read_text(), flags=re.S)
want = {}
for numbers, names in re.findall(r'PIN\s+(\[[^;]+?\]|\d+)\s*=\s*(\[[^;]+?\]|\w+)\s*;', src, re.I):
    nums = [int(n) for n in numbers.strip('[]').split(',')]
    names = names.strip('[]')
    m = re.fullmatch(r'([A-Za-z_]+)(\d+)\.\.(\d+)', names)
    labels = [f'{m[1]}{i}' for i in range(int(m[2]), int(m[3]) + 1)] if m else [names]
    assert len(nums) == len(labels)
    want.update(zip(labels, nums))
fit = Path('bin/' + name + '.fit').read_text(encoding='latin-1')
got = {s: int(n) for s, n in re.findall(r'^(\w+) is placed at pin (\d+)', fit, re.M)}
got.update({s: int(n) for s, n in re.findall(r'^(\w+) assigned to pin\s+(\d+)', fit, re.M)})
bad = {s: (n, got.get(s)) for s, n in want.items() if got.get(s) != n}
assert not bad, f'fitter moved pins: {bad}'
assert Path('bin/' + name + '.jed').exists(), 'no JEDEC output'
print(f'{name}: {len(want)} pins kept; JEDEC ready')
PY
done
