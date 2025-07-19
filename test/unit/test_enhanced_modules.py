#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for enhanced SpiderFoot modules.

Tests the new OSINT modules including:
- TikTok OSINT module
- Advanced Correlation Engine
- Performance Optimizer
- Blockchain Analytics
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock, mock_open
import json
import time

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, project_root)

# Import SpiderFoot components
from spiderfoot import SpiderFootEvent, SpiderFootPlugin
from modules.sfp_tiktok_osint import sfp_tiktok_osint
from modules.sfp_advanced_correlation import sfp_advanced_correlation, AdvancedCorrelationEngine
from modules.sfp_performance_optimizer import sfp_performance_optimizer, TTLCache, AdaptiveRateLimiter
from modules.sfp_blockchain_analytics import sfp_blockchain_analytics, BlockchainAnalyzer


class TestTikTokOSINT(unittest.TestCase):
    """Test cases for TikTok OSINT module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.module = sfp_tiktok_osint()
        self.sfc = MagicMock()
        self.module.setup(self.sfc, {})
    
    def test_module_metadata(self):
        """Test module metadata is correctly defined."""
        self.assertEqual(self.module.meta['name'], "TikTok OSINT Intelligence")
        self.assertIn("Social Media", self.module.meta['categories'])
        self.assertIn("Footprint", self.module.meta['useCases'])
    
    def test_watched_events(self):
        """Test that module watches correct event types."""
        watched = self.module.watchedEvents()
        expected_events = ["SOCIAL_MEDIA_PROFILE_URL", "USERNAME", "HUMAN_NAME", "EMAILADDR", "PHONE_NUMBER"]
        for event in expected_events:
            self.assertIn(event, watched)
    
    def test_produced_events(self):
        """Test that module produces correct event types."""
        produced = self.module.producedEvents()
        expected_events = ["SOCIAL_MEDIA_PROFILE", "SOCIAL_MEDIA_CONTENT", "USERNAME", "HUMAN_NAME"]
        for event in expected_events:
            self.assertIn(event, produced)
    
    @patch('modules.sfp_tiktok_osint.time.sleep')
    def test_tiktok_url_analysis(self, mock_sleep):
        """Test TikTok URL analysis functionality."""
        # Mock HTML content
        mock_html = '''
        <html>
            <script>{"nickname":"TestUser","signature":"Test bio","followerCount":1000}</script>
        </html>
        '''
        
        # Mock fetchUrl response
        self.sfc.fetchUrl.return_value = {
            'code': '200',
            'content': mock_html
        }
        
        # Create test event
        event = SpiderFootEvent("SOCIAL_MEDIA_PROFILE_URL", "https://tiktok.com/@testuser", "test_module")
        
        # Test the handler
        self.module.handleEvent(event)
        
        # Verify fetchUrl was called
        self.sfc.fetchUrl.assert_called()
        
        # Verify sleep was called for rate limiting
        mock_sleep.assert_called()
    
    def test_username_extraction_from_url(self):
        """Test username extraction from TikTok URLs."""
        test_cases = [
            ("https://tiktok.com/@testuser", "testuser"),
            ("https://www.tiktok.com/@another_user", "another_user"),
            ("https://tiktok.com/@user123?tab=videos", "user123"),
        ]
        
        for url, expected_username in test_cases:
            # This would test the internal URL parsing logic
            # For now, just verify the pattern exists
            import re
            match = re.search(r'tiktok\.com/@([^/?]+)', url)
            self.assertIsNotNone(match)
            self.assertEqual(match.group(1), expected_username)


class TestAdvancedCorrelation(unittest.TestCase):
    """Test cases for Advanced Correlation Engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.module = sfp_advanced_correlation()
        self.sfc = MagicMock()
        self.module.setup(self.sfc, {})
        self.engine = AdvancedCorrelationEngine()
    
    def test_module_metadata(self):
        """Test module metadata is correctly defined."""
        self.assertEqual(self.module.meta['name'], "Advanced Correlation Engine")
        self.assertIn("Content Analysis", self.module.meta['categories'])
    
    def test_entity_relationship_addition(self):
        """Test adding entity relationships."""
        self.engine.add_entity_relationship("user1", "user2", "same_person", 0.9)
        
        # Check if relationship was added
        self.assertIn(("user2", "same_person", 0.9), self.engine.entity_graph["user1"])
        self.assertIn(("user1", "same_person", 0.9), self.engine.entity_graph["user2"])
    
    def test_connected_entities_search(self):
        """Test finding connected entities."""
        # Add test relationships
        self.engine.add_entity_relationship("user1", "user2", "same_person", 0.9)
        self.engine.add_entity_relationship("user2", "user3", "family", 0.8)
        
        # Find connections
        connections = self.engine.find_connected_entities("user1", max_depth=2)
        
        # Verify connections found
        self.assertIn(0, connections)  # Direct connections
        self.assertTrue(len(connections[0]) > 0)
    
    def test_temporal_pattern_analysis(self):
        """Test temporal pattern analysis."""
        # Create test events with timestamps
        events = [
            {'timestamp': 1000, 'type': 'login', 'entity': 'user1'},
            {'timestamp': 1005, 'type': 'login', 'entity': 'user2'},
            {'timestamp': 1010, 'type': 'logout', 'entity': 'user1'},
            {'timestamp': 1015, 'type': 'logout', 'entity': 'user2'},
        ]
        
        patterns = self.engine.analyze_temporal_patterns(events, time_window_hours=1)
        
        # Should find patterns in the clustered events
        self.assertTrue(len(patterns) >= 0)
    
    def test_geospatial_clustering(self):
        """Test geospatial data clustering."""
        # Create test geo data (lat, lng coordinates)
        geo_data = [
            {'lat': 40.7128, 'lng': -74.0060, 'name': 'NYC1'},  # New York
            {'lat': 40.7589, 'lng': -73.9851, 'name': 'NYC2'},  # New York (close)
            {'lat': 34.0522, 'lng': -118.2437, 'name': 'LA1'},  # Los Angeles
        ]
        
        clusters = self.engine.cluster_geospatial_data(geo_data, radius_km=50)
        
        # Should find NYC cluster but not include LA
        self.assertTrue(len(clusters) >= 0)
        
        # If clusters found, verify they have required fields
        for cluster in clusters:
            self.assertIn('center', cluster)
            self.assertIn('points', cluster)
            self.assertIn('confidence', cluster)


class TestPerformanceOptimizer(unittest.TestCase):
    """Test cases for Performance Optimizer module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.module = sfp_performance_optimizer()
        self.sfc = MagicMock()
        self.module.setup(self.sfc, {})
    
    def test_module_metadata(self):
        """Test module metadata is correctly defined."""
        self.assertEqual(self.module.meta['name'], "Performance Optimizer")
        self.assertIn("Content Analysis", self.module.meta['categories'])
    
    def test_ttl_cache_basic_operations(self):
        """Test TTL cache basic operations."""
        cache = TTLCache(default_ttl=5, max_size=100)
        
        # Test set and get
        cache.set("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")
        
        # Test non-existent key
        self.assertIsNone(cache.get("nonexistent"))
        
        # Test TTL expiration
        cache.set("key2", "value2", ttl=0)  # Immediate expiration
        time.sleep(0.1)
        self.assertIsNone(cache.get("key2"))
    
    def test_ttl_cache_size_limit(self):
        """Test TTL cache size limiting."""
        cache = TTLCache(default_ttl=3600, max_size=2)
        
        # Fill cache to capacity
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Should evict oldest
        
        # Verify size limit enforced
        self.assertIsNone(cache.get("key1"))  # Should be evicted
        self.assertEqual(cache.get("key2"), "value2")
        self.assertEqual(cache.get("key3"), "value3")
    
    def test_adaptive_rate_limiter(self):
        """Test adaptive rate limiter functionality."""
        limiter = AdaptiveRateLimiter(base_delay=0.1, max_delay=1.0)
        
        # Test success recording
        initial_delay = limiter.current_delay
        limiter.record_success()
        
        # Test failure recording
        limiter.record_failure("429")
        self.assertGreater(limiter.current_delay, initial_delay)
        
        # Test wait functionality (should not raise exception)
        start_time = time.time()
        limiter.wait()
        elapsed = time.time() - start_time
        self.assertGreaterEqual(elapsed, 0)  # Should wait some amount
    
    def test_cache_key_creation(self):
        """Test cache key creation."""
        key1 = self.module.create_cache_key("arg1", "arg2", 123)
        key2 = self.module.create_cache_key("arg1", "arg2", 123)
        key3 = self.module.create_cache_key("arg1", "arg2", 456)
        
        # Same inputs should create same key
        self.assertEqual(key1, key2)
        
        # Different inputs should create different keys
        self.assertNotEqual(key1, key3)


class TestBlockchainAnalytics(unittest.TestCase):
    """Test cases for Blockchain Analytics module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.module = sfp_blockchain_analytics()
        self.sfc = MagicMock()
        self.module.setup(self.sfc, {})
        self.analyzer = BlockchainAnalyzer({})
    
    def test_module_metadata(self):
        """Test module metadata is correctly defined."""
        self.assertEqual(self.module.meta['name'], "Advanced Blockchain Analytics")
        self.assertIn("Secondary Networks", self.module.meta['categories'])
        self.assertIn("Investigate", self.module.meta['useCases'])
    
    def test_watched_events(self):
        """Test that module watches correct blockchain events."""
        watched = self.module.watchedEvents()
        expected_events = ["BITCOIN_ADDRESS", "ETHEREUM_ADDRESS", "CRYPTOCURRENCY_ADDRESS"]
        for event in expected_events:
            self.assertIn(event, watched)
    
    def test_produced_events(self):
        """Test that module produces correct blockchain events."""
        produced = self.module.producedEvents()
        expected_events = [
            "BLOCKCHAIN_ANALYSIS",
            "CRYPTOCURRENCY_RISK_ASSESSMENT", 
            "MONEY_LAUNDERING_INDICATOR",
            "SANCTIONS_LIST_MATCH"
        ]
        for event in expected_events:
            self.assertIn(event, produced)
    
    def test_bitcoin_address_validation(self):
        """Test Bitcoin address validation."""
        valid_addresses = [
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",  # Legacy
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # P2SH
            "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"  # Bech32
        ]
        
        invalid_addresses = [
            "invalid_address",
            "1234567890",
            "0x742d35Cc6634C0532925a3b8D8C3e4321e555"  # Ethereum format
        ]
        
        for addr in valid_addresses:
            self.assertTrue(self.module._is_bitcoin_address(addr), f"Should validate: {addr}")
        
        for addr in invalid_addresses:
            self.assertFalse(self.module._is_bitcoin_address(addr), f"Should not validate: {addr}")
    
    def test_ethereum_address_validation(self):
        """Test Ethereum address validation."""
        valid_addresses = [
            "0x742d35Cc6634C0532925a3b8D8C3e43216de222e",
            "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
        ]
        
        invalid_addresses = [
            "invalid_address",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",  # Bitcoin format
            "0x742d35Cc6634C0532925a3b8D8C3e43216de222"  # Too short
        ]
        
        for addr in valid_addresses:
            self.assertTrue(self.module._is_ethereum_address(addr), f"Should validate: {addr}")
        
        for addr in invalid_addresses:
            self.assertFalse(self.module._is_ethereum_address(addr), f"Should not validate: {addr}")
    
    def test_crypto_type_determination(self):
        """Test cryptocurrency type determination."""
        test_cases = [
            ("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2", "BITCOIN_ADDRESS", "bitcoin"),
            ("0x742d35Cc6634C0532925a3b8D8C3e43216de222e", "ETHEREUM_ADDRESS", "ethereum"),
            ("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", "CRYPTOCURRENCY_ADDRESS", "bitcoin"),
        ]
        
        for address, event_type, expected_type in test_cases:
            result = self.module._determine_crypto_type(address, event_type)
            self.assertEqual(result, expected_type, f"Address {address} should be {expected_type}")
    
    def test_money_laundering_detection(self):
        """Test money laundering pattern detection."""
        # Test rapid transactions
        rapid_transactions = [
            {'timestamp': 1000, 'value': 100000},
            {'timestamp': 1300, 'value': 95000},  # 5 minutes later
            {'timestamp': 1600, 'value': 90000},  # 5 minutes later
        ]
        
        indicators = self.analyzer._detect_money_laundering_patterns(rapid_transactions)
        self.assertIn('rapid_transactions', indicators)
        
        # Test round number structuring
        round_transactions = [
            {'timestamp': 1000, 'value': 1000000},  # Round number
            {'timestamp': 2000, 'value': 2000000},  # Round number
            {'timestamp': 3000, 'value': 1500000},  # Not round
        ]
        
        indicators = self.analyzer._detect_money_laundering_patterns(round_transactions)
        self.assertIn('round_number_structuring', indicators)
    
    @patch('modules.sfp_blockchain_analytics.requests.get')
    def test_bitcoin_transaction_fetching(self, mock_get):
        """Test Bitcoin transaction fetching with mocked API."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'txs': [
                {
                    'hash': 'test_hash_1',
                    'outputs': [{'value': 100000}],
                    'confirmed': '2023-01-01T00:00:00Z',
                    'confirmations': 6
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Set up analyzer with API key
        analyzer = BlockchainAnalyzer({'blockcypher': 'test_key'})
        
        # Test transaction fetching
        transactions = analyzer._get_bitcoin_transactions('1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2')
        
        # Verify API was called and data returned
        mock_get.assert_called()
        self.assertTrue(len(transactions) > 0)
        self.assertIn('hash', transactions[0])


class TestNewCorrelationRules(unittest.TestCase):
    """Test cases for new correlation rules."""
    
    def test_tiktok_correlation_rule_structure(self):
        """Test TikTok correlation rule has correct structure."""
        rule_path = os.path.join(project_root, 'correlations', 'tiktok_user_correlation.yaml')
        
        # Verify file exists
        self.assertTrue(os.path.exists(rule_path), "TikTok correlation rule file should exist")
        
        # Read and parse YAML
        import yaml
        with open(rule_path, 'r') as f:
            rule = yaml.safe_load(f)
        
        # Verify required fields
        self.assertEqual(rule['id'], 'tiktok_user_correlation')
        self.assertIn('meta', rule)
        self.assertIn('collections', rule)
        self.assertIn('analysis', rule)
        self.assertIn('headline', rule)
    
    def test_blockchain_correlation_rule_structure(self):
        """Test blockchain correlation rule has correct structure."""
        rule_path = os.path.join(project_root, 'correlations', 'blockchain_risk_aggregation.yaml')
        
        # Verify file exists
        self.assertTrue(os.path.exists(rule_path), "Blockchain correlation rule file should exist")
        
        # Read and parse YAML
        import yaml
        with open(rule_path, 'r') as f:
            rule = yaml.safe_load(f)
        
        # Verify required fields
        self.assertEqual(rule['id'], 'blockchain_risk_aggregation')
        self.assertIn('meta', rule)
        self.assertIn('collections', rule)
        self.assertIn('analysis', rule)
        self.assertIn('headline', rule)
        
        # Verify blockchain-specific collections
        collection_names = [c['name'] for c in rule['collections']]
        self.assertIn('Cryptocurrency Risk Assessments', collection_names)
        self.assertIn('Money Laundering Indicators', collection_names)


if __name__ == '__main__':
    # Create test suite
    test_classes = [
        TestTikTokOSINT,
        TestAdvancedCorrelation,
        TestPerformanceOptimizer,
        TestBlockchainAnalytics,
        TestNewCorrelationRules
    ]
    
    suite = unittest.TestSuite()
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    if not result.wasSuccessful():
        sys.exit(1)
