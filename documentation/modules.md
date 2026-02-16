# Modules

*Author: poppopjmp*

SpiderFoot includes **300+ modules** for data gathering, enrichment, and analysis, including **33 external tool integrations** for active reconnaissance. Modules can be combined to create powerful OSINT workflows tailored to your needs.

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
- **sfp_tiktok_osint**: TikTok profile analysis and content intelligence
- **sfp_mastodon**: Mastodon social network analysis
- **sfp_telegram**: Telegram channel and user analysis

### Blockchain & Cryptocurrency
- **sfp_bitcoin**: Bitcoin address analysis
- **sfp_ethereum**: Ethereum address investigation
- **sfp_blockchain_analytics**: Advanced multi-cryptocurrency investigation
- **sfp_blockchain**: General blockchain analysis

### External Tools (Active Reconnaissance)

SpiderFoot integrates **36 external security tool modules** for active scanning. Most require the **Active Scan Worker** Docker image. See [Active Scan Worker](active-scan-worker.md) for details.

#### Subdomain & DNS
- **sfp_subfinder**: Passive subdomain discovery via Subfinder
- **sfp_tool_amass**: Advanced subdomain enumeration via Amass
- **sfp_tool_dnsx**: DNS toolkit for resolution and brute-forcing
- **sfp_tool_dnstwist**: Similar domain and typosquat detection
- **sfp_tool_massdns**: High-performance bulk DNS resolver

#### Web & HTTP
- **sfp_httpx**: HTTP probing and technology detection
- **sfp_tool_katana**: Web crawler and spider
- **sfp_tool_gau**: Fetch known URLs from web archives
- **sfp_tool_gospider**: Fast web spidering
- **sfp_tool_hakrawler**: Simple web crawler
- **sfp_tool_waybackurls**: Wayback Machine URL fetcher
- **sfp_tool_nikto**: Web server vulnerability scanner
- **sfp_tool_whatweb**: Website technology fingerprinting
- **sfp_tool_wappalyzer**: Technology stack detection
- **sfp_tool_gobuster**: Directory and file brute-forcing
- **sfp_tool_gowitness**: Webpage screenshot capture
- **sfp_tool_ffuf**: Fast web fuzzer

#### SSL/TLS & Certificates
- **sfp_tool_tlsx**: TLS certificate and configuration analysis
- **sfp_tool_testsslsh**: Comprehensive SSL/TLS testing via testssl.sh
- **sfp_tool_sslscan**: SSL/TLS cipher and certificate scanning
- **sfp_tool_sslyze**: SSL/TLS deep analysis

#### Vulnerability & CMS
- **sfp_nuclei**: Template-based vulnerability scanner
- **sfp_tool_cmseek**: CMS detection and enumeration
- **sfp_tool_snallygaster**: Secret file and vulnerability scanner
- **sfp_tool_retirejs**: JavaScript library vulnerability detection
- **sfp_tool_dalfox**: XSS parameter scanner

#### Port & Network Scanning
- **sfp_tool_naabu**: Fast port scanner
- **sfp_tool_masscan**: High-speed network scanner
- **sfp_tool_onesixtyone**: SNMP community string scanner
- **sfp_tool_nbtscan**: NetBIOS name scanner
- **sfp_tool_wafw00f**: Web Application Firewall detection

#### Secret & Credential Discovery
- **sfp_tool_trufflehog**: Secret and credential scanner in repositories
- **sfp_tool_gitleaks**: Git secret detection

#### Fuzzing & Parameter Discovery
- **sfp_tool_arjun**: HTTP parameter discovery
- **sfp_tool_linkfinder**: JavaScript endpoint extraction

#### OSINT & Social
- **sfp_tool_phoneinfoga**: Phone number OSINT

### AI & Advanced Analytics
- **sfp_advanced_correlation**: Cross-platform entity resolution and pattern analysis
- **sfp_performance_optimizer**: Intelligent caching and performance optimization

### Data Breach
- **sfp_haveibeen**: HaveIBeenPwned integration
- **sfp_hunter**: Hunter.io email discovery
- **sfp_emailrep**: Email reputation checking
- **sfp_hudsonrock**: Hudson Rock Cavalier infostealer intelligence

---

## Module Index

Below is a complete list of all documented modules. Click a module name to view its documentation:

| Module | Description |
|--------|-------------|
| [sfp_advanced_correlation](modules/sfp_advanced_correlation.md) | Advanced data correlation engine with cross-platform identity resolution, temporal analysis, and geospatial clustering. |
| [sfp_alienvault](modules/sfp_alienvault.md) | Queries AlienVault OTX for threat intelligence, indicators of compromise, and reputation data. |
| [sfp_arin](modules/sfp_arin.md) | Queries ARIN for network, ASN, and contact information. |
| [sfp_blockchain_analytics](modules/sfp_blockchain_analytics.md) | Advanced blockchain and cryptocurrency investigation with multi-chain support and risk assessment. |
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
| [sfp_hudsonrock](modules/sfp_hudsonrock.md) | Queries Hudson Rock Cavalier API for infostealer-compromised credentials and machine data. |
| [sfp_ipinfo](modules/sfp_ipinfo.md) | Queries IPinfo for geolocation, ASN, and network information. |
| [sfp_pastebin](modules/sfp_pastebin.md) | Searches Pastebin for leaks, credentials, and mentions. |
| [sfp_performance_optimizer](modules/sfp_performance_optimizer.md) | Performance optimization with intelligent caching, rate limiting, and resource monitoring. |
| [sfp_portscan_tcp](modules/sfp_portscan_tcp.md) | Performs TCP port scanning on the target host. |
| [sfp_riskiq](modules/sfp_riskiq.md) | Integrates with RiskIQ (PassiveTotal) for passive DNS, SSL, and threat intelligence. |
| [sfp_securitytrails](modules/sfp_securitytrails.md) | Integrates with SecurityTrails for passive DNS, WHOIS, and infrastructure data. |
| [sfp_shodan](modules/sfp_shodan.md) | Queries Shodan for open ports, banners, vulnerabilities, and geolocation. |
| [sfp_social](modules/sfp_social.md) | Searches social media platforms for mentions, profiles, and activity. |
| [sfp_ssl](modules/sfp_ssl.md) | Analyzes SSL/TLS certificates for the target host. |
| [sfp_threatcrowd](modules/sfp_threatcrowd.md) | Queries ThreatCrowd for information about domains, IPs, and emails. |
| [sfp_tiktok_osint](modules/sfp_tiktok_osint.md) | Comprehensive TikTok intelligence gathering including user profiles and content analysis. |
| sfp_tool_amass | Advanced subdomain enumeration via OWASP Amass. |
| sfp_tool_arjun | HTTP parameter discovery and enumeration. |
| sfp_tool_cmseek | CMS detection and enumeration via CMSeeK. |
| sfp_tool_dalfox | XSS parameter scanner and vulnerability finder. |
| sfp_tool_dnsx | DNS toolkit for resolution, brute-forcing, and wildcard filtering. |
| sfp_tool_dnstwist | Domain typosquat and similar domain detection. |
| sfp_tool_ffuf | Fast web fuzzer for directory and parameter brute-forcing. |
| sfp_tool_gau | Fetch known URLs from Wayback Machine, Common Crawl, and other archives. |
| sfp_tool_gitleaks | Git secret and credential detection. |
| sfp_tool_gobuster | Directory, file, and DNS brute-forcing. |
| sfp_tool_gospider | Fast web spidering and crawling. |
| sfp_tool_gowitness | Webpage screenshot capture via headless Chrome. |
| sfp_tool_hakrawler | Simple, fast web crawler. |
| sfp_httpx | HTTP probing with technology detection and response analysis. |
| sfp_tool_katana | Advanced web crawling and spidering. |
| sfp_tool_linkfinder | JavaScript endpoint and URL extraction. |
| sfp_tool_masscan | High-speed TCP port scanner (requires NET_RAW capability). |
| sfp_tool_massdns | High-performance bulk DNS stub resolver (requires NET_RAW capability). |
| sfp_tool_naabu | Fast port scanner with SYN/CONNECT scanning (requires NET_RAW capability). |
| sfp_tool_nbtscan | NetBIOS name and information scanner. |
| sfp_tool_nikto | Web server vulnerability scanner. |
| sfp_nuclei | Template-based vulnerability scanner with 9000+ templates. |
| sfp_tool_onesixtyone | SNMP community string scanner. |
| sfp_tool_phoneinfoga | Phone number OSINT and information gathering. |
| sfp_tool_retirejs | Retired JavaScript library vulnerability detection. |
| sfp_tool_snallygaster | Secret file and configuration leak scanner. |
| sfp_tool_sslscan | SSL/TLS cipher suite and certificate analysis. |
| sfp_tool_sslyze | SSL/TLS deep analysis and certificate validation. |
| sfp_subfinder | Fast passive subdomain discovery. |
| sfp_tool_testsslsh | Comprehensive SSL/TLS testing via testssl.sh. |
| sfp_tool_tlsx | TLS certificate grabbing and configuration analysis. |
| sfp_tool_trufflehog | Secret and credential detection in repositories and filesystems. |
| sfp_tool_wafw00f | Web Application Firewall detection and fingerprinting. |
| sfp_tool_wappalyzer | Technology stack detection via Wappalyzer rules. |
| sfp_tool_waybackurls | Wayback Machine URL fetching. |
| sfp_tool_whatweb | Website technology fingerprinting and identification. |
| sfp_tool_wappalyzer | Technology stack detection via Wappalyzer rules. |

| [sfp_twitter](modules/sfp_twitter.md) | Searches Twitter for profiles, mentions, and activity. |
| [sfp_username](modules/sfp_username.md) | Searches for usernames related to the target across social media and forums. |
| [sfp_virustotal](modules/sfp_virustotal.md) | Integrates with VirusTotal to check domains, IPs, and files for malware and reputation. |
| [sfp_whois](modules/sfp_whois.md) | Performs WHOIS lookups for domains and IP addresses. |

---

## Module Selection Strategies

- **By Use Case:**
  - Passive: sfp_dnsresolve, sfp_whois, sfp_ssl, sfp_threatcrowd, sfp_virustotal
  - Active: sfp_tool_subfinder, sfp_tool_httpx, sfp_tool_nuclei, sfp_tool_katana
  - Network: sfp_tool_naabu, sfp_tool_masscan, sfp_tool_sslscan, sfp_whois
  - Internet Exposure: sfp_shodan, sfp_censys, sfp_binaryedge
  - External Tools: Use the **tools-only** scan profile for all 33 tool modules
- **By Risk Level:**
  - Low: Passive only
  - Medium: Minimal active (sfp_tool_httpx, sfp_tool_subfinder, sfp_tool_dnsx)
  - High: Full active (all sfp_tool_* modules)
- **By Scan Profile:**
  - Use predefined profiles like `tools-only`, `full`, `passive`, or `web-audit`
  - See [Scan Profiles](active-scan-worker.md#scan-profiles) for the full list

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
