# Spiderfoot OSINT Automation Platform

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://raw.githubusercontent.com/poppopjmp/spiderfoot/master/LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.9+-green)](https://www.python.org)
[![Stable Release](https://img.shields.io/badge/version-5.3.3-blue.svg)](https://github.com/poppopjmp/spiderfoot/releases/tag/v5.3.3)
[![Production Grade](https://img.shields.io/badge/Production-Grade-blue.svg)](https://github.com/poppopjmp/spiderfoot)
[![AI Enhanced](https://img.shields.io/badge/AI-Enhanced-orange.svg)](https://github.com/poppopjmp/spiderfoot)
[![CI status](https://github.com/poppopjmp/spiderfoot/workflows/Tests/badge.svg)](https://github.com/poppopjmp/spiderfoot/actions?query=workflow%3A"Tests")
[![Docker CI Build](https://github.com/poppopjmp/spiderfoot/workflows/Docker%20Image%20CI/badge.svg)](https://github.com/poppopjmp/spiderfoot/actions?query=workflow%3A"Docker%20Image%20CI")
[![Code QL](https://github.com/poppopjmp/spiderfoot/workflows/CodeQL/badge.svg)](https://github.com/poppopjmp/spiderfoot/actions?query=workflow%3A"CodeQL")
[![Last Commit](https://img.shields.io/github/last-commit/poppopjmp/spiderfoot)](https://github.com/poppopjmp/spiderfoot/commits/master)
[![codecov](https://codecov.io/github/poppopjmp/spiderfoot/graph/badge.svg?token=ZRD8GIXJSP)](https://codecov.io/github/poppopjmp/spiderfoot)
[![Codacy Security Scan](https://github.com/poppopjmp/spiderfoot/actions/workflows/codacy.yml/badge.svg)](https://github.com/poppopjmp/spiderfoot/actions/workflows/codacy.yml)
[![Discord](https://img.shields.io/discord/770524432464216074)](https://discord.gg/vyvztrG)
![Active Development](https://img.shields.io/badge/Maintenance%20Level-Actively%20Developed-brightgreen.svg)

**SpiderFoot** is a production-ready, enterprise-grade open source intelligence (OSINT) automation platform. Enhanced with advanced storage capabilities, AI-powered threat intelligence, and comprehensive security hardening, it integrates with hundreds of data sources and utilizes advanced methods for data analysis, making intelligence data easily navigable and actionable.

SpiderFoot features an embedded web-server for providing a clean and intuitive web-based interface but can also be used completely via the command-line. It's written in **Python 3** and **MIT-licensed**.

---

## Platform Architecture

```mermaid
graph TD;
    A[User] -->|Web UI| B[SpiderFoot Core Engine];
    A -->|CLI| B;
    B --> C[Modules];
    B --> D[Database];
    B --> E[API];
    C --> F[External Data Sources];
    E --> G[SIEM/SOAR/Integrations];
    B --> H[Scheduler];
    B --> I[Correlation Engine];
    B --> J[Reporting & Export];
```

---

## Spiderfoot Enhancements

This version includes production-ready enterprise features:

- **Advanced Storage Engine**: High-performance data storage with optimized querying and reporting
- **AI-Powered Threat Intelligence**: Automated threat analysis and intelligent pattern recognition
- **Security Hardening**: Enhanced security controls, input validation, and secure configurations
- **Comprehensive Reporting**: Advanced analytics and customizable report generation
- **Performance Optimization**: Scalable architecture for enterprise workloads
- **Production Configuration**: Ready-to-deploy configurations for enterprise environments

![Spiderfoot v5](./documentation/images/v5.png)

---

## Features

### Core Platform

- Web based UI or CLI
- Over 200 modules with enterprise enhancements
- Python 3.9+
- YAML-configurable [correlation engine](/correlations/README.md) with 37+ pre-defined rules
- CSV/JSON/GEXF export with advanced formatting options
- API key export/import
- SQLite and PostgreSQL back-end for enterprise scalability
- Highly configurable with production-ready defaults
- Fully documented with enterprise deployment guides
- Advanced visualizations and analytics
- TOR integration for dark web searching
- Docker and Kubernetes deployment support
- Can call other tools like DNSTwist, Whatweb, Nmap and CMSeeK
- Actively developed since 2012!
- Comprehensive REST API for enterprise integration

---

## Visual Workflow: Typical OSINT Scan

```mermaid
graph LR;
    A[Start Scan] --> B[Select Target];
    B --> C[Choose Modules];
    C --> D[Run Scan];
    D --> E[Data Collection];
    E --> F[Correlation & Analysis];
    F --> G[View Results];
    G --> H[Export/Integrate];
```

---

## Enterprise Capabilities

### AI-Powered Intelligence

- **Automated Threat Analysis**: Machine learning algorithms analyze patterns and identify threats
- **Intelligent Pattern Recognition**: AI-powered correlation of indicators across data sources
- **Predictive Analytics**: Threat trend analysis and risk prediction capabilities
- **Natural Language Processing**: Automated analysis of text-based intelligence sources

### Security & Compliance

- **Enhanced Input Validation**: Comprehensive sanitization and validation of all inputs
- **Security Configuration**: Hardened default configurations and security best practices
- **Audit Logging**: Comprehensive audit trails for compliance and forensic analysis
- **Access Controls**: Role-based access control and authentication mechanisms

### Performance & Scalability

- **High-Performance Storage**: Optimized database operations with compression and indexing
- **Concurrent Processing**: Advanced threading and asynchronous processing capabilities
- **Resource Management**: Intelligent resource allocation and memory optimization
- **Load Balancing**: Support for distributed scanning across multiple instances

### Advanced Analytics

- **Custom Dashboards**: Configurable dashboards with real-time metrics and KPIs
- **Comprehensive Reporting**: Advanced report generation with customizable templates
- **Data Visualization**: Interactive charts, graphs, and network topology views
- **Export Capabilities**: Multiple export formats with enterprise-grade data handling

### Enterprise Integration

- **REST API**: Comprehensive API for seamless integration with security tools
- **Webhook Support**: Real-time notifications and event-driven integrations
- **SIEM Integration**: Direct integration with popular SIEM platforms
- **CI/CD Pipeline Support**: Automated scanning integration for DevSecOps workflows

---

## Deployment Overview

```mermaid
graph TD;
    A[User/Analyst] -->|Web UI/CLI| B[SpiderFoot Container];
    B --> C[Persistent Storage];
    B --> D[Network];
    B --> E[External APIs];
    B --> F[SIEM/SOAR];
    B --> G[Monitoring];
```

---

## Documentation

Comprehensive documentation is available for all aspects of SpiderFoot Enterprise:

### Quick Links

- **[Installation Guide](documentation/installation.md)** - Complete setup instructions
- **[Quick Start Guide](documentation/quickstart.md)** - Get scanning quickly
- **[User Guide](documentation/user_guide.md)** - Fundamental concepts and usage
- **[CLI Reference](documentation/user_guide.md)** - Command-line interface guide
- **[API Documentation](documentation/api_reference.md)** - REST API reference
- **[Module Guide](documentation/modules.md)** - Understanding modules

---

## Uses

SpiderFoot can be used offensively (e.g. in a red team exercise or penetration test) for reconnaissance of your target or defensively to gather information about what you or your organisation might have exposed over the Internet.

You can target the following entities in a SpiderFoot scan:

- IP address
- Domain/sub-domain name
- Hostname
- Network subnet (CIDR)
- ASN
- E-mail address
- Phone number
- Username
- Person's name
- Bitcoin address

SpiderFoot's 200+ modules feed each other in a publisher/subscriber model to ensure maximum data extraction to do things like:

- [Host/sub-domain/TLD enumeration/extraction](https://asciinema.org/a/295912)
- [Email address, phone number and human name extraction](https://asciinema.org/a/295947)
- [Bitcoin and Ethereum address extraction](https://asciinema.org/a/295957)
- [Check for susceptibility to sub-domain hijacking](https://asciinema.org/a/344377)
- DNS zone transfers
- [Threat intelligence and Blacklist queries](https://asciinema.org/a/295949)
- API integration with [SHODAN](https://asciinema.org/a/127601), [HaveIBeenPwned](https://asciinema.org/a/128731), [GreyNoise](https://asciinema.org/a/295943), AlienVault, SecurityTrails, etc.
- [Social media account enumeration](https://asciinema.org/a/295923)
- [S3/Azure/Digitalocean bucket enumeration/scraping](https://asciinema.org/a/295941)
- IP geo-location
- Web scraping, web content analysis
- [Image, document and binary file meta data analysis](https://asciinema.org/a/296274)
- Dark web searches
- [Port scanning and banner grabbing](https://asciinema.org/a/295939)
- [Data breach searches](https://asciinema.org/a/296145)
- So much more...

---

## Enterprise Deployment

SpiderFoot Enterprise is production-ready and designed for enterprise environments:

### Quick Production Deployment

**Standard Installation:**

```bash
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot
pip3 install -r requirements.txt
python3 ./sf.py -l 127.0.0.1:5001
```

**Docker Production Deployment:**

```bash
# Production deployment with optimized configuration
docker-compose -f docker-compose-prod.yml up -d

# Development environment
docker-compose up -d
```

**Enterprise Configuration:**

```bash
# Initialize with production settings
python3 ./sf.py --init-prod

# Run with enterprise modules enabled
python3 ./sf.py -l 0.0.0.0:5001 --enterprise
```

### Enterprise Features Configuration

The enterprise modules are automatically loaded and configured:

- **Advanced Storage** (`sfp__stor_db_advanced`): High-performance data storage with compression and indexing
- **AI Threat Intelligence** (`sfp__ai_threat_intel`): ML-powered threat analysis and pattern recognition
- **Security Hardening** (`sfp__security_hardening`): Enhanced security controls and validation

See the [Enterprise Deployment Guide](docs/enterprise_deployment.md) for detailed configuration options.

---

## Enterprise Database Configuration

SpiderFoot Enterprise supports both SQLite (default) and PostgreSQL for enterprise scalability:

### PostgreSQL Enterprise Setup

For high-volume enterprise deployments, configure PostgreSQL:

```bash
# Install PostgreSQL and dependencies
sudo apt-get install postgresql postgresql-contrib
pip3 install psycopg2-binary

# Create database and user
sudo -u postgres psql
CREATE DATABASE spiderfoot_enterprise;
CREATE USER spiderfootuser WITH PASSWORD 'secure_enterprise_password';
GRANT ALL PRIVILEGES ON DATABASE spiderfoot_enterprise TO spiderfootuser;
\q

# Configure SpiderFoot for PostgreSQL
python3 ./sf.py --init-db postgresql://spiderfootuser:secure_enterprise_password@localhost/spiderfoot_enterprise
```

### Advanced Storage Features

The enterprise storage engine provides:

- **Compression**: Automatic data compression for efficient storage
- **Indexing**: Optimized database indexes for fast query performance
- **Partitioning**: Automatic data partitioning for large datasets
- **Backup**: Automated backup and recovery capabilities
- **Monitoring**: Real-time storage performance metrics

---

## Community

Whether you're a contributor, user or just curious about SpiderFoot and OSINT in general, we'd love to have you join our community! SpiderFoot now has a [Discord server](https://discord.gg/vyvztrG) for seeking help from the community, requesting features or just general OSINT chit-chat.

---

## Writing Correlation Rules

We have a comprehensive write-up and reference of the correlation rule-set introduced in SpiderFoot 4.0 [here](/correlations/README.md).

Also take a look at the [template.yaml](/correlations/template.yaml) file for a walk through. The existing [37 rules](/correlations) are also quite readable and good as starting points for additional rules.

---

## Modules / Integrations

SpiderFoot has over 200 modules, most of which *don't require API keys*, and many of those that do require API keys *have a free tier*.

| Name     | Description | Type   |
|:---------| :-----------|:-------|
| 4chan | Search 4chan for mentions of the target. | Free API
[AbstractAPI](https://app.abstractapi.com/)|Look up domain, phone and IP address information from AbstractAPI.|Tiered API
[abuse.ch](https://www.abuse.ch)|Check if a host/domain, IP address or netblock is malicious according to Abuse.ch.|Free API
[AbuseIPDB](https://www.abuseipdb.com)|Check if an IP address is malicious according to AbuseIPDB.com blacklist.|Tiered API
Account Finder|Look for possible associated accounts on over 500 social and other websites such as Instagram, Reddit, etc.|Internal
[AdBlock Check](https://adblockplus.org/)|Check if linked pages would be blocked by AdBlock Plus.|Tiered API
[AdGuard DNS](https://adguard.com/)|Check if a host would be blocked by AdGuard DNS.|Free API
[Ahmia](https://ahmia.fi/)|Search Tor 'Ahmia' search engine for mentions of the target.|Free API
[AI Summary](https://github.com/poppopjmp/spiderfoot)|Generate AI-powered summaries of discovered data.|Internal
[AlienVault IP Reputation](https://cybersecurity.att.com/)|Check if an IP or netblock is malicious according to the AlienVault IP Reputation database.|Free API
[AlienVault OTX](https://otx.alienvault.com/)|Obtain information from AlienVault Open Threat Exchange (OTX)|Tiered API
[Aparat](https://www.aparat.com/)|Search Aparat for videos related to the target.|Free API
[Apple iTunes](https://itunes.apple.com/)|Search Apple iTunes for mobile apps.|Free API
[Archive.org](https://archive.org/)|Identifies historic versions of interesting files/pages from the Wayback Machine.|Free API
[ARIN](https://www.arin.net/)|Queries ARIN registry for contact information.|Free API
[Azure Blob Finder](https://azure.microsoft.com/en-in/services/storage/blobs/)|Search for potential Azure blobs associated with the target and attempt to list their contents.|Free API
[Bambenek](https://bambenekconsulting.com/)|Check if a netblock or IP is malicious according to Bambenek feeds.|Free API
Base64 Decoder|Identify Base64-encoded strings in URLs, often revealing interesting hidden information.|Internal
[BGPView](https://bgpview.io/)|Obtain network information from BGPView API.|Free API
[BinaryEdge](https://www.binaryedge.io/)|Obtain information from BinaryEdge.io Internet scanning systems, including breaches, vulnerabilities, torrents and passive DNS.|Tiered API
[Bing](https://www.bing.com/)|Obtain information from Bing to identify sub-domains and links.|Tiered API
[Bing (Shared IPs)](https://www.bing.com/)|Search Bing for hosts sharing the same IP.|Tiered API
Binary String Extractor|Attempt to identify strings in binary content.|Internal
Bitcoin Finder|Identify bitcoin addresses in scraped webpages.|Internal
[Bitcoin Who's Who](https://bitcoinwhoswho.com/)|Check for Bitcoin addresses against the Bitcoin Who's Who database of suspect/malicious addresses.|Tiered API
[Blockchain](https://www.blockchain.com/)|Queries blockchain.info to find the balance of identified bitcoin wallet addresses.|Free API
[blocklist.de](http://www.blocklist.de/en/index.html)|Check if a netblock or IP is malicious according to blocklist.de.|Free API
[Bluesky](https://bsky.app/)|Search Bluesky for mentions of the target.|Free API
[BNB](https://www.binance.com/)|Identify BNB addresses in scraped webpages.|Internal
[BotScout](https://botscout.com/)|Searches BotScout.com's database of spam-bot IP addresses and e-mail addresses.|Tiered API
[botvrij.eu](https://botvrij.eu/)|Check if a domain is malicious according to botvrij.eu.|Free API
[BuiltWith](https://builtwith.com/)|Query BuiltWith.com's Domain API for information about your target's web technology stack, e-mail addresses and more.|Tiered API
[C99](https://api.c99.nl/)|Queries the C99 API which offers various data (geo location, proxy detection, phone lookup, etc).|Commercial API
[CallerName](http://callername.com/)|Lookup US phone number location and reputation information.|Free API
[Censys](https://censys.io/)|Obtain host information from Censys.io.|Tiered API
[Certificate Transparency](https://crt.sh/)|Gather hostnames from historical certificates in crt.sh.|Free API
[CertSpotter](https://sslmate.com/certspotter/)|Gather information about SSL certificates from SSLMate CertSpotter API.|Tiered API
[CINS Army List](https://cinsscore.com/)|Check if a netblock or IP address is malicious according to Collective Intelligence Network Security (CINS) Army list.|Free API
[CIRCL.LU](https://www.circl.lu/)|Obtain information from CIRCL.LU's Passive DNS and Passive SSL databases.|Free API
[Cisco Umbrella](https://umbrella.cisco.com/)|Check if a domain is categorized as malicious or unsafe by Cisco Umbrella.|Tiered API
[Citadel](https://www.citadel.com/)|Search Citadel for threat intelligence.|Free API
[CleanBrowsing.org](https://cleanbrowsing.org/)|Check if a host would be blocked by CleanBrowsing.org DNS content filters.|Free API
[CleanTalk Spam List](https://cleantalk.org)|Check if a netblock or IP address is on CleanTalk.org's spam IP list.|Free API
[CloudFlare DNS](https://www.cloudflare.com/)|Check if a host would be blocked by CloudFlare DNS.|Free API
[CloudFront](https://aws.amazon.com/cloudfront/)|Check if a host is using CloudFront CDN.|Free API
[CoinBlocker Lists](https://zerodot1.gitlab.io/CoinBlockerListsWeb/)|Check if a domain appears on CoinBlocker lists.|Free API
[CommonCrawl](http://commoncrawl.org/)|Searches for URLs found through CommonCrawl.org.|Free API
[Comodo Secure DNS](https://www.comodo.com/secure-dns/)|Check if a host would be blocked by Comodo Secure DNS.|Tiered API
Company Name Extractor|Identify company names in any obtained data.|Internal
Cookie Extractor|Extract Cookies from HTTP headers.|Internal
Country Name Extractor|Identify country names in any obtained data.|Internal
Credit Card Number Extractor|Identify Credit Card Numbers in any data|Internal
[CriminalIP](https://www.criminalip.io/)|Look up domain, phone and IP address information from CriminalIP.|Tiered API
[Crobat API](https://sonar.omnisint.io/)|Search Crobat API for subdomains.|Free API
Cross-Referencer|Identify whether other domains are associated ('Affiliates') of the target by looking for links back to the target site(s).|Internal
[Certificate Transparency (crt.sh)](https://crt.sh/)|Gather hostnames from historical certificates in crt.sh.|Free API
[CRXcavator](https://crxcavator.io/)|Search CRXcavator for Chrome extensions.|Free API
Custom Threat Feed|Check if a host/domain, netblock, ASN or IP is malicious according to your custom feed.|Internal
[CyberCrime-Tracker.net](https://cybercrime-tracker.net/)|Check if a host/domain or IP address is malicious according to CyberCrime-Tracker.net.|Free API
[Debounce](https://debounce.io/)|Check whether an email is disposable|Free API
[Deepinfo](https://deepinfo.com/) | Search Deepinfo.com for historical DNS records, WHOIS data, and associated domains. | Tiered API
[Dehashed](https://www.dehashed.com/)|Gather breach data from Dehashed API.|Commercial API
[Dideo](https://dideo.ir/)|Search Dideo for videos related to the target.|Free API
[Digital Ocean Space Finder](https://www.digitalocean.com/products/spaces/)|Search for potential Digital Ocean Spaces associated with the target and attempt to list their contents.|Free API
[Discord](https://discord.com/)|Search Discord for mentions of the target.|Free API
DNS Brute-forcer|Attempts to identify hostnames through brute-forcing common names and iterations.|Internal
DNS Common SRV|Attempts to identify hostnames through brute-forcing common DNS SRV records.|Internal
[DNSDumpster](https://dnsdumpster.com/)|Passive subdomain enumeration using HackerTarget's DNSDumpster|Free API
[DNSGrep](https://opendata.rapid7.com/)|Obtain Passive DNS information from Rapid7 Sonar Project using DNSGrep API.|Free API
[DNS Neighbor](https://dnsneighbor.com/)|Attempt to reverse-resolve the IP addresses next to your target to see if they are related.|Internal
DNS Raw Records|Retrieves raw DNS records such as MX, TXT and others.|Internal
DNS Resolver|Resolves hosts and IP addresses identified, also extracted from raw content.|Internal
DNS Zone Transfer|Attempts to perform a full DNS zone transfer.|Internal
[DNS for Family](https://dnsforfamily.com/)|Check if a host would be blocked by DNS for Family.|Free API
[Douyin](https://www.douyin.com/)|Search Douyin for videos related to the target.|Free API
[DroneBL](https://dronebl.org/)|Query the DroneBL database for open relays, open proxies, vulnerable servers, etc.|Free API
[DuckDuckGo](https://duckduckgo.com/)|Query DuckDuckGo's API for descriptive information about your target.|Free API
E-Mail Address Extractor|Identify e-mail addresses in any obtained data.|Internal
[EmailCrawlr](https://emailcrawlr.com/)|Search EmailCrawlr for email addresses and phone numbers associated with a domain.|Tiered API
[EmailFormat](https://www.email-format.com/)|Look up e-mail addresses on email-format.com.|Free API
[EmailRep](https://emailrep.io/)|Search EmailRep.io for email address reputation.|Tiered API
[Emerging Threats](https://rules.emergingthreats.net/)|Check if a netblock or IP address is malicious according to EmergingThreats.net.|Free API
Error String Extractor|Identify common error messages in content like SQL errors, etc.|Internal
Ethereum Address Extractor|Identify ethereum addresses in scraped webpages.|Internal
[Etherscan](https://etherscan.io)|Queries etherscan.io to find the balance of identified ethereum wallet addresses.|Free API
File Metadata Extractor|Extracts meta data from documents and images.|Internal
[Flickr](https://www.flickr.com/)|Search Flickr for domains, URLs and emails related to the specified domain.|Free API
[Focsec](https://focsec.com/)|Look up IP address information from Focsec.|Tiered API
[Fofa](https://fofa.so/)|Look up domain, IP address, and other information from Fofa.|Tiered API
[Fortinet](https://www.fortiguard.com/)|Check if an IP address is malicious according to Fortinet.|Free API
[Fraudguard](https://fraudguard.io/)|Obtain threat information from Fraudguard.io|Tiered API
[F-Secure Riddler.io](https://riddler.io/)|Obtain network information from F-Secure Riddler.io API.|Commercial API
[FullContact](https://www.fullcontact.com)|Gather domain and e-mail information from FullContact.com API.|Tiered API
[FullHunt](https://fullhunt.io/)|Identify domain attack surface using FullHunt API.|Tiered API
[Github](https://github.com/)|Identify associated public code repositories on Github.|Free API
[GLEIF](https://search.gleif.org/)|Look up company information from Global Legal Entity Identifier Foundation (GLEIF).|Tiered API
[Google Maps](https://cloud.google.com/maps-platform/)|Identifies potential physical addresses and latitude/longitude coordinates.|Tiered API
[Google Object Storage Finder](https://cloud.google.com/storage)|Search for potential Google Object Storage buckets associated with the target and attempt to list their contents.|Free API
[Google SafeBrowsing](https://developers.google.com/safe-browsing/v4/lookup-api)|Check if the URL is included on any of the Safe Browsing lists.|Free API
[Google Search](https://developers.google.com/custom-search)|Obtain information from the Google Custom Search API to identify sub-domains and links.|Tiered API
[Gravatar](https://secure.gravatar.com/)|Retrieve user information from Gravatar API.|Free API
[Grayhat Warfare](https://buckets.grayhatwarfare.com/)|Find bucket names matching the keyword extracted from a domain from Grayhat API.|Tiered API
[Greensnow](https://greensnow.co/)|Check if a netblock or IP address is malicious according to greensnow.co.|Free API
[grep.app](https://grep.app/)|Search grep.app API for links and emails related to the specified domain.|Free API
[GreyNoise](https://greynoise.io/)|Obtain IP enrichment data from GreyNoise|Tiered API
[GreyNoise Community](https://greynoise.io/)|Obtain IP enrichment data from GreyNoise Community API|Tiered API
[HackerOne (Unofficial)](http://www.nobbd.de/)|Check external vulnerability scanning/reporting service h1.nobbd.de to see if the target is listed.|Free API
[HackerTarget](https://hackertarget.com/)|Search HackerTarget.com for hosts sharing the same IP.|Free API
Hash Extractor|Identify MD5 and SHA hashes in web content, files and more.|Internal
[HaveIBeenPwned](https://haveibeenpwned.com/)|Check HaveIBeenPwned.com for hacked e-mail addresses identified in breaches.|Commercial API
Honeypot|Identify honeypot systems related to the target.|Internal
Hosting Provider Identifier|Find out if any IP addresses identified fall within known 3rd party hosting ranges, e.g. Amazon, Azure, etc.|Internal
[Host.io](https://host.io)|Obtain information about domain names from host.io.|Tiered API
[Hunter.io](https://hunter.io/)|Check for e-mail addresses and names on hunter.io.|Tiered API
[Hybrid Analysis](https://www.hybrid-analysis.com)|Search Hybrid Analysis for domains and URLs related to the target.|Free API
IBAN Number Extractor|Identify International Bank Account Numbers (IBANs) in any data.|Internal
[Iknowwhatyoudownload.com](https://iknowwhatyoudownload.com/en/peer/)|Check iknowwhatyoudownload.com for IP addresses that have been using torrents.|Tiered API
[Instagram](https://www.instagram.com/)|Search Instagram for profiles related to the target.|Free API
[IntelligenceX](https://intelx.io/)|Obtain information from IntelligenceX about identified IP addresses, domains, e-mail addresses and phone numbers.|Tiered API
Interesting File Finder|Identifies potential files of interest, e.g. office documents, zip files.|Internal
[Internet Storm Center](https://isc.sans.edu)|Check if an IP address is malicious according to SANS ISC.|Free API
[ipapi.co](https://ipapi.co/)|Queries ipapi.co to identify geolocation of IP Addresses using ipapi.co API|Tiered API
[ipapi.com](https://ipapi.com/)|Queries ipapi.com to identify geolocation of IP Addresses using ipapi.com API|Tiered API
[IPInfo.io](https://ipinfo.io)|Identifies the physical location of IP addresses identified using ipinfo.io.|Tiered API
[IPQualityScore](https://www.ipqualityscore.com/)|Determine if target is malicious using IPQualityScore API|Tiered API
[ipregistry](https://ipregistry.co/)|Query the ipregistry.co database for reputation and geo-location.|Tiered API
[ipstack](https://ipstack.com/)|Identifies the physical location of IP addresses identified using ipstack.com.|Tiered API
[JsonWHOIS.com](https://jsonwhois.com)|Search JsonWHOIS.com for WHOIS records associated with a domain.|Tiered API
Junk File Finder|Looks for old/temporary and other similar files.|Internal
[Keybase](https://keybase.io/)|Obtain additional information about domain names and identified usernames.|Free API
[Koodous](https://koodous.com/apks/)|Search Koodous for mobile apps.|Tiered API
[LeakCheck](https://leakcheck.net/) | Check LeakCheck.net for data breaches associated with a domain or email address. | Free API
[LeakIX](https://leakix.net/)|Search LeakIX for host data leaks, open ports, software and geoip.|Free API
[Leak-Lookup](https://leak-lookup.com/)|Searches Leak-Lookup.com's database of breaches.|Free API
[Maltiverse](https://maltiverse.com)|Obtain information about any malicious activities involving IP addresses|Free API
[MalwarePatrol](https://www.malwarepatrol.net/)|Searches malwarepatrol.net's database of malicious URLs/IPs.|Tiered API
[MetaDefender](https://metadefender.opswat.com/)|Search MetaDefender API for IP address and domain IP reputation.|Tiered API
[Mnemonic PassiveDNS](https://www.mnemonic.no)|Obtain Passive DNS information from PassiveDNS.mnemonic.no.|Free API
[multiproxy.org Open Proxies](https://multiproxy.org/)|Check if an IP address is an open proxy according to multiproxy.org open proxy list.|Free API
[MySpace](https://myspace.com/)|Gather username and location from MySpace.com profiles.|Free API
[NameAPI](https://www.nameapi.org/)|Check whether an email is disposable|Tiered API
[Netlas](https://netlas.io/)|Look up domain and IP address information from Netlas API.|Tiered API
[NetworksDB](https://networksdb.io/)|Search NetworksDB.io API for IP address and domain information.|Tiered API
[NeutrinoAPI](https://www.neutrinoapi.com/)|Search NeutrinoAPI for phone location information, IP address information, and host reputation.|Tiered API
[numverify](http://numverify.com/)|Lookup phone number location and carrier information from numverify.com.|Tiered API
[Onion.link](https://onion.link/)|Search Tor 'Onion City' search engine for mentions of the target domain using Google Custom Search.|Free API
[Onionsearchengine.com](https://as.onionsearchengine.com)|Search Tor onionsearchengine.com for mentions of the target domain.|Free API
[Onyphe](https://www.onyphe.io)|Check Onyphe data (threat list, geo-location, pastries, vulnerabilities)  about a given IP.|Tiered API
[Open Bug Bounty](https://www.openbugbounty.org/)|Check external vulnerability scanning/reporting service openbugbounty.org to see if the target is listed.|Free API
[OpenCorporates](https://opencorporates.com)|Look up company information from OpenCorporates.|Tiered API
[OpenDNS](https://www.opendns.com/)|Check if a host would be blocked by OpenDNS.|Free API
[OpenNIC DNS](https://www.opennic.org/)|Resolves host names in the OpenNIC alternative DNS system.|Free API
[OpenPhish](https://openphish.com/)|Check if a host/domain is malicious according to OpenPhish.com.|Free API
[OpenStreetMap](https://www.openstreetmap.org/)|Retrieves latitude/longitude coordinates for physical addresses from OpenStreetMap API.|Free API
[OpenWiFiMap](https://openwifimap.com/)|Search OpenWiFiMap for WiFi hotspots related to the target.|Free API
Page Information|Obtain information about web pages (do they take passwords, do they contain forms, etc.)|Internal
[PasteBin](https://pastebin.com/)|PasteBin search (via Google Search API) to identify related content.|Tiered API
PGP Key Servers|Look up domains and e-mail addresses in PGP public key servers.|Internal
[PhishStats](https://phishstats.info/)|Check if a netblock or IP address is malicious according to PhishStats.|Free API
[PhishTank](https://phishtank.com/)|Check if a host/domain is malicious according to PhishTank.|Free API
Phone Number Extractor|Identify phone numbers in scraped webpages.|Internal
Port Scanner - TCP|Scans for commonly open TCP ports on Internet-facing systems.|Internal
[Project Honey Pot](https://www.projecthoneypot.org/)|Query the Project Honey Pot database for IP addresses.|Free API
[ProjectDiscovery Chaos](https://chaos.projectdiscovery.io)|Search for hosts/subdomains using chaos.projectdiscovery.io|Commercial API
[Psbdmp](https://psbdmp.cc/)|Check psbdmp.cc (PasteBin Dump) for potentially hacked e-mails and domains.|Free API
[Pulsedive](https://pulsedive.com/)|Obtain information from Pulsedive's API.|Tiered API
[PunkSpider](https://punkspider.io/)|Check the QOMPLX punkspider.io service to see if the target is listed as vulnerable.|Free API
[Quad9](https://quad9.net/)|Check if a host would be blocked by Quad9 DNS.|Free API
[Recorded Future](https://www.recordedfuture.com/)|Obtain threat intelligence from Recorded Future.|Commercial API
[Reddit](https://www.reddit.com/)|Search Reddit for mentions of the target.|Free API
[ReverseWhois](https://www.reversewhois.io/)|Reverse Whois lookups using reversewhois.io.|Free API
[RIPE](https://www.ripe.net/)|Queries the RIPE registry (includes ARIN data) to identify netblocks and other info.|Free API
[Robtex](https://www.robtex.com/)|Search Robtex.com for hosts sharing the same IP.|Free API
[Rocket.Chat](https://rocket.chat/)|Search Rocket.Chat for mentions of the target.|Free API
[RocketReach](https://rocketreach.co/)|Look up email addresses, phone numbers, and social media profiles from RocketReach.|Tiered API
[Rubika](https://rubika.ir/)|Search Rubika for mentions of the target.|Free API
[S3 Bucket Finder](https://aws.amazon.com/s3/)|Search for potential Amazon S3 buckets associated with the target and attempt to list their contents.|Free API
[searchcode](https://searchcode.com/)|Search searchcode for code repositories mentioning the target domain.|Free API
[SecurityTrails](https://securitytrails.com/)|Obtain Passive DNS and other information from SecurityTrails|Tiered API
[Seon](https://seon.io/)|Queries seon.io to gather intelligence about IP Addresses, email addresses, and phone numbers|Commercial API
[SHODAN](https://www.shodan.io/)|Obtain information from SHODAN about identified IP addresses.|Tiered API
Similar Domain Finder|Search various sources to identify similar looking domain names, for instance squatted domains.|Internal
[Skymem](http://www.skymem.info/)|Look up e-mail addresses on Skymem.|Free API
[SlideShare](https://www.slideshare.net)|Gather name and location from SlideShare profiles.|Free API
[Snov](https://snov.io/)|Gather available email IDs from identified domains|Tiered API
[Social Links](https://sociallinks.io/)|Queries SocialLinks.io to gather intelligence from social media platforms and dark web.|Commercial API
[Social Media Profile Finder](https://developers.google.com/custom-search)|Tries to discover the social media profiles for human names identified.|Tiered API
Social Network Identifier|Identify presence on social media networks such as LinkedIn, Twitter and others.|Internal
[SORBS](http://www.sorbs.net/)|Query the SORBS database for open relays, open proxies, vulnerable servers, etc.|Free API
[SpamCop](https://www.spamcop.net/)|Check if a netblock or IP address is in the SpamCop database.|Free API
[Spamhaus Zen](https://www.spamhaus.org/)|Check if a netblock or IP address is in the Spamhaus Zen database.|Free API
[spur.us](https://spur.us/)|Obtain information about any malicious activities involving IP addresses found|Commercial API
SSL Certificate Analyzer|Gather information about SSL certificates used by the target's HTTPS sites.|Internal
[StackOverflow](https://www.stackexchange.com)|Search StackOverflow for any mentions of a target domain. Returns potentially related information.|Tiered API
[Steven Black Hosts](https://github.com/StevenBlack/hosts)|Check if a domain is malicious (malware or adware) according to Steven Black Hosts list.|Free API
Strange Header Identifier|Obtain non-standard HTTP headers returned by web servers.|Internal
Subdomain Takeover Checker|Check if affiliated subdomains are vulnerable to takeover.|Internal
[Sublist3r PassiveDNS](https://api.sublist3r.com)|Passive subdomain enumeration using Sublist3r's API|Free API
[SURBL](http://www.surbl.org/)|Check if a netblock, IP address or domain is in the SURBL blacklist.|Free API
[Talos Intelligence](https://talosintelligence.com/)|Check if a netblock or IP address is malicious according to TalosIntelligence.|Free API
[Telegram](https://telegram.org/)|Search Telegram for mentions of the target.|Free API
[TextMagic](https://www.textmagic.com/)|Obtain phone number type from TextMagic API|Tiered API
[ThreatCrowd](https://www.threatcrowd.org)|Obtain information from ThreatCrowd about identified IP addresses, domains and e-mail addresses.|Free API
[ThreatFox](https://threatfox.abuse.ch)|Check if an IP address is malicious according to ThreatFox.|Free API
[ThreatMiner](https://www.threatminer.org/)|Obtain information from ThreatMiner's database for passive DNS and threat intelligence.|Free API
TLD Searcher|Search all Internet TLDs for domains with the same name as the target (this can be very slow.)|Internal
[Tool - CMSeeK]([https://github.com/Tuhinshubhra/CMSeeK](https://github.com/Tuhinshubhra/CMSeeK))|Identify what Content Management System (CMS) might be used.|Tool
[Tool - DNSTwist]([https://github.com/elceef/dnstwist](https://github.com/elceef/dnstwist))|Identify bit-squatting, typo and other similar domains to the target using a local DNSTwist installation.|Tool
[Tool - Gobuster]([https://github.com/OJ/gobuster](https://github.com/OJ/gobuster))|Directory brute-forcing using Gobuster.|Tool
[Tool - nbtscan]([http://www.unixwiz.net/tools/nbtscan.html](http://www.unixwiz.net/tools/nbtscan.html))|Scans for open NETBIOS nameservers on your target's network.|Tool
[Tool - Nmap]([https://nmap.org/](https://nmap.org/))|Identify what Operating System might be used.|Tool
[Tool - Nuclei]([https://nuclei.projectdiscovery.io/](https://nuclei.projectdiscovery.io/))|Fast and customisable vulnerability scanner.|Tool
[Tool - onesixtyone]([https://github.com/trailofbits/onesixtyone](https://github.com/trailofbits/onesixtyone))|Fast scanner to find publicly exposed SNMP services.|Tool
[Tool - Retire.js]([http://retirejs.github.io/retire.js/](http://retirejs.github.io/retire.js/))|Scanner detecting the use of JavaScript libraries with known vulnerabilities|Tool
[Tool - snallygaster]([https://github.com/hannob/snallygaster](https://github.com/hannob/snallygaster))|Finds file leaks and other security problems on HTTP servers.|Tool
[Tool - testssl.sh]([https://testssl.sh](https://testssl.sh))|Identify various TLS/SSL weaknesses, including Heartbleed, CRIME and ROBOT.|Tool
[Tool - TruffleHog]([https://github.com/trufflesecurity/truffleHog](https://github.com/trufflesecurity/truffleHog))|Searches through git repositories for high entropy strings and secrets, digging deep into commit history.|Tool
[Tool - WAFW00F]([https://github.com/EnableSecurity/wafw00f](https://github.com/EnableSecurity/wafw00f))|Identify what web application firewall (WAF) is in use on the specified website.|Tool
[Tool - Wappalyzer]([https://www.wappalyzer.com/](https://www.wappalyzer.com/))|Wappalyzer identifies technologies on websites.|Tool
[Tool - WhatWeb]([https://github.com/urbanadventurer/whatweb](https://github.com/urbanadventurer/whatweb))|Identify what software is in use on the specified website.|Tool
[TOR Exit Nodes](https://metrics.torproject.org/)|Check if an IP adddress or netblock appears on the Tor Metrics exit node list.|Free API
[TORCH](https://torchsearch.wordpress.com/)|Search Tor 'TORCH' search engine for mentions of the target domain.|Free API
[Tron](https://tron.network/)|Search Tron for mentions of the target.|Free API
[Trumail](https://trumail.io/)|Check whether an email is disposable|Free API
[Twilio](https://www.twilio.com/)|Obtain information from Twilio about phone numbers. Ensure you have the Caller Name add-on installed in Twilio.|Tiered API
[Twitter](https://twitter.com/)|Gather name and location from Twitter profiles.|Free API
[UCEPROTECT](http://www.uceprotect.net/)|Check if a netblock or IP address is in the UCEPROTECT database.|Free API
[Unwired Labs](https://unwiredlabs.com/)|Obtain geolocation data from Unwired Labs.|Tiered API
[URLScan.io](https://urlscan.io/)|Search URLScan.io cache for domain information.|Free API
[Venmo](https://venmo.com/)|Gather user information from Venmo API.|Free API
[ViewDNS.info](https://viewdns.info/)|Identify co-hosted websites and perform reverse Whois lookups using ViewDNS.info.|Tiered API
[VirusTotal](https://www.virustotal.com/)|Obtain information from VirusTotal about identified IP addresses.|Tiered API
[VoIP Blacklist (VoIPBL)](https://voipbl.org/)|Check if an IP address or netblock is malicious according to VoIP Blacklist (VoIPBL).|Free API
[VXVault.net](http://vxvault.net/)|Check if a domain or IP address is malicious according to VXVault.net.|Free API
Web Analytics Extractor|Identify web analytics IDs in scraped webpages and DNS TXT records.|Internal
Web Framework Identifier|Identify the usage of popular web frameworks like jQuery, YUI and others.|Internal
Web Server Identifier|Obtain web server banners to identify versions of web servers being used.|Internal
Web Spider|Spidering of web-pages to extract content for searching.|Internal
[WeChat](https://www.wechat.com/)|Search WeChat for mentions of the target.|Free API
[WhatCMS](https://whatcms.org/)|Check web technology using WhatCMS.org API.|Tiered API
[WhatsApp](https://www.whatsapp.com/)|Search WhatsApp for mentions of the target.|Free API
Whois|Perform a WHOIS look-up on domain names and owned netblocks.|Internal
[WhoisFreaks](https://whoisfreaks.com/) | Perform WHOIS lookups and identify historical WHOIS records using WhoisFreaks.com. | Tiered API
[Whoisology](https://whoisology.com/)|Reverse Whois lookups using Whoisology.com.|Commercial API
[Whoxy](https://www.whoxy.com/)|Reverse Whois lookups using Whoxy.com.|Commercial API
[WiGLE](https://wigle.net/)|Query WiGLE to identify nearby WiFi access points.|Free API
[Wikileaks](https://wikileaks.org/)|Search Wikileaks for mentions of domain names and e-mail addresses.|Free API
[Wikipedia Edits](https://www.wikipedia.org/)|Identify edits to Wikipedia articles made from a given IP address or username.|Free API
[XForce Exchange](https://exchange.xforce.ibmcloud.com/)|Obtain IP reputation and passive DNS information from IBM X-Force Exchange.|Tiered API
[Xiaohongshu](https://www.xiaohongshu.com/)|Search Xiaohongshu for mentions of the target.|Free API
[Yandex DNS](https://yandex.com/)|Check if a host would be blocked by Yandex DNS.|Free API
[Zetalytics](https://zetalytics.com/)|Query the Zetalytics database for hosts on your target domain(s).|Tiered API
[ZoneFiles.io](https://zonefiles.io)|Search ZoneFiles.io Domain query API for domain information.|Tiered API
[Zone-H Defacement Check](https://zone-h.org/)|Check if a hostname/domain appears on the zone-h.org 'special defacements' RSS feed.|Free API
[ZoomEye](https://www.zoomeye.org/)|Look up domain, IP address, and other information from ZoomEye.|Tiered API

---

## Documentation

Read more at the [project website](https://github.com/poppopjmp/spiderfoot/wiki), including more complete documentation, blog posts with tutorials/guides.

---

## Active Maintenance Status

SpiderFoot is actively maintained with regular updates and contributions. The project is under active development, with recent commits and ongoing improvements. Issues and pull requests are actively managed and addressed. The community is engaged through discussions and contributions. We encourage users to report issues and contribute to the project.

Maintainer: Poppopjmp <van1sh@van1shland.io>

---

## Recent Updates

- Added new modules for enhanced data extraction and analysis.
- Improved performance and stability of existing modules.
- Updated dependencies to ensure compatibility with the latest versions.
- Fixed various bugs and issues reported by the community.
- Enhanced documentation and added new tutorials for better user experience.
- Added initial support for Postgresql
- Container Autocreation
- Testing Integration
- Codecoverage and quality

---

## Version Management

SpiderFoot uses a centralized version management system to ensure consistency across all components:

- **Single Source of Truth**: All versions controlled from the `VERSION` file
- **Automated Updates**: Use `python update_version.py` to update all version references
- **Consistency Checking**: Validate version consistency with `python update_version.py --check`
- **Release Management**: Streamlined version bumping with `python update_version.py --set X.Y.Z`

For detailed information, see the [Version Management Guide](docs/VERSION_MANAGEMENT.md).

---

## Triggering a Release Build

To trigger a release build manually using the GitHub Actions workflow, follow these steps:

1. Go to the GitHub repository page.
2. Click on the "Actions" tab.
3. In the left sidebar, click on the "Release" workflow.
4. Click on the "Run workflow" button.
5. Select the branch you want to release from (e.g., `main`).
6. Click on the "Run workflow" button to start the release build process.

The GitHub Actions workflow will handle the rest, including checking out the repository, setting up Python, installing dependencies, running tests, building the Docker image, and pushing the Github Content Registry

---

## REST API Usage

The SpiderFoot REST API allows you to interact with SpiderFoot programmatically. The API provides endpoints for starting scans, stopping scans, retrieving scan results, listing available modules, listing active scans, getting scan status, listing scan history, exporting scan results, importing API keys, and exporting API keys.

### Available Endpoints

- `GET /api/scan/start`: Start a new scan
- `POST /api/scan/stop`: Stop an ongoing scan
- `GET /api/scan/results`: Retrieve scan results
- `GET /api/modules`: List available modules
- `GET /api/scans/active`: List active scans
- `GET /api/scan/status`: Get the status of a specific scan
- `GET /api/scans/history`: List the history of all scans performed
- `GET /api/scan/export`: Export scan results in various formats (e.g., CSV, JSON)
- `POST /api/keys/import`: Import API keys for various modules
- `GET /api/keys/export`: Export API keys for various modules

### Example Usage

To start a new scan, send a `GET` request to the `/api/scan/start` endpoint with the required parameters:

```bash
curl -X GET "http://127.0.0.1:8000/api/scan/start?target=example.com&modules=module1,module2"
```

To stop an ongoing scan, send a `POST` request to the `/api/scan/stop` endpoint with the scan ID:

```bash
curl -X POST "http://127.0.0.1:8000/api/scan/stop" -d '{"scan_id": "12345"}'
```

To retrieve scan results, send a `GET` request to the `/api/scan/results` endpoint with the scan ID:

```bash
curl -X GET "http://127.0.0.1:8000/api/scan/results?scan_id=12345"
```

For more detailed instructions and examples, refer to the API documentation.

---

*For more diagrams and visualizations, see the documentation and web UI dashboards!*
