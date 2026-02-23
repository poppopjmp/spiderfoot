"""Run batch 2 tests - output goes directly to a file."""
import subprocess
import sys
import time
import os

output_file = r'd:\github\spiderfoot\batch2_results.txt'
start = time.time()

with open(output_file, 'w', encoding='utf-8') as f:
    proc = subprocess.Popen(
        [sys.executable, '-m', 'pytest',
         'test/unit/',
         '--ignore=test/unit/modules',
         '--ignore=test/unit/spiderfoot',
         '--tb=line', '-q', '-p', 'no:logging', '--no-header',
         '-W', 'ignore'],
        stdout=f, stderr=subprocess.STDOUT,
        cwd=r'D:\github\spiderfoot'
    )
    retcode = proc.wait()

elapsed = time.time() - start
# Now read the file and print summary
with open(output_file, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()
lines = content.strip().split('\n')
print(f"Elapsed: {elapsed:.1f}s, exit code: {retcode}")
print(f"Total output lines: {len(lines)}")
print("--- Last 30 lines ---")
for line in lines[-30:]:
    print(line)
