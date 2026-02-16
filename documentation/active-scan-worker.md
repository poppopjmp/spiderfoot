# Active Scan Worker — Architecture & Integration Guide

## Overview

The **active scan worker** is a dedicated Celery container that handles all scan
execution tasks.  It ships the full SpiderFoot codebase **plus** additional
reconnaissance tools that are not present in the base image, ensuring that every
`sfp_tool_*` and `sfp_*` module can find its required binary.

```
                        ┌─────────────────────────────┐
                        │       Redis (broker)         │
                        └──────┬──────────┬────────────┘
                               │          │
          ┌────────────────────┘          └──────────────────────┐
          │  queues: default, report,                            │
          │  export, agents, monitor                 queue: scan │
          ▼                                                      ▼
┌──────────────────────┐                        ┌──────────────────────────┐
│   celery-worker      │                        │  celery-worker-active    │
│   (general tasks)    │                        │  (active scanning)       │
│                      │                        │                          │
│  Base image only     │                        │  21+ recon tools:        │
│  No scan binaries    │                        │  httpx, subfinder,       │
│  needed              │                        │  gobuster, amass, dnsx,  │
│                      │                        │  massdns, naabu, masscan │
│                      │                        │  katana, gospider, gau,  │
│                      │                        │  hakrawler, waybackurls, │
│                      │                        │  ffuf, gowitness, tlsx,  │
│                      │                        │  arjun, sslyze, sslscan, │
│                      │                        │  dalfox, nikto, gitleaks,│
│                      │                        │  linkfinder + wordlists  │
└──────────────────────┘                        └──────────────────────────┘
```

## Queue Routing

Celery task routing is configured in `spiderfoot/celery_app.py`:

| Task pattern                  | Queue     | Worker               |
|-------------------------------|-----------|----------------------|
| `spiderfoot.tasks.scan.*`     | `scan`    | celery-worker-active |
| `spiderfoot.tasks.report.*`   | `report`  | celery-worker        |
| `spiderfoot.tasks.export.*`   | `export`  | celery-worker        |
| `spiderfoot.tasks.agents.*`   | `agents`  | celery-worker        |
| `spiderfoot.tasks.monitor.*`  | `monitor` | celery-worker        |
| Everything else               | `default` | celery-worker        |

No code changes are needed — the existing `celery_app.py` routes `scan.*` tasks
to the `scan` queue automatically.  The worker separation is purely at the
docker-compose level by assigning different `--queues` flags.

## Tool Inventory

### Already in the base image (`Dockerfile`)

| Tool          | Module(s)                | Type       |
|---------------|--------------------------|------------|
| nmap          | `sfp_nmap`               | apt        |
| nuclei        | `sfp_nuclei`             | binary     |
| testssl.sh    | `sfp_tool_testsslsh`     | git clone  |
| CMSeeK        | `sfp_tool_cmseek`        | git clone  |
| retire.js     | `sfp_tool_retirejs`      | npm        |
| nbtscan       | `sfp_tool_nbtscan`       | apt        |
| onesixtyone   | `sfp_tool_onesixtyone`   | apt        |
| whatweb        | `sfp_tool_whatweb`       | apt        |
| dnstwist      | `sfp_tool_dnstwist`      | pip        |
| snallygaster  | `sfp_tool_snallygaster`  | pip        |
| trufflehog    | `sfp_tool_trufflehog`    | pip        |
| wafw00f       | `sfp_tool_wafw00f`       | pip        |

### Added by the active worker (`Dockerfile.active-worker`)

#### DNS & Subdomain Enumeration

| Tool       | Module                    | Purpose                             | Install   |
|------------|---------------------------|--------------------------------------|-----------|
| **httpx**      | `sfp_httpx`           | HTTP probing & tech fingerprinting  | Go build  |
| **subfinder**  | `sfp_subfinder`       | Passive subdomain enumeration       | Go build  |
| **gobuster**   | `sfp_tool_gobuster`   | Directory / DNS brute-forcing       | Go build  |
| amass      | `sfp_tool_amass`          | OWASP attack surface mapping        | Go build  |
| dnsx       | `sfp_tool_dnsx`           | DNS resolution & record queries     | Go build  |
| massdns    | `sfp_tool_massdns`        | Bulk DNS resolution                 | C build   |

#### Web Crawling & Discovery

| Tool       | Module                    | Purpose                             | Install   |
|------------|---------------------------|--------------------------------------|-----------|
| katana     | `sfp_tool_katana`         | Next-gen web crawling (headless)    | Go build  |
| gospider   | `sfp_tool_gospider`       | Fast web spider                     | Go build  |
| hakrawler  | `sfp_tool_hakrawler`      | Simple web crawler                  | Go build  |
| gau        | `sfp_tool_gau`            | Fetch archived URLs (Wayback etc.)  | Go build  |
| waybackurls| `sfp_tool_waybackurls`    | Wayback Machine URL extraction      | Go build  |
| ffuf       | `sfp_tool_ffuf`           | Web content fuzzing                 | Go build  |
| gowitness  | `sfp_tool_gowitness`      | Web screenshots (headless Chrome)   | Go build  |
| arjun      | `sfp_tool_arjun`          | HTTP parameter discovery            | pip       |

#### Port Scanning

| Tool       | Module                    | Purpose                             | Install   |
|------------|---------------------------|--------------------------------------|-----------|
| naabu      | `sfp_tool_naabu`          | High-speed SYN/CONNECT port scan    | Go build  |
| masscan    | `sfp_tool_masscan`        | Ultra-fast mass port scanner        | C build   |

#### Vulnerability Scanning

| Tool       | Module                    | Purpose                             | Install   |
|------------|---------------------------|--------------------------------------|-----------|
| dalfox     | `sfp_tool_dalfox`         | XSS parameter scanning              | Go build  |
| nikto      | `sfp_tool_nikto`          | Classic web vulnerability scanner   | git clone |

#### Secret & JS Analysis

| Tool       | Module                    | Purpose                             | Install   |
|------------|---------------------------|--------------------------------------|-----------|
| gitleaks   | `sfp_tool_gitleaks`       | Git secret detection                | Go build  |
| linkfinder | `sfp_tool_linkfinder`     | JS endpoint extraction              | pip       |

#### SSL/TLS Analysis

| Tool       | Module                    | Purpose                             | Install   |
|------------|---------------------------|--------------------------------------|-----------|
| tlsx       | `sfp_tool_tlsx`           | Fast TLS cert & cipher analysis     | Go build  |
| sslyze     | `sfp_tool_sslyze`         | Deep SSL/TLS configuration audit    | pip       |
| sslscan    | `sfp_tool_sslscan`        | SSL cipher enumeration              | apt       |

**Bold** = required by a pre-existing SpiderFoot module; all others have new
dedicated modules created in `modules/sfp_tool_*.py`.

### Wordlists (downloaded at build time)

| File                               | Purpose                         |
|------------------------------------|---------------------------------|
| `/tools/wordlists/common.txt`                   | Web content discovery  |
| `/tools/wordlists/raft-medium-directories.txt`  | Directory brute-force  |
| `/tools/wordlists/raft-medium-files.txt`        | File discovery         |
| `/tools/wordlists/subdomains-top1million-5000.txt`  | DNS subdomain enum |
| `/tools/wordlists/subdomains-top1million-20000.txt` | DNS subdomain enum |
| `/tools/wordlists/subdomains-top1million-110000.txt`| Large subdomain enum|
| `/tools/wordlists/burp-parameter-names.txt`     | Parameter fuzzing      |
| `/tools/wordlists/resolvers.txt`                | DNS resolvers list     |

Modules can find wordlists via `SF_WORDLISTS_PATH` environment variable
(defaults to `/tools/wordlists`).

## Files Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `Dockerfile.active-worker` | **Created** | Multi-stage build: Go builder → C builder → wordlists → runtime |
| `docker-compose-microservices.yml` | **Modified** | Added `celery-worker-active` service with `scan` profile + `x-sf-active-build` anchor; general worker no longer handles `scan` queue |
| `documentation/active-scan-worker.md` | **Created** | This file |

## Build & Run

### Using Docker Compose profiles

```bash
# 1. Copy / edit environment
cp .env.example .env

# 2. Build base image first, then all services including active worker
docker compose -f docker-compose-microservices.yml --profile scan build api
docker compose -f docker-compose-microservices.yml --profile scan build

# 3. Start core + active scan worker
docker compose -f docker-compose-microservices.yml --profile scan up -d
```

### Build order note

`Dockerfile.active-worker` uses `FROM spiderfoot-micro:latest` — the base image
must be built before the active worker image.  Running `docker compose build api`
first (or `docker compose up --build`) ensures this.

## Resource Requirements

| Container              | CPU   | RAM   | Notes                            |
|------------------------|-------|-------|----------------------------------|
| celery-worker          | 2 CPU | 2 GB  | General tasks, low resource use  |
| celery-worker-active   | 4 CPU | 4 GB  | Scans are CPU & network-heavy    |

Active scan concurrency is controlled by `CELERY_ACTIVE_WORKER_CONCURRENCY`
(default: `2`).  Each scan can spawn multiple tool processes, so keep concurrency
low to avoid resource contention.

## Scaling

To run multiple active scan workers (horizontal scaling):

```bash
docker compose -f docker-compose-microservices.yml up -d \
  --scale celery-worker-active=3
```

Each instance will compete for tasks from the `scan` queue via Celery's built-in
fair scheduling (`worker_prefetch_multiplier=1`, `task_acks_late=True`).

## Security Considerations

- The active worker runs with `CAP_NET_RAW` and `CAP_NET_ADMIN` capabilities
  (required for nmap SYN scans, naabu raw sockets).
- Tools like nmap, naabu, and massdns have `setcap` applied inside the container.
- The container still runs as the non-root `spiderfoot` user.
- Network access: The active worker needs egress to scan targets.  Consider
  firewall rules to prevent scanning internal infrastructure.

## Extending with New Tools

1. Add the tool installation to `Dockerfile.active-worker` (in the appropriate
   builder stage).
2. Create a new `sfp_tool_<name>.py` module in `modules/`.
3. The module should look for the binary in `PATH` (the `/tools/bin/` directory
   is already on `PATH` inside the container).
4. Rebuild: `docker compose build celery-worker-active`.

## Module Event Flow

The new tool modules integrate into SpiderFoot's event-driven pipeline.
Below is the data flow showing which events trigger each tool and what
they produce:

```
DOMAIN_NAME ──┬──→ sfp_tool_amass      ──→ INTERNET_NAME, IP_ADDRESS
              ├──→ sfp_tool_gau        ──→ LINKED_URL_*, URL_JAVASCRIPT
              ├──→ sfp_tool_waybackurls──→ LINKED_URL_*, URL_JAVASCRIPT
              ├──→ sfp_tool_gospider   ──→ LINKED_URL_*, URL_JAVASCRIPT, EMAILADDR
              ├──→ sfp_tool_katana     ──→ LINKED_URL_*, URL_JAVASCRIPT
              ├──→ sfp_tool_ffuf       ──→ LINKED_URL_INTERNAL, HTTP_CODE
              ├──→ sfp_tool_hakrawler  ──→ LINKED_URL_*, URL_JAVASCRIPT
              └──→ sfp_tool_nikto      ──→ VULNERABILITY_*, WEBSERVER_*

INTERNET_NAME ┬──→ sfp_tool_dnsx       ──→ IP_ADDRESS, RAW_DNS_RECORDS, DNS_*
              ├──→ sfp_tool_naabu      ──→ TCP_PORT_OPEN
              ├──→ sfp_tool_tlsx       ──→ SSL_CERTIFICATE_*, VULNERABILITY_*
              ├──→ sfp_tool_sslyze     ──→ SSL_CERTIFICATE_*, VULNERABILITY_*
              └──→ sfp_tool_sslscan    ──→ SSL_CERTIFICATE_*, VULNERABILITY_*

INTERNET_NAME_UNRESOLVED
              └──→ sfp_tool_massdns    ──→ IP_ADDRESS, INTERNET_NAME (promoted)

IP_ADDRESS ───┬──→ sfp_tool_naabu      ──→ TCP_PORT_OPEN
              ├──→ sfp_tool_masscan    ──→ TCP_PORT_OPEN, WEBSERVER_BANNER
              ├──→ sfp_tool_tlsx       ──→ SSL_CERTIFICATE_*
              └──→ sfp_tool_sslyze     ──→ SSL_CERTIFICATE_*, VULNERABILITY_*

URL_FORM ─────┬──→ sfp_tool_dalfox     ──→ VULNERABILITY_*, RAW_RIR_DATA
              └──→ sfp_tool_arjun      ──→ URL_FORM, RAW_RIR_DATA

URL_JAVASCRIPT└──→ sfp_tool_linkfinder ──→ LINKED_URL_INTERNAL, LINKED_URL_EXTERNAL

LINKED_URL_INTERNAL
              ├──→ sfp_tool_katana     ──→ LINKED_URL_*, URL_JAVASCRIPT
              ├──→ sfp_tool_ffuf       ──→ LINKED_URL_INTERNAL, HTTP_CODE
              ├──→ sfp_tool_gowitness  ──→ RAW_RIR_DATA (screenshot metadata)
              ├──→ sfp_tool_nikto      ──→ VULNERABILITY_*
              └──→ sfp_tool_arjun      ──→ URL_FORM

PUBLIC_CODE_REPO
              └──→ sfp_tool_gitleaks   ──→ PASSWORD_COMPROMISED, VULNERABILITY_*

NETBLOCK_OWNER└──→ sfp_tool_masscan    ──→ TCP_PORT_OPEN

TCP_PORT_OPEN └──→ sfp_tool_tlsx       ──→ SSL_CERTIFICATE_* (TLS ports only)
```

## New Modules Reference

| Module | Tool | Watched Events | Key Produced Events |
|--------|------|---------------|---------------------|
| `sfp_tool_amass` | OWASP Amass | `DOMAIN_NAME` | `INTERNET_NAME`, `IP_ADDRESS` |
| `sfp_tool_dnsx` | dnsx | `INTERNET_NAME`, `DOMAIN_NAME` | `IP_ADDRESS`, `RAW_DNS_RECORDS`, `DNS_TEXT` |
| `sfp_tool_massdns` | massdns | `INTERNET_NAME_UNRESOLVED` | `IP_ADDRESS`, `INTERNET_NAME` |
| `sfp_tool_gau` | gau | `DOMAIN_NAME` | `LINKED_URL_*`, `URL_JAVASCRIPT` |
| `sfp_tool_waybackurls` | waybackurls | `DOMAIN_NAME` | `LINKED_URL_*`, `URL_JAVASCRIPT` |
| `sfp_tool_gospider` | gospider | `DOMAIN_NAME`, `LINKED_URL_INTERNAL` | `LINKED_URL_*`, `URL_JAVASCRIPT`, `EMAILADDR` |
| `sfp_tool_hakrawler` | hakrawler | `DOMAIN_NAME`, `LINKED_URL_INTERNAL` | `LINKED_URL_*`, `URL_JAVASCRIPT` |
| `sfp_tool_katana` | katana | `DOMAIN_NAME`, `LINKED_URL_INTERNAL` | `LINKED_URL_*`, `URL_JAVASCRIPT` |
| `sfp_tool_ffuf` | ffuf | `DOMAIN_NAME`, `LINKED_URL_INTERNAL` | `LINKED_URL_INTERNAL`, `HTTP_CODE` |
| `sfp_tool_gowitness` | gowitness | `LINKED_URL_INTERNAL`, `DOMAIN_NAME` | `RAW_RIR_DATA` |
| `sfp_tool_arjun` | Arjun | `LINKED_URL_INTERNAL`, `URL_FORM` | `URL_FORM`, `RAW_RIR_DATA` |
| `sfp_tool_nikto` | Nikto | `DOMAIN_NAME`, `IP_ADDRESS`, `LINKED_URL_INTERNAL` | `VULNERABILITY_*`, `WEBSERVER_BANNER` |
| `sfp_tool_dalfox` | Dalfox | `URL_FORM`, `LINKED_URL_INTERNAL` | `VULNERABILITY_*` |
| `sfp_tool_gitleaks` | Gitleaks | `PUBLIC_CODE_REPO` | `PASSWORD_COMPROMISED`, `VULNERABILITY_GENERAL` |
| `sfp_tool_linkfinder` | LinkFinder | `URL_JAVASCRIPT` | `LINKED_URL_INTERNAL`, `LINKED_URL_EXTERNAL` |
| `sfp_tool_naabu` | Naabu | `IP_ADDRESS`, `INTERNET_NAME`, `DOMAIN_NAME` | `TCP_PORT_OPEN` |
| `sfp_tool_masscan` | Masscan | `IP_ADDRESS`, `NETBLOCK_OWNER` | `TCP_PORT_OPEN`, `WEBSERVER_BANNER` |
| `sfp_tool_tlsx` | tlsx | `INTERNET_NAME`, `IP_ADDRESS`, `TCP_PORT_OPEN` | `SSL_CERTIFICATE_*`, `VULNERABILITY_GENERAL` |
| `sfp_tool_sslyze` | SSLyze | `INTERNET_NAME`, `IP_ADDRESS` | `SSL_CERTIFICATE_*`, `VULNERABILITY_CVE_*` |
| `sfp_tool_sslscan` | sslscan | `INTERNET_NAME`, `IP_ADDRESS` | `SSL_CERTIFICATE_*`, `VULNERABILITY_GENERAL` |

## Scan Profiles

### Tools-Only Profile

The `tools-only` scan profile enables **all 36 external tool modules** in a single
scan — both pre-installed base tools and active worker tools. It also includes
`sfp_dnsresolve` and `sfp_spider` as core helpers to feed discovered data into
the tool pipeline.

```python
from spiderfoot.scan.scan_profile import get_profile_manager

pm = get_profile_manager()
profile = pm.get("tools-only")
modules = profile.resolve_modules(all_modules)
```

Or via the API:

```bash
curl -X POST http://localhost/api/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "type": "DOMAIN_NAME", "profile": "tools-only"}'
```

**Note:** The `tools-only` profile requires the active scan worker container
(`celery-worker-active`) to be running — base-image tools will work on any
worker, but active worker tools (amass, httpx, naabu, etc.) are only available
in the active worker image.

### Other Profiles

| Profile | Description |
|---------|-------------|
| `quick-recon` | Fast passive scan, no API keys |
| `full-footprint` | Comprehensive active footprinting |
| `passive-only` | Strictly passive, no target contact |
| `vuln-assessment` | Vulnerability & exposure focus |
| `infrastructure` | DNS, ports, hosting, SSL mapping |
| `social-media` | Social media presence discovery |
| `dark-web` | Tor hidden service search |
| `api-powered` | Premium API-key data sources only |
| `minimal` | Bare minimum for validation |
| `investigate` | Deep targeted investigation |

## CI/CD — E2E Tool Testing

The GitHub Actions workflow `.github/workflows/e2e-tools.yml` provides automated
end-to-end testing of the active scan worker:

1. **Build** — Builds both `spiderfoot-micro` and `spiderfoot-active` images
2. **Verify Tools** — Checks every binary exists and runs its version command
3. **Verify Modules** — Imports all 36 tool modules inside the container
4. **Smoke Test** — Runs live tool tests against `example.com` (httpx, subfinder,
   dnsx, gau, katana, tlsx, sslscan)

The workflow runs on pushes to `main`/`dev-*` that modify `Dockerfile.active-worker`
or `modules/sfp_tool_*.py`, and can be triggered manually via `workflow_dispatch`.

## Docker Build — `Dockerfile.active-worker`

The image uses a **4-stage multi-stage build**:

| Stage | Base Image | Purpose |
|-------|-----------|---------|
| `go-builder` | `golang:1.24-bookworm` | Compile 16 Go tools with `GOTOOLCHAIN=auto` |
| `c-builder` | `debian:bookworm-slim` | Compile massdns + masscan from source |
| `wordlists` | `debian:bookworm-slim` | Download 8 curated wordlists |
| Runtime | `spiderfoot-micro:latest` | Install apt/pip tools, copy binaries & wordlists |

The `BASE_IMAGE` build argument allows CI to pass a GHCR image tag:

```bash
docker build -f Dockerfile.active-worker \
  --build-arg BASE_IMAGE=ghcr.io/org/spiderfoot-base:v5.9.0 \
  -t spiderfoot-active:latest .
```
