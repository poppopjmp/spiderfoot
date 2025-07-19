# sfp_ai_summary - AI Threat Intelligence Summarizer

## Overview

The AI Threat Intelligence Summarizer module leverages large language models (LLMs) to provide automated analysis and summarization of SpiderFoot scan findings. This module uses OpenAI's GPT models to generate comprehensive threat intelligence reports and identify key security concerns.

## Features

### Automated Threat Analysis
- **Intelligent Summarization**: LLM-powered scan result analysis
- **Risk Assessment**: Automated threat level evaluation
- **Pattern Recognition**: AI-driven pattern identification
- **Context Awareness**: Understanding of security implications

### Flexible Reporting
- **On-Demand Summaries**: Generate summaries on scan completion
- **Periodic Reports**: Scheduled analysis during long scans
- **Custom Analysis**: User-defined analysis parameters
- **Multi-Format Output**: JSON, text, and structured reports

### Advanced Analytics
- **Threat Correlation**: Connect related security findings
- **Priority Ranking**: Importance-based finding organization
- **Actionable Insights**: Specific remediation recommendations
- **Confidence Scoring**: AI confidence in assessments

## Configuration

### OpenAI API Settings
```ini
[ai_summary]
# OpenAI API configuration
openai_api_key = your_openai_api_key
model = gpt-3.5-turbo
max_tokens = 1000
temperature = 0.3
```

### Analysis Parameters
```ini
# Summary generation settings
summary_frequency = on_finish
max_events_per_summary = 100
include_confidence_scores = True
threat_level_analysis = True

# Report customization
include_remediation_steps = True
technical_detail_level = medium
executive_summary = True
```

### Cost Management
```ini
# Token usage optimization
compress_input = True
use_cheaper_model_for_preprocessing = True
batch_analysis = True
cache_similar_analyses = True
```

## Supported Event Types

### Input Events
- `*` (All event types for comprehensive analysis)

### Output Events
- `THREAT_INTEL_SUMMARY`
- `AI_RISK_ASSESSMENT`
- `SECURITY_RECOMMENDATION`
- `PATTERN_ANALYSIS`

## AI Analysis Capabilities

### Threat Intelligence Analysis
- **Vulnerability Assessment**: Automated vulnerability prioritization
- **Attack Vector Identification**: Potential attack path analysis
- **Risk Quantification**: Numerical risk scoring
- **Compliance Impact**: Regulatory compliance implications

### Pattern Recognition
- **Attack Patterns**: Known attack technique identification
- **Anomaly Detection**: Unusual finding patterns
- **Correlation Analysis**: Related finding connections
- **Trend Analysis**: Historical pattern comparison

### Remediation Guidance
- **Immediate Actions**: Critical issue remediation
- **Strategic Recommendations**: Long-term security improvements
- **Priority Matrix**: Risk-based prioritization
- **Implementation Guidance**: Technical implementation steps

## Usage Examples

### Basic Threat Analysis
```bash
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_virustotal,sfp_ai_summary
```

### Comprehensive Security Assessment
```bash
python sf.py -s target.com -t DOMAIN_NAME -m sfp_portscan_tcp,sfp_banner,sfp_ssl,sfp_whois,sfp_ai_summary
```

### Multi-Target Analysis
```bash
python sf.py -s targets.txt -t FILE -m sfp_dnsresolve,sfp_ssl,sfp_portscan_tcp,sfp_ai_summary
```

## Report Types

### Executive Summary
```json
{
  "executive_summary": {
    "overall_risk_level": "HIGH",
    "critical_findings": 3,
    "high_priority_actions": [
      "Update SSL certificate",
      "Patch vulnerable services",
      "Implement access controls"
    ],
    "business_impact": "High risk of data breach"
  }
}
```

### Technical Analysis
```json
{
  "technical_analysis": {
    "vulnerabilities": [
      {
        "type": "SSL_CERTIFICATE_EXPIRED",
        "severity": "HIGH",
        "description": "SSL certificate expired 30 days ago",
        "remediation": "Renew SSL certificate immediately"
      }
    ],
    "attack_vectors": [
      "Man-in-the-middle attacks via expired SSL",
      "Data interception on encrypted channels"
    ]
  }
}
```

### Compliance Report
```json
{
  "compliance_analysis": {
    "frameworks": ["PCI-DSS", "SOC2", "ISO27001"],
    "violations": [
      {
        "framework": "PCI-DSS",
        "requirement": "4.1",
        "description": "Encryption in transit",
        "status": "NON_COMPLIANT"
      }
    ]
  }
}
```

## AI Model Configuration

### Model Selection
```python
# Available models
models = {
    'gpt-3.5-turbo': {
        'cost': 'low',
        'speed': 'fast',
        'quality': 'good'
    },
    'gpt-4': {
        'cost': 'high',
        'speed': 'slow',
        'quality': 'excellent'
    },
    'gpt-4-turbo': {
        'cost': 'medium',
        'speed': 'medium',
        'quality': 'excellent'
    }
}
```

### Prompt Engineering
```python
# Custom analysis prompts
prompts = {
    'vulnerability_analysis': "Analyze these security findings for vulnerabilities...",
    'risk_assessment': "Assess the overall risk level based on these findings...",
    'remediation_planning': "Provide specific remediation steps for these issues..."
}
```

### Token Optimization
```python
# Token usage strategies
optimization = {
    'compress_findings': True,
    'prioritize_high_risk': True,
    'batch_similar_findings': True,
    'use_structured_output': True
}
```

## Integration with Other Modules

### Enhanced Analysis Combinations
```bash
# Comprehensive security assessment with AI analysis
-m sfp_portscan_tcp,sfp_ssl,sfp_whois,sfp_virustotal,sfp_ai_summary

# Social media investigation with AI insights
-m sfp_tiktok_osint,sfp_twitter,sfp_linkedin,sfp_ai_summary

# Blockchain investigation with AI correlation
-m sfp_blockchain_analytics,sfp_advanced_correlation,sfp_ai_summary
```

### Correlation Enhancement
- **Pattern Recognition**: AI-enhanced correlation patterns
- **Risk Amplification**: Combined risk assessment
- **Context Enrichment**: Additional context for findings
- **Prioritization**: AI-driven finding prioritization

## Cost Management

### Token Usage Optimization
```ini
# Cost-effective configuration
model = gpt-3.5-turbo
max_tokens = 500
compress_input = True
cache_similar_analyses = True

# Batch processing
batch_size = 50
batch_delay_seconds = 1.0
```

### Usage Monitoring
```python
# Track API usage
usage_stats = {
    'total_tokens': 0,
    'total_cost': 0.0,
    'requests_count': 0,
    'average_tokens_per_request': 0
}

# Cost alerts
cost_threshold = 10.0  # USD
alert_on_threshold = True
```

## Security and Privacy

### Data Protection
- **Data Anonymization**: Remove PII before analysis
- **Local Processing**: Option for local LLM models
- **Encryption**: Encrypted API communications
- **Data Retention**: Configurable analysis data retention

### Privacy Compliance
- **GDPR Compliance**: Privacy-by-design implementation
- **Data Minimization**: Send only necessary data to AI
- **Consent Management**: User consent for AI analysis
- **Audit Trails**: Comprehensive AI usage logging

## Advanced Features

### Custom Analysis Rules
```yaml
# Custom AI analysis rules
analysis_rules:
  - name: "Critical Vulnerability Detection"
    condition: "severity == 'CRITICAL'"
    prompt: "Focus on immediate threat mitigation"
    
  - name: "Compliance Analysis"
    condition: "compliance_relevant == true"
    prompt: "Analyze for regulatory compliance"
```

### Multi-Language Support
```ini
# Supported languages
supported_languages = ['en', 'es', 'fr', 'de', 'it', 'pt']
default_language = 'en'
auto_detect_language = True
```

### Integration APIs
```python
# REST API for AI analysis
POST /api/ai/analyze
{
    "findings": [...],
    "analysis_type": "threat_assessment",
    "detail_level": "high"
}

# Response
{
    "summary": "...",
    "risk_level": "HIGH",
    "recommendations": [...],
    "confidence": 0.85
}
```

## Troubleshooting

### Common Issues
1. **API Key Errors**: Verify OpenAI API key configuration
2. **Rate Limiting**: Adjust request frequency settings
3. **High Costs**: Enable cost optimization features
4. **Poor Analysis Quality**: Adjust prompt engineering

### Performance Optimization
```ini
# For cost-sensitive environments
model = gpt-3.5-turbo
max_tokens = 300
batch_size = 100

# For high-quality analysis
model = gpt-4
max_tokens = 2000
temperature = 0.1
```

### Quality Improvement
```python
# Improve analysis quality
quality_settings = {
    'use_structured_prompts': True,
    'include_context': True,
    'validate_outputs': True,
    'use_multiple_models': False
}
```

---

For more information on AI-powered security analysis, see the [AI Integration Guide](../ai_integration.md).
