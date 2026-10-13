"""Generate r1 README and build/assembly/design docs from tools/docs_templates."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = Path(__file__).with_name('docs_templates')
for name, target in [('README.md', root / 'README.md'),
                     ('BUILD.md', root / 'docs' / 'BUILD.md'),
                     ('DESIGN.md', root / 'docs' / 'DESIGN.md'),
                     ('BRINGUP.md', root / 'docs' / 'BRINGUP.md')]:
    target.write_bytes((src / name).read_bytes())
    print('Generated', target.relative_to(root))
