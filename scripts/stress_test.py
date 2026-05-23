import os
import time
import requests
import concurrent.futures
from collections import Counter

BASE_URL = os.environ.get("SF_TEST_API_URL", "http://localhost:3000")
USERNAME = os.environ.get("SF_TEST_USERNAME", "admin")
PASSWORD = os.environ.get("SF_TEST_PASSWORD", "admin")

CONCURRENCY = int(os.environ.get("STRESS_CONCURRENCY", 20))
TOTAL_SCANS = int(os.environ.get("STRESS_TOTAL_SCANS", 50))

def login():
    print(f"Logging into {BASE_URL}...")
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD})
    resp.raise_for_status()
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def run_single_scan(worker_id, headers):
    metrics = {
        "creation_time": 0,
        "completion_time": 0,
        "error": None,
        "status": "UNKNOWN"
    }
    
    start_time = time.time()
    scan_id = None
    
    try:
        # 1. Create scan
        payload = {
            "name": f"stress-test-{worker_id}-{int(time.time())}",
            "target": "spiderfoot.net",
            "modules": ["sfp_dnsresolve"]
        }
        resp = requests.post(f"{BASE_URL}/api/v1/scans", json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        scan_id = resp.json().get("id")
        metrics["creation_time"] = time.time() - start_time
        
        # 2. Poll until finished
        poll_start = time.time()
        while True:
            status_resp = requests.get(f"{BASE_URL}/api/v1/scans/{scan_id}", headers=headers, timeout=10)
            status_resp.raise_for_status()
            status = status_resp.json().get("status", "UNKNOWN")
            
            if status in ["FINISHED", "ERROR", "ABORTED"]:
                metrics["status"] = status
                metrics["completion_time"] = time.time() - poll_start
                break
                
            if time.time() - poll_start > 120:
                metrics["error"] = "Timeout polling for completion"
                metrics["status"] = "TIMEOUT"
                break
                
            time.sleep(2)
            
    except Exception as e:
        metrics["error"] = str(e)
        metrics["status"] = "HTTP_ERROR"
        
    return metrics

def main():
    try:
        headers = login()
    except Exception as e:
        print(f"Failed to login: {e}")
        return

    print(f"Starting stress test: {TOTAL_SCANS} total scans with {CONCURRENCY} concurrent workers.")
    
    overall_start = time.time()
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(run_single_scan, i, headers) for i in range(TOTAL_SCANS)]
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            res = future.result()
            results.append(res)
            if (i+1) % 5 == 0:
                print(f"Completed {i+1}/{TOTAL_SCANS} scans...")

    overall_time = time.time() - overall_start
    
    # Analyze metrics
    statuses = Counter([r["status"] for r in results])
    creation_times = [r["creation_time"] for r in results if r["creation_time"] > 0]
    completion_times = [r["completion_time"] for r in results if r["completion_time"] > 0]
    errors = [r["error"] for r in results if r["error"]]
    
    print("\n--- STRESS TEST RESULTS ---")
    print(f"Total Wall Time: {overall_time:.2f}s")
    print(f"Scan Throughput: {TOTAL_SCANS / overall_time:.2f} scans/sec")
    print(f"Statuses: {dict(statuses)}")
    
    if creation_times:
        print(f"Avg Creation Latency: {sum(creation_times)/len(creation_times):.3f}s")
        print(f"Max Creation Latency: {max(creation_times):.3f}s")
        
    if completion_times:
        print(f"Avg Completion Time: {sum(completion_times)/len(completion_times):.2f}s")
        print(f"Max Completion Time: {max(completion_times):.2f}s")
        
    if errors:
        print(f"Encountered {len(errors)} errors:")
        for err in set(errors):
            print(f"  - {err} ({errors.count(err)} times)")

if __name__ == "__main__":
    main()
