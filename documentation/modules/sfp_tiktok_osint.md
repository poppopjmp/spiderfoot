# sfp_tiktok_osint

## Overview

The TikTok OSINT Intelligence module provides comprehensive intelligence gathering capabilities for TikTok social media platform. This module enables investigators to collect user profile information, analyze content patterns, and perform network mapping while respecting platform guidelines and rate limits.

## Features

- **User Profile Analysis**: Extract comprehensive profile metadata including follower counts, verification status, and bio information
- **Content Intelligence**: Analyze recent videos, hashtags, and content patterns
- **Network Analysis**: Map follower/following relationships (when available)
- **Geographic Intelligence**: Extract location data from profiles and content
- **Rate Limiting**: Intelligent rate limiting to avoid detection and respect platform terms
- **Cross-Platform Correlation**: Integration with advanced correlation engine for identity attribution

## Configuration

### Required Settings

| Option | Description | Default |
|--------|-------------|---------|
| `api_key` | TikTok API Client Key (optional) | "" |
| `api_secret` | TikTok API Client Secret (optional) | "" |
| `use_web_scraping` | Use web scraping when API unavailable | True |

### Optional Settings

| Option | Description | Default |
|--------|-------------|---------|
| `max_videos_per_user` | Maximum videos to analyze per user | 50 |
| `analyze_comments` | Analyze comments on videos | True |
| `extract_hashtags` | Extract and analyze hashtags | True |
| `network_analysis` | Perform network analysis | True |
| `rate_limit_delay` | Delay between requests (seconds) | 2 |
| `respect_robots_txt` | Respect robots.txt restrictions | True |

## Input Events

- `SOCIAL_MEDIA_PROFILE_URL`: TikTok profile URLs
- `USERNAME`: Usernames to search on TikTok
- `HUMAN_NAME`: Names to search for
- `EMAILADDR`: Email addresses for profile matching

## Output Events

- `SOCIAL_MEDIA_PROFILE`: Complete TikTok profile data
- `SOCIAL_MEDIA_CONTENT`: Individual content pieces
- `SOCIAL_MEDIA_HASHTAG`: Extracted hashtags
- `SOCIAL_MEDIA_MENTION`: User mentions and interactions
- `SOCIAL_MEDIA_NETWORK`: Network relationship data
- `USERNAME`: Discovered usernames
- `HUMAN_NAME`: Extracted real names
- `GEOINFO`: Geographic location data

## Use Cases

### Social Media Footprinting
Discover TikTok presence of individuals or organizations for digital footprint mapping.

### Influence Analysis
Analyze follower networks and content engagement patterns to understand influence and reach.

### Content Trend Analysis
Track hashtag usage and content trends for market research or threat intelligence.

### Cross-Platform Investigation
Correlate TikTok profiles with other social media accounts for comprehensive identity attribution.

## API Integration

### TikTok API (When Available)
If you have access to TikTok's official API:

1. Register at [TikTok Developers](https://developers.tiktok.com/)
2. Create an application and obtain Client Key and Client Secret
3. Configure the module with your credentials

### Web Scraping Mode
When API access is not available, the module uses respectful web scraping:

- Implements proper rate limiting
- Respects robots.txt guidelines
- Uses rotating user agents
- Includes error handling and retry logic

## Ethical Considerations

This module is designed to operate within ethical and legal boundaries:

- **Respect Platform Terms**: Always comply with TikTok's Terms of Service
- **Rate Limiting**: Built-in delays prevent aggressive scraping
- **Public Data Only**: Only collects publicly available information
- **No Account Required**: Does not require authentication or account creation

## Troubleshooting

### Common Issues

**Module not finding profiles:**
- Verify the username or URL format is correct
- Check if the profile is public and accessible
- Ensure rate limiting delays are appropriate

**Rate limiting errors:**
- Increase the `rate_limit_delay` setting
- Use longer delays during peak hours
- Consider using API access instead of web scraping

**Missing data in results:**
- TikTok frequently changes their page structure
- Some data may be restricted to authenticated users
- Check module logs for specific extraction errors

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
# In SpiderFoot configuration
'_debug': True
```

## Example Output

```json
{
  "username": "example_user",
  "display_name": "Example User",
  "bio": "Content creator #tech #gaming",
  "follower_count": 15000,
  "following_count": 500,
  "video_count": 125,
  "verified": false,
  "profile_picture": "https://example.com/avatar.jpg",
  "analysis_timestamp": 1690123456
}
```

## Integration with Other Modules

The TikTok OSINT module works seamlessly with:

- **Advanced Correlation Engine**: For cross-platform identity resolution
- **Social Media modules**: For comprehensive social media analysis
- **Email/Username modules**: For account discovery and attribution
- **Geographic modules**: For location-based analysis

## Legal and Compliance

Always ensure compliance with:
- Local privacy laws and regulations
- Platform Terms of Service
- Organizational policies
- Investigative guidelines

This module is intended for legitimate security research, threat intelligence, and investigative purposes only.
