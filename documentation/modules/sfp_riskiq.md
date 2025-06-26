# sfp_riskiq

**Purpose:**
Integrates with RiskIQ (PassiveTotal) to gather passive DNS, SSL, and threat intelligence data for the target. Useful for infrastructure mapping and threat analysis.

**Category:** Threat Intelligence / Infrastructure Mapping

---

## Usage

- Enabled for domain and IP targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_riskiq
```

## Output Example

```pre
Domain: example.com
Passive DNS: 93.184.216.34, 93.184.216.35
SSL Certificates: 2
Threats: 1
```

## API Keys Required

- RiskIQ API key (required)

## Tips

- Use to enrich asset and threat intelligence with historical data.
- Combine with sfp_dnsresolve and sfp_ssl for full mapping.

---

Authored by poppopjmp
