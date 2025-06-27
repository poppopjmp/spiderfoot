# Modules

*Author: poppopjmp*

SpiderFoot includes over 200 modules for data gathering, enrichment, and analysis. Modules can be combined to create powerful OSINT workflows tailored to your needs.

---

## What Are Modules?

Modules are plugins that collect, enrich, or analyze data from various sources. Each module focuses on a specific data type or integration (e.g., DNS, WHOIS, Shodan, VirusTotal, breach data, social media, etc.).

- Modules can be enabled, disabled, or configured individually.
- Some modules require API keys for external services (see [Configuration](configuration.md)).
- You can run scans with all modules or select a subset for targeted investigations.

---

## Module Categories

### DNS and Network
- **sfp_dnsresolve**: DNS resolution and reverse DNS
- **sfp_whois**: WHOIS information lookup
- **sfp_ssl**: SSL certificate analysis
- **sfp_portscan_tcp**: TCP port scanning
- **sfp_banner**: Service banner grabbing

### Threat Intelligence
- **sfp_threatcrowd**: ThreatCrowd API queries
- **sfp_virustotal**: VirusTotal API integration
- **sfp_alienvault**: AlienVault OTX integration
- **sfp_malware**: Malware analysis platforms

### Search Engines
- **sfp_google**: Google search results
- **sfp_bing**: Bing search results
- **sfp_duckduckgo**: DuckDuckGo search
- **sfp_yandex**: Yandex search engine

### Social Media
- **sfp_twitter**: Twitter account enumeration
- **sfp_github**: GitHub repository discovery
- **sfp_linkedin**: LinkedIn profile discovery
- **sfp_instagram**: Instagram account lookup

### Data Breach
- **sfp_haveibeen**: HaveIBeenPwned integration
- **sfp_hunter**: Hunter.io email discovery
- **sfp_emailrep**: Email reputation checking

---

## Module Index

Below is a complete list of all documented modules. Click a module name to view its documentation:

| Module | Description |
|--------|-------------|
| [sfp_alienvault](modules/sfp_alienvault.md) | Queries AlienVault OTX for threat intelligence, indicators of compromise, and reputation data. |
| [sfp_arin](modules/sfp_arin.md) | Queries ARIN for network, ASN, and contact information. |
| [sfp_breach](modules/sfp_breach.md) | Checks for data breaches and leaked credentials. |
| [sfp_btc](modules/sfp_btc.md) | Identifies and analyzes Bitcoin addresses related to the target. |
| [sfp_certspotter](modules/sfp_certspotter.md) | Queries CertSpotter for certificate transparency logs. |
| [sfp_dnsbrute](modules/sfp_dnsbrute.md) | Performs DNS brute-forcing to discover subdomains. |
| [sfp_dnsdumpster](modules/sfp_dnsdumpster.md) | Queries DNSDumpster for passive DNS and subdomain enumeration. |
| [sfp_dnsresolve](modules/sfp_dnsresolve.md) | Resolves DNS records for the target domain or host. |
| [sfp_email](modules/sfp_email.md) | Extracts and analyzes email addresses related to the target. |
| [sfp_github](modules/sfp_github.md) | Searches GitHub for code, repositories, and mentions. |
| [sfp_gravatar](modules/sfp_gravatar.md) | Searches Gravatar for avatars, profile data, and associated emails. |
| [sfp_hibp](modules/sfp_hibp.md) | Checks HaveIBeenPwned for breaches and exposures. |
| [sfp_ipinfo](modules/sfp_ipinfo.md) | Queries IPinfo for geolocation, ASN, and network information. |
| [sfp_pastebin](modules/sfp_pastebin.md) | Searches Pastebin for leaks, credentials, and mentions. |
| [sfp_portscan_tcp](modules/sfp_portscan_tcp.md) | Performs TCP port scanning on the target host. |
| [sfp_riskiq](modules/sfp_riskiq.md) | Integrates with RiskIQ (PassiveTotal) for passive DNS, SSL, and threat intelligence. |
| [sfp_securitytrails](modules/sfp_securitytrails.md) | Integrates with SecurityTrails for passive DNS, WHOIS, and infrastructure data. |
| [sfp_shodan](modules/sfp_shodan.md) | Queries Shodan for open ports, banners, vulnerabilities, and geolocation. |
| [sfp_social](modules/sfp_social.md) | Searches social media platforms for mentions, profiles, and activity. |
| [sfp_ssl](modules/sfp_ssl.md) | Analyzes SSL/TLS certificates for the target host. |
| [sfp_threatcrowd](modules/sfp_threatcrowd.md) | Queries ThreatCrowd for information about domains, IPs, and emails. |
| [sfp_twitter](modules/sfp_twitter.md) | Searches Twitter for profiles, mentions, and activity. |
| [sfp_username](modules/sfp_username.md) | Searches for usernames related to the target across social media and forums. |
| [sfp_virustotal](modules/sfp_virustotal.md) | Integrates with VirusTotal to check domains, IPs, and files for malware and reputation. |
| [sfp_whois](modules/sfp_whois.md) | Performs WHOIS lookups for domains and IP addresses. |

---

## Module Selection Strategies

- **By Use Case:**
  - Passive: sfp_dnsresolve,sfp_whois,sfp_ssl,sfp_threatcrowd,sfp_virustotal
  - Active: sfp_subdomain_enum,sfp_spider,sfp_webheader
  - Network: sfp_portscan_tcp,sfp_banner,sfp_ssl,sfp_whois
  - Internet Exposure: sfp_shodan,sfp_censys,sfp_binaryedge
- **By Risk Level:**
  - Low: Passive only
  - Medium: Minimal active
  - High: Full active

---

## Module Configuration & Performance

- Configure API keys and options for each module in the web UI under **Settings → Module Settings**.
- Modules that require API keys will show a warning if not configured.
- Tune thread counts, timeouts, and module-specific limits for performance.
- Monitor API rate limits to avoid blocking.

---

## Developing Your Own Modules

- SpiderFoot's modular architecture makes it easy to add new modules.
- See the [Developer Guide](developer_guide.md) for instructions, templates, and best practices.
- Community contributions are welcome!

---

## Best Practices

- Start with passive modules for initial reconnaissance
- Understand module behavior before using active modules
- Consider target sensitivity when choosing modules
- Monitor resource usage during scans
- Tune thread counts and timeouts for performance
- Regularly update modules and API keys

---

## More Information

- See the webapp for a full, searchable module index and descriptions.
- For troubleshooting module issues, see the [Troubleshooting Guide](troubleshooting.md).

---
