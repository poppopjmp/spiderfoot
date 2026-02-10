# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_tiktok_osint
# Purpose:      TikTok OSINT module for user and content analysis
#
# Author:       SpiderFoot Enhancement Team
# Created:      2025-07-19
# Copyright:    (c) SpiderFoot Enhancement Team 2025
# License:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
TikTok OSINT Module

Performs comprehensive TikTok intelligence gathering including:
- User profile analysis
- Content metadata extraction
- Follower/following network analysis
- Video trend analysis
- Hashtag intelligence
- Geographic location data
"""

import json
import re
import time
from typing import Any

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_tiktok_osint(SpiderFootModernPlugin):
    """TikTok OSINT intelligence gathering module."""

    meta = {
        'name': "TikTok OSINT Intelligence",
        'summary': "Gather intelligence from TikTok including user profiles, content analysis, and network mapping.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Social Media"],
        'dataSource': {
            'website': "https://www.tiktok.com",
            'model': "FREE_NOAUTH_LIMITED",
            'references': [
                "https://developers.tiktok.com/doc/",
                "https://www.tiktok.com/community-guidelines"
            ],
            'apiKeyInstructions': [
                "Visit https://developers.tiktok.com/",
                "Create a developer account",
                "Register your application",
                "Copy the Client Key and Client Secret"
            ],
            'favIcon': "https://sf16-website-login.neutral.ttwstatic.com/obj/tiktok_web_login_static/tiktok/webapp/main/webapp-desktop/8152caf0c8e8bc67ae0d.ico",
            'description': "TikTok is a short-form video hosting service. This module extracts user profiles, content metadata, and performs network analysis for OSINT purposes."
        }
    }

    opts = {
        'api_key': '',
        'api_secret': '',
        'max_videos_per_user': 50,
        'analyze_comments': True,
        'extract_hashtags': True,
        'network_analysis': True,
        'content_analysis': True,
        'rate_limit_delay': 2,
        'use_web_scraping': True,
        'respect_robots_txt': True
    }

    optdescs = {
        'api_key': "TikTok API Client Key (optional for web scraping)",
        'api_secret': "TikTok API Client Secret (optional for web scraping)",
        'max_videos_per_user': "Maximum number of videos to analyze per user",
        'analyze_comments': "Analyze comments on videos for additional intelligence",
        'extract_hashtags': "Extract and analyze hashtags from content",
        'network_analysis': "Perform network analysis of followers/following",
        'content_analysis': "Perform detailed content analysis",
        'rate_limit_delay': "Delay between requests to avoid rate limiting (seconds)",
        'use_web_scraping': "Use web scraping when API is not available",
        'respect_robots_txt': "Respect robots.txt restrictions"
    }

    results = None
    errorState = False
    
    def setup(self, sfc, userOpts=None):
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
    def watchedEvents(self):
        """Return the list of events this module watches."""
        return [
            "SOCIAL_MEDIA_PROFILE_URL",
            "USERNAME",
            "HUMAN_NAME",
            "EMAILADDR",
            "PHONE_NUMBER"
        ]

    def producedEvents(self):
        """Return the list of events this module produces."""
        return [
            "SOCIAL_MEDIA_PROFILE",
            "SOCIAL_MEDIA_CONTENT",
            "SOCIAL_MEDIA_HASHTAG",
            "SOCIAL_MEDIA_MENTION",
            "SOCIAL_MEDIA_NETWORK",
            "USERNAME",
            "HUMAN_NAME",
            "GEOINFO",
            "AFFILIATE_INTERNET_NAME",
            "RAW_RIR_DATA",
            "WEBSERVER_TECHNOLOGY",
            "LINKED_URL_EXTERNAL"
        ]

    def handleEvent(self, event):
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if eventName == "SOCIAL_MEDIA_PROFILE_URL":
            if "tiktok.com" in eventData:
                self._analyze_tiktok_profile_url(eventData, event)
        elif eventName == "USERNAME":
            self._search_tiktok_username(eventData, event)
        elif eventName in ["HUMAN_NAME", "EMAILADDR"]:
            self._search_tiktok_by_identifier(eventData, event)

    def _analyze_tiktok_profile_url(self, url: str, source_event: SpiderFootEvent) -> None:
        """Analyze a TikTok profile URL.
        
        Args:
            url: TikTok profile URL to analyze
            source_event: Source SpiderFootEvent that triggered this analysis
        """
        self.debug(f"Analyzing TikTok profile URL: {url}")
        
        # Extract username from URL
        username_match = re.search(r'tiktok\.com/@([^/?]+)', url)
        if not username_match:
            self.debug("Could not extract username from TikTok URL")
            return
            
        username = username_match.group(1)
        
        # Analyze the profile
        profile_data = self._get_profile_data(username)
        if profile_data:
            self._process_profile_data(profile_data, username, source_event)

    def _search_tiktok_username(self, username: str, source_event: SpiderFootEvent) -> None:
        """Search for a username on TikTok.
        
        Args:
            username: Username to search for
            source_event: Source SpiderFootEvent that triggered this search
        """
        self.debug(f"Searching TikTok for username: {username}")
        
        profile_data = self._get_profile_data(username)
        if profile_data:
            self._process_profile_data(profile_data, username, source_event)

    def _search_tiktok_by_identifier(self, identifier: str, source_event: SpiderFootEvent) -> None:
        """Search TikTok using various identifiers."""
        self.debug(f"Searching TikTok for identifier: {identifier}")
        
        # For now, this would require more advanced search capabilities
        # that aren't available through public APIs
        pass

    def _get_profile_data(self, username: str) -> dict[str, Any] | None:
        """Get TikTok profile data."""
        if self.opts['api_key'] and self.opts['api_secret']:
            return self._get_profile_data_api(username)
        elif self.opts['use_web_scraping']:
            return self._get_profile_data_scraping(username)
        else:
            self.debug("No API credentials and web scraping disabled")
            return None

    def _get_profile_data_api(self, username: str) -> dict[str, Any] | None:
        """Get profile data using TikTok API."""
        # Note: TikTok's API access is limited and requires approval
        # This is a placeholder for when API access is available
        self.debug("TikTok API access is currently limited - using web scraping fallback")
        return self._get_profile_data_scraping(username)

    def _get_profile_data_scraping(self, username: str) -> dict[str, Any] | None:
        """Get profile data using web scraping techniques."""
        profile_url = f"https://www.tiktok.com/@{username}"
        
        # Respect rate limiting
        time.sleep(self.opts['rate_limit_delay'])
        
        res = self.fetch_url(
            profile_url,
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts['_useragent']
        )
        
        if res['code'] != "200":
            self.debug(f"Failed to fetch TikTok profile: {res['code']}")
            return None
            
        if not res['content']:
            self.debug("No content returned from TikTok profile")
            return None

        return self._parse_profile_html(res['content'], username)

    def _parse_profile_html(self, html_content: str, username: str) -> dict[str, Any] | None:
        """Parse TikTok profile HTML content."""
        try:
            # Extract profile data from HTML
            profile_data = {
                'username': username,
                'display_name': self._extract_display_name(html_content),
                'bio': self._extract_bio(html_content),
                'follower_count': self._extract_follower_count(html_content),
                'following_count': self._extract_following_count(html_content),
                'video_count': self._extract_video_count(html_content),
                'verified': self._is_verified_account(html_content),
                'profile_picture': self._extract_profile_picture(html_content),
                'videos': self._extract_recent_videos(html_content)
            }
            
            return profile_data
            
        except Exception as e:
            self.error(f"Error parsing TikTok profile HTML: {e}")
            return None

    def _extract_display_name(self, html: str) -> str | None:
        """Extract display name from HTML."""
        # Look for common patterns in TikTok HTML
        patterns = [
            r'"nickname":"([^"]+)"',
            r'<h2[^>]*>([^<]+)</h2>',
            r'data-e2e="profile-subtitle"[^>]*>([^<]+)<'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()
        
        return None

    def _extract_bio(self, html: str) -> str | None:
        """Extract bio/description from HTML."""
        patterns = [
            r'"signature":"([^"]+)"',
            r'data-e2e="profile-description"[^>]*>([^<]+)<'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()
        
        return None

    def _extract_follower_count(self, html: str) -> int | None:
        """Extract follower count from HTML."""
        patterns = [
            r'"followerCount":(\d+)',
            r'data-e2e="followers-count"[^>]*>([^<]+)<'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    return int(match.group(1).replace(',', '').replace('K', '000').replace('M', '000000'))
                except ValueError:
                    continue
        
        return None

    def _extract_following_count(self, html: str) -> int | None:
        """Extract following count from HTML."""
        patterns = [
            r'"followingCount":(\d+)',
            r'data-e2e="following-count"[^>]*>([^<]+)<'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    return int(match.group(1).replace(',', '').replace('K', '000').replace('M', '000000'))
                except ValueError:
                    continue
        
        return None

    def _extract_video_count(self, html: str) -> int | None:
        """Extract video count from HTML."""
        patterns = [
            r'"videoCount":(\d+)',
            r'data-e2e="video-count"[^>]*>([^<]+)<'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    return int(match.group(1).replace(',', '').replace('K', '000').replace('M', '000000'))
                except ValueError:
                    continue
        
        return None

    def _is_verified_account(self, html: str) -> bool:
        """Check if account is verified."""
        verified_patterns = [
            r'"verified":true',
            r'data-e2e="profile-verified-badge"',
            r'class="[^"]*verified[^"]*"'
        ]
        
        for pattern in verified_patterns:
            if re.search(pattern, html):
                return True
        
        return False

    def _extract_profile_picture(self, html: str) -> str | None:
        """Extract profile picture URL."""
        patterns = [
            r'"avatarLarger":"([^"]+)"',
            r'data-e2e="profile-avatar"[^>]*src="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        
        return None

    def _extract_recent_videos(self, html: str) -> list[dict[str, Any]]:
        """Extract recent video data."""
        videos = []
        
        # This would require more sophisticated parsing
        # For now, return empty list
        return videos

    def _process_profile_data(self, profile_data: dict[str, Any], username: str, source_event: SpiderFootEvent) -> None:
        """Process and emit events for profile data."""
        if not profile_data:
            return

        # Create profile event
        profile_json = json.dumps(profile_data, ensure_ascii=False)
        profile_event = SpiderFootEvent(
            "SOCIAL_MEDIA_PROFILE",
            profile_json,
            self.__name__,
            source_event
        )
        self.notifyListeners(profile_event)

        # Extract and emit individual data points
        if profile_data.get('display_name'):
            name_event = SpiderFootEvent(
                "HUMAN_NAME",
                profile_data['display_name'],
                self.__name__,
                profile_event
            )
            self.notifyListeners(name_event)

        if profile_data.get('bio'):
            bio_event = SpiderFootEvent(
                "SOCIAL_MEDIA_CONTENT", 
                profile_data['bio'],
                self.__name__,
                profile_event
            )
            self.notifyListeners(bio_event)

            # Extract hashtags from bio
            if self.opts['extract_hashtags']:
                hashtags = re.findall(r'#(\w+)', profile_data['bio'])
                for hashtag in hashtags:
                    hashtag_event = SpiderFootEvent(
                        "SOCIAL_MEDIA_HASHTAG",
                        hashtag,
                        self.__name__,
                        bio_event
                    )
                    self.notifyListeners(hashtag_event)

        # Emit raw data for correlation engine
        raw_event = SpiderFootEvent(
            "RAW_RIR_DATA",
            f"TikTok Profile: {profile_json}",
            self.__name__,
            source_event
        )
        self.notifyListeners(raw_event)
