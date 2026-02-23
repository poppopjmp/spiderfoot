"""Run batch 2 tests and capture all output to a file."""
import subprocess
import sys
import time

output_file = r'd:\github\spiderfoot\batch2_results.txt'
start = time.time()

proc = subprocess.run(
    [sys.executable, '-m', 'pytest',
     'test/unit/',
     '--ignore=test/unit/modules',
     '--ignore=test/unit/spiderfoot',
     '--tb=line', '-q', '-p', 'no:logging', '--no-header'],
    capture_output=True, text=True,
    cwd=r'D:\github\spiderfoot',
    timeout=1800
)

elapsed = time.time() - start

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(proc.stdout)
    if proc.stderr:
        f.write('\n--- STDERR ---\n')
        f.write(proc.stderr)

# Print summary
lines = proc.stdout.strip().split('\n')
print(f"Elapsed: {elapsed:.1f}s, exit code: {proc.returncode}")
print(f"Total output lines: {len(lines)}")
print("--- Last 30 lines ---")
for line in lines[-30:]:
    print(line)
