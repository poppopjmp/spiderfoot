import subprocess, sys, time

start = time.time()
with open(r'd:\github\spiderfoot\test_output_final.txt', 'w', encoding='utf-8') as f:
    proc = subprocess.Popen(
        [sys.executable, '-m', 'pytest', 'test/unit/', '--ignore=test/unit/modules',
         '--tb=line', '-q', '-p', 'no:logging', '--no-header'],
        stdout=f, stderr=subprocess.STDOUT,
        cwd=r'D:\github\spiderfoot'
    )
    proc.wait()
elapsed = time.time() - start
print(f"Done in {elapsed:.1f}s, exit code: {proc.returncode}")
