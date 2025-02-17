# SpiderFoot Documentation

## Overview

SpiderFoot is an open source intelligence (OSINT) automation tool. It integrates with just about every data source available and utilizes a range of methods for data analysis, making that data easy to navigate. SpiderFoot has an embedded web-server for providing a clean and intuitive web-based interface but can also be used completely via the command-line. It's written in Python 3 and MIT-licensed.

## Features

- Web based UI or CLI
- Over 200 modules
- Python 3.7+
- YAML-configurable correlation engine with 37 pre-defined rules
- CSV/JSON/GEXF export
- API key export/import
- SQLite back-end for custom querying
- Highly configurable
- Fully documented
- Visualizations
- TOR integration for dark web searching
- Dockerfile for Docker-based deployments
- Can call other tools like DNSTwist, Whatweb, Nmap and CMSeeK
- Actively developed since 2012

## Installation

To install and run SpiderFoot, you need at least Python 3.7 and a number of Python libraries which you can install with `pip`. We recommend you install a packaged release since master will often have bleeding edge features and modules that aren't fully tested.

### Stable build (packaged release):

```
 wget https://github.com/smicallef/spiderfoot/archive/v4.0.tar.gz
 tar zxvf v4.0.tar.gz
 cd spiderfoot-4.0
 pip3 install -r requirements.txt
 python3 ./sf.py -l 127.0.0.1:5001
```

### Development build (cloning git master branch):

```
 git clone https://github.com/smicallef/spiderfoot.git
 cd spiderfoot
 pip3 install -r requirements.txt
 python3 ./sf.py -l 127.0.0.1:5001
```

## Usage

SpiderFoot can be used offensively (e.g. in a red team exercise or penetration test) for reconnaissance of your target or defensively to gather information about what you or your organization might have exposed over the Internet.

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

- Host/sub-domain/TLD enumeration/extraction
- Email address, phone number and human name extraction
- Bitcoin and Ethereum address extraction
- Check for susceptibility to sub-domain hijacking
- DNS zone transfers
- Threat intelligence and Blacklist queries
- API integration with SHODAN, HaveIBeenPwned, GreyNoise, AlienVault, SecurityTrails, etc.
- Social media account enumeration
- S3/Azure/Digitalocean bucket enumeration/scraping
- IP geo-location
- Web scraping, web content analysis
- Image, document and binary file meta data analysis
- Dark web searches
- Port scanning and banner grabbing
- Data breach searches
- So much more...

## Documentation

Read more at the [project website](https://www.spiderfoot.net/r.php?u=aHR0cHM6Ly93d3cuc3BpZGVyZm9vdC5uZXQv&s=os_gh), including more complete documentation, blog posts with tutorials/guides, plus information about [SpiderFoot HX](https://www.spiderfoot.net/r.php?u=aHR0cHM6Ly93d3cuc3BpZGVyZm9vdC5uZXQvaHgvCg==&s=os_gh).

Latest updates announced on [Twitter](https://twitter.com/spiderfoot).

## Community

Whether you're a contributor, user or just curious about SpiderFoot and OSINT in general, we'd love to have you join our community! SpiderFoot now has a [Discord server](https://discord.gg/vyvztrG) for seeking help from the community, requesting features or just general OSINT chit-chat.

## Maintainers

Steve Micallef <steve@binarypool.com>
Poppopjmp <van1sh@van1shland.io>
