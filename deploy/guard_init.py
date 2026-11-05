"""Omit Android init writes to non-namespaced host sysctls in this image layer."""
from pathlib import Path
import re
import sys

pattern = re.compile(r'^\s*write\s+/proc/sys/(?:kernel|vm|fs)/')
count = 0
for directory in sys.argv[1:]:
    for path in Path(directory).rglob('*.rc'):
        lines = path.read_text().splitlines(keepends=True)
        output = []
        for line in lines:
            if pattern.match(line):
                output.append('# Container host sysctl retained: ' + line.lstrip())
                count += 1
            else:
                output.append(line)
        path.write_text(''.join(output))
if count == 0:
    raise SystemExit('No matching init writes found; review the upstream image before proceeding.')
print(f'Disabled {count} Android init writes to host-global sysctls.')
