# SpiderFoot CLI (Go)

Cross-platform command-line client for the SpiderFoot REST API. Compiles to a single static binary for Linux, macOS, and Windows.

## Quick Start

```bash
# Build for your current platform
make build

# Or build all platforms at once
make all

# Run
./build/sf health --server http://localhost:8001
```

## Installation

Download the latest release for your platform from the releases page, or build from source:

```bash
cd cli
go build -o sf .
```

## Configuration

The CLI reads configuration from (in order of precedence):
1. Command-line flags
2. Environment variables (prefixed with `SF_`)
3. `~/.spiderfoot.yaml` config file

### Environment Variables

```bash
export SF_SERVER=http://localhost:8001
export SF_API_KEY=your-api-key
export SF_TOKEN=your-jwt-token
```

### Config File

```yaml
# ~/.spiderfoot.yaml
server: http://localhost:8001
api_key: your-api-key
output: table
```

## Commands

### Health Check

```bash
sf health
sf health --server https://spiderfoot.example.com
```

### Scans

```bash
# List all scans
sf scan list

# Get scan details
sf scan get <scan-id>

# Start a new scan
sf scan start --target example.com --name "My Scan"
sf scan start -t example.com --type passive
sf scan start -t example.com --modules sfp_dns,sfp_whois

# Stop a running scan
sf scan stop <scan-id>

# Delete a scan
sf scan delete <scan-id>
```

### Modules

```bash
# List all modules
sf modules

# Filter by type
sf modules --filter passive

# Output as JSON
sf modules -o json
```

### Export

```bash
# Export scan results
sf export json <scan-id>
sf export csv <scan-id>
sf export stix <scan-id>
sf export excel <scan-id>

# Specify output file
sf export json <scan-id> --file results.json
```

### Schedules

```bash
# List schedules
sf schedule list

# Create a schedule (interval in hours)
sf schedule create --name "Daily scan" --target example.com --interval 24

# Update a schedule
sf schedule update <schedule-id> --interval 12 --description "Twice daily"

# Delete a schedule
sf schedule delete <schedule-id>

# Manually trigger a schedule
sf schedule trigger <schedule-id>
```

### Configuration

```bash
# Show current config
sf config show

# Set a value
sf config set server http://localhost:8001
sf config set api_key mykey123
```

### Global Flags

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--server` | | API server URL | `http://127.0.0.1:8001` |
| `--api-key` | | API key | |
| `--token` | | JWT bearer token | |
| `--output` | `-o` | Output format: table/json/csv | `table` |
| `--no-color` | | Disable colored output | `false` |
| `--insecure` | | Skip TLS verification | `false` |
| `--config` | | Config file path | `~/.spiderfoot.yaml` |

## Cross-Platform Build

Requires Go 1.22+.

```bash
make all        # Build for all platforms (6 binaries)
make linux      # Build linux-amd64 and linux-arm64
make darwin     # Build darwin-amd64 and darwin-arm64
make windows    # Build windows-amd64 and windows-arm64
```

Output binaries are placed in the `build/` directory.

## Architecture

```
cli/
├── main.go                    Entry point
├── cmd/
│   ├── root.go                Root command, persistent flags, viper config
│   ├── version.go             Version info
│   ├── health.go              Health check
│   ├── scan.go                Scan CRUD (list, get, start, stop, delete)
│   ├── modules.go             Module listing
│   ├── export.go              Data export (JSON, CSV, STIX, Excel)
│   ├── schedule.go            Schedule management
│   └── config.go              CLI configuration
├── internal/
│   ├── client/
│   │   └── client.go          HTTP client with auth, TLS, retries
│   └── output/
│       └── output.go          Table, JSON, CSV formatters
├── Makefile                   Cross-compilation targets
└── go.mod                     Go module definition
```
