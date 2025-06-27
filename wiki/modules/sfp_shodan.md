# sfp_shodan

**Purpose:**
Queries the Shodan API for information about the target IP, domain, or network, including open ports, banners, vulnerabilities, and geolocation. Useful for attack surface mapping and vulnerability assessment.

**Category:** Threat Intelligence / Attack Surface

---

## Usage
- Enabled for IP, domain, and network targets.
- Can be run from the web UI or CLI:
  ```sh
  python sf.py -s 8.8.8.8 -t IP_ADDRESS -m sfp_shodan
  ```

## Output Example
```
IP: 8.8.8.8
Open Ports: 53, 443
Banners: DNS, HTTPS
Vulnerabilities: None
Location: United States
```

## API Keys Required
- Shodan API key (required)

## Tips
- Use to identify exposed services and vulnerabilities.
- Combine with sfp_portscan_tcp for deeper port analysis.

---

*Authored by poppopjmp*
