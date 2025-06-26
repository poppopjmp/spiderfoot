# sfp_portscan_tcp

**Purpose:**
Performs TCP port scanning on the target host to identify open ports and services. Useful for attack surface mapping and vulnerability assessment.

**Category:** Reconnaissance / Attack Surface

---

## Usage

- Enabled for IP and domain targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s 8.8.8.8 -t IP_ADDRESS -m sfp_portscan_tcp
```

## Output Example

```pre
IP: 8.8.8.8
Open Ports: 53, 80, 443
Services: DNS, HTTP, HTTPS
```

## API Keys Required

None

## Tips

- Use to identify exposed services and potential vulnerabilities.
- Combine with sfp_shodan for deeper analysis.

---

*Authored by poppopjmp*
