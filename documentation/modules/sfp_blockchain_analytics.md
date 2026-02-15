# sfp_blockchain_analytics - Advanced Blockchain Analytics

## Overview

The Advanced Blockchain Analytics module provides comprehensive cryptocurrency investigation capabilities for Bitcoin, Ethereum, Litecoin, and other blockchain networks. This module enables investigators to analyze wallet addresses, track transaction flows, identify risk factors, and detect money laundering patterns.

## Features

### Multi-Cryptocurrency Support
- **Bitcoin**: Complete transaction analysis and wallet clustering
- **Ethereum**: Smart contract interaction analysis and token tracking
- **Litecoin**: Transaction flow and address attribution
- **Other Networks**: Extensible support for additional blockchains

### Advanced Analytics
- **Transaction Flow Analysis**: Multi-hop transaction tracking
- **Wallet Clustering**: Identity resolution across related addresses
- **Exchange Attribution**: Identification of major exchange wallets
- **Risk Scoring**: ML-based risk assessment algorithms
- **Sanctions Checking**: OFAC and other sanctions list verification

### Investigation Capabilities
- **Money Laundering Detection**: Pattern recognition for suspicious flows
- **Dark Web Marketplace Integration**: Known criminal address identification
- **Cross-Chain Analysis**: Multi-blockchain correlation
- **Temporal Analysis**: Time-based transaction pattern detection

## Configuration

### Required API Keys
```ini
[blockchain_analytics]
blockcypher_api_key = your_blockcypher_key
etherscan_api_key = your_etherscan_key
```

### Analysis Settings
```ini
# Transaction analysis depth
transaction_depth = 3

# Risk assessment threshold (0.0-1.0)
risk_threshold = 0.6

# Enable sanctions checking
sanctions_check_enabled = True

# Enable wallet clustering
wallet_clustering_enabled = True
```

### Rate Limiting
```ini
# API requests per second
api_rate_limit_per_second = 3

# Maximum concurrent requests
max_concurrent_requests = 5
```

## Supported Event Types

### Input Events
- `BITCOIN_ADDRESS`
- `ETHEREUM_ADDRESS` 
- `CRYPTOCURRENCY_ADDRESS`
- `BLOCKCHAIN_TRANSACTION`

### Output Events
- `BLOCKCHAIN_ADDRESS_ANALYSIS`
- `CRYPTOCURRENCY_TRANSACTION`
- `BLOCKCHAIN_RISK_ASSESSMENT`
- `CRYPTOCURRENCY_EXCHANGE`
- `SANCTIONS_MATCH`
- `MONEY_LAUNDERING_INDICATOR`

## Usage Examples

### Bitcoin Address Investigation
```bash
python sf.py -s 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -t BITCOIN_ADDRESS -m sfp_blockchain_analytics
```

### Ethereum Address Analysis
```bash
python sf.py -s 0x742d35Cc6634C0532925a3b8D400000abBAd2f3d -t ETHEREUM_ADDRESS -m sfp_blockchain_analytics
```

### Multi-Address Investigation
```bash
python sf.py -s crypto_addresses.txt -t FILE -m sfp_blockchain_analytics,sfp_advanced_correlation
```

## Risk Assessment Metrics

### Risk Factors
- **Sanctions List Matches**: OFAC, EU, UN sanctions
- **Dark Web Associations**: Known criminal marketplace addresses
- **Mixing Services**: Tumbler and privacy coin usage
- **High-Risk Exchanges**: Exchanges with poor compliance
- **Suspicious Patterns**: Rapid fund movement, layering

### Risk Scoring
- **0.0-0.3**: Low risk (normal usage patterns)
- **0.3-0.6**: Medium risk (some suspicious indicators)
- **0.6-0.8**: High risk (multiple risk factors)
- **0.8-1.0**: Critical risk (strong criminal indicators)

## Integration with Other Modules

### Recommended Module Combinations
```bash
# Complete cryptocurrency investigation
-m sfp_blockchain_analytics,sfp_advanced_correlation

# Performance-optimized investigation
-m sfp_blockchain_analytics,sfp_performance_optimizer

# Multi-platform correlation
-m sfp_blockchain_analytics,sfp_tiktok_osint,sfp_advanced_correlation
```

## API Integration

### Blockchain Data Providers
- **BlockCypher**: Bitcoin, Litecoin, Dogecoin
- **Etherscan**: Ethereum, ERC-20 tokens
- **BlockStream**: Bitcoin block explorer
- **Infura**: Ethereum node access

### Rate Limiting and Costs
- Free tier limitations apply to most APIs
- Premium plans recommended for intensive investigations
- Built-in rate limiting prevents API quota exhaustion

## Security and Privacy

### Data Handling
- No private keys or sensitive data stored
- Query logs can be disabled for sensitive investigations
- Supports proxy configuration for anonymity

### Compliance
- GDPR-compliant data processing
- Configurable data retention policies
- Audit logging for compliance requirements

## Troubleshooting

### Common Issues
1. **API Key Errors**: Verify API keys in module configuration
2. **Rate Limiting**: Adjust rate limit settings or upgrade API plans
3. **Network Timeouts**: Check network connectivity and proxy settings
4. **Invalid Addresses**: Ensure proper address format validation

### Performance Optimization
- Enable caching for repeated address queries
- Use batch processing for multiple addresses
- Configure appropriate rate limits for your API plan

## Advanced Features

### Machine Learning Integration
- Transaction pattern recognition
- Anomaly detection algorithms
- Risk score calibration
- Behavioral analysis

### Custom Risk Indicators
- User-defined risk patterns
- Custom sanctions lists
- Proprietary threat intelligence feeds
- Industry-specific risk factors

---

For more information on blockchain investigation techniques, see the [Advanced User Guide](../advanced.md).
