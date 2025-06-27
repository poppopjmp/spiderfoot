# sfp_ipinfo

**Purpose:**
Queries the IPinfo API for geolocation, ASN, and network information about the target IP address. Useful for mapping infrastructure and identifying hosting providers.

**Category:** Infrastructure Mapping / Geolocation

---

## Usage

- Enabled for IP address targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s 8.8.8.8 -t IP_ADDRESS -m sfp_ipinfo
```

## Output Example

```pre
IP: 8.8.8.8
Location: United States, California
ASN: AS15169 (Google LLC)
ISP: Google
```

## API Keys Required

- IPinfo API key (optional, for higher rate limits)

## Tips

- Use to enrich IP addresses with geolocation and ASN data.
- Combine with sfp_shodan and sfp_portscan_tcp for full context.

---

Authored by poppopjmp
