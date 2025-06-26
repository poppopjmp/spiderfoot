# Configuration

## API Keys
Configure API keys in the web UI under Settings → Module Settings.

Common APIs:
- VirusTotal
- Shodan
- Hunter.io
- SecurityTrails
- Have I Been Pwned

## Configuration File
Edit `spiderfoot.conf` for advanced options:

```ini
[webui]
host = 127.0.0.1
port = 5001

[database]
path = spiderfoot.db
```
