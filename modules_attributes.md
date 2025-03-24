# SpiderFoot Modules and Their Attributes

This document lists all SpiderFoot modules and their attributes, such as `useCases`, `categories`, and others.

## Modules

### sfp_openphish
- **Name**: OpenPhish
- **Summary**: Check if a host/domain is malicious according to OpenPhish.com.
- **Use Cases**: Investigate, Passive
- **Categories**: Reputation Systems

### sfp_dnsraw
- **Name**: DNS Raw Records
- **Summary**: Retrieves raw DNS records such as MX, TXT, and others.
- **Use Cases**: Footprint, Investigate, Passive
- **Categories**: DNS

### sfp_openbugbounty
- **Name**: Open Bug Bounty
- **Summary**: Check external vulnerability scanning/reporting service openbugbounty.org to see if the target is listed.
- **Use Cases**: Footprint, Investigate, Passive
- **Categories**: Leaks, Dumps and Breaches

### sfp_email
- **Name**: E-Mail Address Extractor
- **Summary**: Identify e-mail addresses in any obtained data.
- **Use Cases**: Passive, Investigate, Footprint
- **Categories**: Content Analysis

### sfp_ipapicom
- **Name**: ipapi.com
- **Summary**: Queries ipapi.com to identify geolocation of IP Addresses using ipapi.com API.
- **Use Cases**: Footprint, Investigate, Passive
- **Categories**: Real World