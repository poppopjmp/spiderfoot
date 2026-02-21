#!/usr/bin/env python3
"""
SpiderFoot Local Microservice Launcher

Runs SpiderFoot in microservice mode on your local machine without Docker.
Starts each service as a separate process:

  1. FastAPI REST API  (port 8001) — data layer, scan management
  2. CherryPy WebUI   (port 5001) — web interface (proxies through API)

Usage:
    python scripts/run_microservices.py                      # API + WebUI
    python scripts/run_microservices.py --api-only            # API only
    python scripts/run_microservices.py --webui-only          # WebUI only (needs API running)
    python scripts/run_microservices.py --api-port 9001       # custom API port
    python scripts/run_microservices.py --webui-port 8080     # custom WebUI port

The WebUI runs with SF_WEBUI_API_MODE=true, routing all data access
through the FastAPI REST API instead of direct database access.
This is the same architecture used in the Docker Compose microservice
deployment (docker-compose-microservices.yml).
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error

# Ensure project root is on the Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ── ANSI colours for terminal output ──────────────────────────────────
class C:
    HEADER  = "\033[95m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BOLD    = "\033[1m"
    RESET   = "\033[0m"


def banner():
    print(f"""
{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════╗
║       SpiderFoot — Local Microservice Mode               ║
╚══════════════════════════════════════════════════════════╝{C.RESET}
""")


def wait_for_service(name: str, url: str, timeout: int = 30) -> bool:
    """Poll a URL until it returns 200 or timeout expires."""
    print(f"  {C.YELLOW}⏳ Waiting for {name} at {url} ...{C.RESET}", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            resp = urllib.request.urlopen(req, timeout=3)
            if resp.status < 500:
                print(f" {C.GREEN}✓ ready{C.RESET}")
                return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(1)
        print(".", end="", flush=True)
    print(f" {C.RED}✗ timeout{C.RESET}")
    return False


def start_api(host: str, port: int, log_level: str) -> subprocess.Popen:
    """Start the FastAPI REST API server as a subprocess."""
    env = os.environ.copy()
    env.update({
        "SF_SERVICE": "api",
        "SF_API_HOST": host,
        "SF_API_PORT": str(port),
        "SF_API_WORKERS": "1",
        "SF_LOG_LEVEL": log_level,
        # Use local PostgreSQL database by default
        "SF_DEPLOYMENT_MODE": "microservice",
        "SF_SERVICE_ROLE": "api",
    })

    cmd = [
        sys.executable, "-m", "spiderfoot.service_runner",
        "--service", "api",
        "--port", str(port),
        "--log-level", log_level,
    ]

    print(f"  {C.BLUE}▶ Starting API server on {host}:{port}{C.RESET}")
    proc = subprocess.Popen(
        cmd,
        env=env,
        cwd=PROJECT_ROOT,
        # Let output go to the same terminal
        stdout=None,
        stderr=None,
    )
    return proc


def start_webui(host: str, port: int, api_url: str, log_level: str) -> subprocess.Popen:
    """Start the CherryPy WebUI server as a subprocess in API proxy mode."""
    env = os.environ.copy()
    env.update({
        "SF_SERVICE": "webui",
        "SF_WEB_HOST": host,
        "SF_WEB_PORT": str(port),
        "SF_LOG_LEVEL": log_level,
        # ── API proxy mode ──
        "SF_WEBUI_API_MODE": "true",
        "SF_WEBUI_API_URL": api_url,
        "SF_WEBUI_API_KEY": os.environ.get("SF_API_KEY", ""),
        "SF_DEPLOYMENT_MODE": "microservice",
        "SF_SERVICE_ROLE": "webui",
    })

    cmd = [
        sys.executable, "-m", "spiderfoot.service_runner",
        "--service", "webui",
        "--port", str(port),
        "--log-level", log_level,
    ]

    print(f"  {C.BLUE}▶ Starting WebUI on {host}:{port} (API proxy → {api_url}){C.RESET}")
    proc = subprocess.Popen(
        cmd,
        env=env,
        cwd=PROJECT_ROOT,
        stdout=None,
        stderr=None,
    )
    return proc


def main():
    parser = argparse.ArgumentParser(
        description="Run SpiderFoot locally in microservice mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          Start both API and WebUI
  %(prog)s --api-only               Start only the API server
  %(prog)s --webui-only             Start only the WebUI (API must be running)
  %(prog)s --api-port 9001          Use custom API port
  %(prog)s --debug                  Enable debug logging
        """,
    )
    parser.add_argument("--api-host", default="127.0.0.1", help="API bind host (default: 127.0.0.1)")
    parser.add_argument("--api-port", type=int, default=8001, help="API port (default: 8001)")
    parser.add_argument("--webui-host", default="127.0.0.1", help="WebUI bind host (default: 127.0.0.1)")
    parser.add_argument("--webui-port", type=int, default=5001, help="WebUI port (default: 5001)")
    parser.add_argument("--api-only", action="store_true", help="Start only the API server")
    parser.add_argument("--webui-only", action="store_true", help="Start only the WebUI")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--log-level", default=None, help="Log level (DEBUG|INFO|WARNING|ERROR)")
    parser.add_argument("--timeout", type=int, default=30, help="Startup health-check timeout (seconds)")
    args = parser.parse_args()

    log_level = args.log_level or ("DEBUG" if args.debug else "INFO")
    api_url = f"http://{args.api_host}:{args.api_port}/api"

    banner()

    processes: list[subprocess.Popen] = []
    api_proc = None
    webui_proc = None

    # ── Graceful shutdown handler ──
    def shutdown(signum=None, frame=None):
        sig_name = signal.Signals(signum).name if signum else "manual"
        print(f"\n{C.YELLOW}⏹  Shutting down ({sig_name})...{C.RESET}")
        for p in reversed(processes):
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
        print(f"{C.GREEN}✓ All services stopped.{C.RESET}")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, shutdown)

    try:
        # ── Start API ──
        if not args.webui_only:
            api_proc = start_api(args.api_host, args.api_port, log_level)
            processes.append(api_proc)

            # Wait for API to be healthy
            health_url = f"http://{args.api_host}:{args.api_port}/healthz"
            if not wait_for_service("API", health_url, timeout=args.timeout):
                # Try alternative health endpoints
                alt_urls = [
                    f"http://{args.api_host}:{args.api_port}/api/docs",
                    f"http://{args.api_host}:{args.api_port}/api/health",
                ]
                ready = False
                for alt in alt_urls:
                    if wait_for_service("API", alt, timeout=5):
                        ready = True
                        break
                if not ready:
                    print(f"{C.RED}✗ API server failed to start.{C.RESET}")
                    print(f"  Check the log output above for errors.")
                    shutdown()

        # ── Start WebUI ──
        if not args.api_only:
            webui_proc = start_webui(args.webui_host, args.webui_port, api_url, log_level)
            processes.append(webui_proc)

            # Wait for WebUI to be healthy
            webui_health = f"http://{args.webui_host}:{args.webui_port}"
            if not wait_for_service("WebUI", webui_health, timeout=args.timeout):
                print(f"{C.YELLOW}⚠ WebUI may still be starting...{C.RESET}")

        # ── Print summary ──
        print()
        print(f"{C.BOLD}{C.GREEN}{'═' * 58}")
        print(f"  SpiderFoot Microservice Mode — Running")
        print(f"{'═' * 58}{C.RESET}")
        if api_proc:
            print(f"  {C.CYAN}API Server:{C.RESET}   http://{args.api_host}:{args.api_port}")
            print(f"  {C.CYAN}API Docs:{C.RESET}     http://{args.api_host}:{args.api_port}/api/docs")
        if webui_proc:
            print(f"  {C.CYAN}Web UI:{C.RESET}       http://{args.webui_host}:{args.webui_port}")
        if webui_proc and not args.api_only:
            print(f"  {C.CYAN}Mode:{C.RESET}         API Proxy (WebUI → API → DB)")
        print(f"  {C.CYAN}Log Level:{C.RESET}    {log_level}")
        print(f"{C.BOLD}{C.GREEN}{'═' * 58}{C.RESET}")
        print(f"\n  Press {C.BOLD}Ctrl+C{C.RESET} to stop all services.\n")

        # ── Wait for processes ──
        while True:
            for p in processes:
                ret = p.poll()
                if ret is not None:
                    print(f"{C.RED}✗ Process {p.pid} exited with code {ret}{C.RESET}")
                    shutdown()
            time.sleep(2)

    except KeyboardInterrupt:
        shutdown()
    except Exception as e:
        print(f"{C.RED}✗ Error: {e}{C.RESET}")
        shutdown()


if __name__ == "__main__":
    main()
