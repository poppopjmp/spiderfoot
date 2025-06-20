# Module Documentation Index

SpiderFoot includes over 200 modules for gathering intelligence from various sources. This index provides an overview of all available modules, organized by category and functionality.

## Module Categories

### DNS and Network
| Module | Description | Type | API Key Required |
|--------|-------------|------|------------------|
| sfp_dnsresolve | DNS resolution and reverse DNS | Passive | No |
| sfp_whois | WHOIS information lookup | Passive | No |
| sfp_ssl | SSL certificate analysis | Passive | No |
| sfp_portscan_tcp | TCP port scanning | Active | No |
| sfp_banner | Service banner grabbing | Active | No |
| sfp_netblocks | Network block enumeration | Passive | No |
| sfp_bgp | BGP information lookup | Passive | No |
| sfp_asn | ASN information gathering | Passive | No |

### Threat Intelligence
| Module | Description | Type | API Key Required |
|--------|-------------|------|------------------|
| sfp_virustotal | VirusTotal API integration | Passive | Yes |
| sfp_threatcrowd | ThreatCrowd threat intelligence | Passive | No |
| sfp_alienvault | AlienVault OTX integration | Passive | Yes |
| sfp_malware | Malware analysis platforms | Passive | Varies |
| sfp_botnet | Botnet detection | Passive | No |
| sfp_reputation | IP/domain reputation services | Passive | Varies |
| sfp_blacklist | Blacklist checking | Passive | No |
| sfp_greynoise | GreyNoise API integration | Passive | Yes |

### Search Engines
| Module | Description | Type | API Key Required |
|--------|-------------|------|------------------|
| sfp_google | Google search results | Passive | Yes |
| sfp_bing | Bing search results | Passive | Yes |
| sfp_duckduckgo | DuckDuckGo search | Passive | No |
| sfp_yandex | Yandex search engine | Passive | No |
| sfp_shodan | Shodan internet device search | Passive | Yes |
| sfp_censys | Censys internet scanning | Passive | Yes |
| sfp_binaryedge | BinaryEdge API integration | Passive | Yes |

### Social Media
| Module | Description | Type | API Key Required |
|--------|-------------|------|------------------|
| sfp_social | Social media profile discovery | Passive | No |
| sfp_twitter | Twitter account enumeration | Passive | Yes |
| sfp_linkedin | LinkedIn profile discovery | Passive | No |
| sfp_instagram | Instagram account lookup | Passive | No |
| sfp_github | GitHub repository search | Passive | Yes |
| sfp_gitlab | GitLab repository search | Passive | No |
| sfp_bitbucket | Bitbucket repository search | Passive | No |

### Data Breaches
| Module | Description | Type | API Key Required |
|--------|-------------|------|------------------|
| sfp_haveibeen | HaveIBeenPwned integration | Passive | Yes |
| sfp_hunter | Hunter.io email discovery | Passive | Yes |
| sfp_emailrep | Email reputation checking | Passive | Yes |
| sfp_breachcomp | Breach compilation checking | Passive | No |
| sfp_leak | Data leak detection | Passive | No |

### Web Analysis
| Module | Description | Type | API Key Required |
|--------|-------------|------|------------------|
| sfp_spider | Web crawling and spidering | Active | No |
| sfp_webheader | HTTP header analysis | Active | No |
| sfp_robots | robots.txt analysis | Passive | No |
| sfp_sitedossier | Site analysis and reports | Passive | No |
| sfp_webframework | Web framework detection | Active | No |
| sfp_whatweb | Web technology identification | Active | No |

### Cloud Services
| Module | Description | Type | API Key Required |
|--------|-------------|------|------------------|
| sfp_aws | Amazon Web Services enumeration | Passive | No |
| sfp_azure | Microsoft Azure enumeration | Passive | No |
| sfp_gcp | Google Cloud Platform enumeration | Passive | No |
| sfp_s3bucket | S3 bucket enumeration | Passive | No |
| sfp_cloudflare | Cloudflare service detection | Passive | No |

### Domain Intelligence
| Module | Description | Type | API Key Required |
|--------|-------------|------|------------------|
| sfp_subdomain_enum | Subdomain enumeration | Active | No |
| sfp_dnsbrute | DNS brute forcing | Active | No |
| sfp_dnstake | DNS takeover detection | Active | No |
| sfp_securitytrails | SecurityTrails API integration | Passive | Yes |
| sfp_passivetotal | PassiveTotal integration | Passive | Yes |
| sfp_riskiq | RiskIQ API integration | Passive | Yes |

## Module Usage Examples

### Basic Module Usage

```bash
# Single module
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Multiple modules
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois

# All modules in category
python sf.py -s example.com -t DOMAIN_NAME -m dns
```

### Workflow Module Usage

```bash
# Passive reconnaissance
python sfworkflow.py multi-scan ws_123 \
  --modules sfp_dnsresolve,sfp_whois,sfp_ssl,sfp_threatcrowd

# Active scanning
python sfworkflow.py multi-scan ws_123 \
  --modules sfp_portscan_tcp,sfp_spider,sfp_subdomain_enum

# Threat intelligence
python sfworkflow.py multi-scan ws_123 \
  --modules sfp_virustotal,sfp_alienvault,sfp_greynoise
```

## Module Configuration

### Global Module Settings

```ini
[modules]
# Default timeouts
*.timeout = 30

# Verification settings
*.verify = true

# Rate limiting
*.delay = 1
```

### Category-Specific Settings

```ini
# DNS modules
sfp_dnsresolve.servers = 8.8.8.8,1.1.1.1
sfp_dnsresolve.timeout = 30

# Scanning modules
sfp_portscan_tcp.maxports = 1000
sfp_portscan_tcp.randomize = true

# Web modules
sfp_spider.maxpages = 100
sfp_spider.maxdirs = 50
```

## API Key Management

### Required API Keys

#### Essential Services
- **VirusTotal**: Malware and threat intelligence
- **Shodan**: Internet device discovery
- **Hunter.io**: Email discovery and verification

#### Recommended Services
- **SecurityTrails**: DNS and domain intelligence
- **PassiveTotal**: Threat intelligence and DNS
- **GreyNoise**: Internet scanning intelligence

#### Free Alternatives
- **ThreatCrowd**: Free threat intelligence
- **HackerTarget**: Free security tools
- **DNS Dumpster**: Domain intelligence

### API Key Configuration

```ini
[modules]
# Essential APIs
sfp_virustotal.api_key = your_virustotal_key
sfp_shodan.api_key = your_shodan_key
sfp_hunter.api_key = your_hunter_key

# Optional APIs
sfp_securitytrails.api_key = your_securitytrails_key
sfp_passivetotal.api_key = your_passivetotal_key
sfp_greynoise.api_key = your_greynoise_key
```

## Module Development

### Creating Custom Modules

1. **Module Template**: Use the provided template
2. **Event Handling**: Define watched and produced events
3. **Configuration**: Set up module options
4. **Testing**: Thoroughly test functionality
5. **Documentation**: Document usage and configuration

### Module Structure

```python
from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_custom_module(SpiderFootPlugin):
    meta = {
        'name': "Custom Module Name",
        'summary': "Brief description of functionality",
        'flags': [""],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["DNS"],
        'dataSource': {
            'website': "https://example.com",
            'model': "FREE_NOAUTH_LIMITED"
        }
    }

    # Module implementation
    def watchedEvents(self):
        return ["DOMAIN_NAME"]

    def producedEvents(self):
        return ["IP_ADDRESS"]

    def handleEvent(self, event):
        # Module logic
        pass
```

## Module Testing

### Testing Individual Modules

```bash
# Test module syntax
python -m py_compile modules/sfp_module_name.py

# Test module functionality
python sf.py -s example.com -t DOMAIN_NAME -m sfp_module_name -v

# Debug mode
python sf.py -s example.com -t DOMAIN_NAME -m sfp_module_name --debug
```

### Performance Testing

```bash
# Time module execution
time python sf.py -s example.com -t DOMAIN_NAME -m sfp_module_name

# Monitor resource usage
top -p $(pgrep -f "sf.py")

# Check memory usage
ps aux | grep sf.py
```

## Troubleshooting

### Common Issues

#### Module Not Found
- Check module file exists in `modules/` directory
- Verify file permissions
- Check for syntax errors

#### API Key Issues
- Verify API key is correct
- Check API key permissions
- Verify rate limits not exceeded

#### Performance Issues
- Increase module timeouts
- Reduce concurrent operations
- Check network connectivity

### Debugging Tools

```bash
# List all modules
python sf.py -M

# Show module information
python sf.py -M sfp_module_name

# Test module configuration
python sf.py --test-modules

# Verbose output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_module_name -v
```

## Best Practices

### Module Selection
1. **Start with passive modules** for initial reconnaissance
2. **Understand module behavior** before using active modules
3. **Consider target sensitivity** when choosing modules
4. **Monitor resource usage** during scans
5. **Review output quality** and adjust as needed

### Performance Optimization
1. **Tune thread counts** based on system capabilities
2. **Set appropriate timeouts** for network operations
3. **Use module-specific limits** to control output volume
4. **Monitor API rate limits** to avoid blocking
5. **Regular module updates** for latest features

### Security Considerations
1. **Protect API keys** from unauthorized access
2. **Use HTTPS** for all external communications
3. **Validate input data** before processing
4. **Monitor module logs** for suspicious activity
5. **Regular security updates** for dependencies

## Contributing

### Adding New Modules

1. **Fork the repository** on GitHub
2. **Create module** following the template
3. **Add documentation** for the new module
4. **Write tests** for functionality
5. **Submit pull request** with changes

### Improving Existing Modules

1. **Identify improvement areas** in existing modules
2. **Test changes thoroughly** before submitting
3. **Update documentation** to reflect changes
4. **Maintain backward compatibility** when possible
5. **Follow coding standards** and conventions

For more detailed information about specific modules, see individual module documentation pages or check the [Custom Module Development Guide](../developer/module_development.md).
