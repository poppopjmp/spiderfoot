# SpiderFoot Event Type Catalog

Complete reference of all standard event types used by SpiderFoot v6.
Modules consume and produce these events to build an intelligence
graph during scans.

## How Events Work

Events are the fundamental unit of data in SpiderFoot. Each event has:

- **Type** — A string identifier (e.g., `DOMAIN_NAME`)
- **Data** — The actual content (e.g., `example.com`)
- **Source** — The parent event that triggered this one
- **Module** — Which module produced this event

Events form a tree starting from the root target.

## Event Types by Category

### Network & Infrastructure

| Event Type | Description |
|-----------|-------------|
| `DOMAIN_NAME` | A domain name (e.g., example.com) |
| `DOMAIN_WHOIS` | WHOIS registration data for a domain |
| `DOMAIN_REGISTRAR` | Domain registrar name |
| `INTERNET_NAME` | A hostname found during scanning |
| `INTERNET_NAME_UNRESOLVED` | A hostname that could not be resolved |
| `IP_ADDRESS` | An IPv4 or IPv6 address |
| `IPV6_ADDRESS` | An IPv6 address specifically |
| `NETBLOCK_OWNER` | Owner of a network block |
| `NETBLOCK_MEMBER` | IP belongs to a known netblock |
| `BGP_AS_OWNER` | Owner of a BGP Autonomous System |
| `BGP_AS_MEMBER` | AS membership information |
| `BGP_AS_PEER` | BGP peering relationship |

### DNS Records

| Event Type | Description |
|-----------|-------------|
| `DNS_TEXT` | DNS TXT record content |
| `DNS_SPF` | SPF record for email authentication |
| `DNS_A` | DNS A record (domain → IPv4) |
| `DNS_AAAA` | DNS AAAA record (domain → IPv6) |
| `DNS_MX` | DNS MX record (mail server) |
| `DNS_NS` | DNS NS record (nameserver) |
| `DNS_CNAME` | DNS CNAME record (alias) |
| `DNS_SOA` | DNS SOA record (start of authority) |

### Web & HTTP

| Event Type | Description |
|-----------|-------------|
| `LINKED_URL_INTERNAL` | Internal URL found on the target |
| `LINKED_URL_EXTERNAL` | External URL found on the target |
| `URL_FORM` | URL of an HTML form |
| `URL_UPLOAD` | URL of a file upload endpoint |
| `URL_JAVASCRIPT` | URL of a JavaScript file |
| `URL_STATIC_CONTENT` | URL of static content (CSS, images) |
| `HTTP_CODE` | HTTP response status code |
| `WEBSERVER_BANNER` | Web server identification banner |
| `WEBSERVER_HTTPHEADERS` | HTTP response headers |
| `WEBSERVER_TECHNOLOGY` | Detected web technology/framework |
| `WEB_ANALYTICS_ID` | Web analytics tracking ID |

### Security & Vulnerabilities

| Event Type | Description |
|-----------|-------------|
| `VULNERABILITY_GENERAL` | Generic vulnerability finding |
| `VULNERABILITY_CVE_CRITICAL` | Critical severity CVE |
| `VULNERABILITY_CVE_HIGH` | High severity CVE |
| `VULNERABILITY_CVE_MEDIUM` | Medium severity CVE |
| `VULNERABILITY_CVE_LOW` | Low severity CVE |
| `VULNERABILITY_DISCLOSURE` | Vulnerability disclosure information |
| `BLACKLISTED_IPADDR` | IP address found on blacklists |
| `BLACKLISTED_AFFILIATE_IPADDR` | Affiliated IP on blacklists |
| `BLACKLISTED_SUBNET` | Subnet found on blacklists |
| `BLACKLISTED_NETBLOCK` | Netblock found on blacklists |
| `MALICIOUS_IPADDR` | Known malicious IP address |
| `MALICIOUS_AFFILIATE_IPADDR` | Affiliated malicious IP |

### SSL/TLS Certificates

| Event Type | Description |
|-----------|-------------|
| `SSL_CERTIFICATE_RAW` | Raw SSL/TLS certificate data |
| `SSL_CERTIFICATE_ISSUED` | Certificate issuance details |
| `SSL_CERTIFICATE_ISSUER` | Certificate issuer (CA) |
| `SSL_CERTIFICATE_MISMATCH` | Certificate hostname mismatch |
| `SSL_CERTIFICATE_EXPIRED` | Expired SSL certificate |
| `SSL_CERTIFICATE_EXPIRING` | Certificate expiring soon |

### People & Contact Info

| Event Type | Description |
|-----------|-------------|
| `EMAILADDR` | Email address |
| `EMAILADDR_COMPROMISED` | Email found in breach data |
| `PHONE_NUMBER` | Phone number |
| `PHYSICAL_ADDRESS` | Physical/postal address |
| `HUMAN_NAME` | A person's name |
| `USERNAME` | Online username/handle |
| `SOCIAL_MEDIA` | Social media profile URL |
| `ACCOUNT_EXTERNAL_OWNED` | External account owned by target |

### Data Leaks & Breaches

| Event Type | Description |
|-----------|-------------|
| `LEAKSITE_CONTENT` | Content from a data leak site |
| `LEAKSITE_URL` | URL of a leak/paste site |
| `PASSWORD_COMPROMISED` | Compromised password (hashed) |
| `DARKNET_MENTION_URL` | Dark web mention URL |
| `DARKNET_MENTION_CONTENT` | Dark web mention content |

### Geolocation

| Event Type | Description |
|-----------|-------------|
| `GEOINFO` | Geographic location information |
| `COUNTRY_NAME` | Country associated with target |
| `PROVIDER_HOSTING` | Hosting provider information |

### Miscellaneous

| Event Type | Description |
|-----------|-------------|
| `AFFILIATE_DOMAIN_NAME` | Domain affiliated with target |
| `AFFILIATE_IPADDR` | IP address affiliated with target |
| `CO_HOSTED_SITE` | Website co-hosted on same IP |
| `SIMILARDOMAIN` | Similar/typosquat domain |
| `RAW_RIR_DATA` | Raw Regional Internet Registry data |
| `RAW_DNS_RECORDS` | Raw DNS record data |
| `RAW_FILE_META_DATA` | Metadata extracted from files |
| `SEARCH_ENGINE_WEB_CONTENT` | Search engine result content |
| `TARGET_WEB_CONTENT` | Content from target website |
| `BASE64_DATA` | Base64-encoded data found |
| `HASH` | Cryptographic hash value |
| `SOFTWARE_USED` | Software identified on target |

## Creating Custom Event Types

If the standard types don't cover your needs:

```python
from spiderfoot.api.api_devtools import APIIntrospector

intro = APIIntrospector()
intro.register_event_type(
    "CUSTOM_IOC",
    "Custom Indicator of Compromise"
)
```

Custom event types should:

1. Use UPPER_SNAKE_CASE
2. Be specific to the data type
3. Not duplicate existing types
4. Start with a category prefix when possible

## Event Type Statistics

- **Total standard types:** 68+
- **Categories covered:** Network, DNS, Web, Security, SSL, People,
  Data Leaks, Geolocation
- **Module coverage:** Most types are produced by 2-5 modules

---

*SpiderFoot v6 — Event Type Catalog*
