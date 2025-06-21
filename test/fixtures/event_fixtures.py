# -*- coding: utf-8 -*-
"""Event fixtures for testing SpiderFoot event handling."""

import pytest
import time
from spiderfoot.event import SpiderFootEvent


@pytest.fixture
def root_event():
    """Create a ROOT event for testing."""
    event = SpiderFootEvent(
        eventType='ROOT',
        data='example.com',
        module='',
        sourceEvent=None
    )
    return event


@pytest.fixture
def internet_name_event():
    """Create an INTERNET_NAME event."""
    return SpiderFootEvent(
        eventType='INTERNET_NAME',
        data='example.com',
        module='sfp_dnsresolve'
    )


@pytest.fixture
def ip_address_event():
    """Create an IP_ADDRESS event."""
    return SpiderFootEvent(
        eventType='IP_ADDRESS',
        data='93.184.216.34',
        module='sfp_dnsresolve'
    )


@pytest.fixture
def domain_name_event():
    """Create a DOMAIN_NAME event."""
    return SpiderFootEvent(
        eventType='DOMAIN_NAME',
        data='subdomain.example.com',
        module='sfp_dnsresolve'
    )


@pytest.fixture
def url_form_event():
    """Create a URL_FORM event."""
    return SpiderFootEvent(
        eventType='URL_FORM',
        data='https://example.com/contact',
        module='sfp_spider'
    )


@pytest.fixture
def event_chain(root_event, internet_name_event, ip_address_event):
    """Create a chain of related events."""
    # Set up event relationships
    internet_name_event.sourceEvent = root_event
    ip_address_event.sourceEvent = internet_name_event
    
    return {
        'root': root_event,
        'internet_name': internet_name_event,
        'ip_address': ip_address_event
    }


@pytest.fixture
def event_types_mapping():
    """Common event type mappings used in SpiderFoot."""
    return {
        'ROOT': 'Root',
        'INTERNET_NAME': 'Internet Name',
        'IP_ADDRESS': 'IP Address',
        'DOMAIN_NAME': 'Domain Name',
        'URL_FORM': 'Form URL',
        'EMAILADDR': 'Email Address',
        'PHONE_NUMBER': 'Phone Number',
        'AFFILIATE_INTERNET_NAME': 'Affiliate Internet Name',
        'CO_HOSTED_SITE': 'Co-Hosted Site',
        'LINKED_URL_INTERNAL': 'Linked URL - Internal',
        'LINKED_URL_EXTERNAL': 'Linked URL - External',
        'SSL_CERTIFICATE_ISSUED': 'SSL Certificate - Issued to',
        'SSL_CERTIFICATE_ISSUER': 'SSL Certificate - Issued by',
        'DNS_A': 'DNS A Record',
        'DNS_AAAA': 'DNS AAAA Record',
        'DNS_MX': 'DNS MX Record',
        'DNS_NS': 'DNS NS Record',
        'DNS_TXT': 'DNS TXT Record',
        'WHOIS_REGISTRAR': 'Registrar',
        'WHOIS_REGISTRANT_NAME': 'Registrant Name',
        'WHOIS_REGISTRANT_EMAIL': 'Registrant Email',
        'MALICIOUS_IPADDR': 'Malicious IP Address',
        'MALICIOUS_INTERNET_NAME': 'Malicious Internet Name',
        'VULNERABILITY': 'Vulnerability',
        'DARKWEB_MENTION': 'Dark Web Mention',
        'DATA_BREACH': 'Data Breach'
    }


@pytest.fixture
def sample_event_data():
    """Sample event data for different event types."""
    return {
        'INTERNET_NAME': 'example.com',
        'IP_ADDRESS': '93.184.216.34',
        'DOMAIN_NAME': 'subdomain.example.com',
        'URL_FORM': 'https://example.com/contact',
        'EMAILADDR': 'admin@example.com',
        'PHONE_NUMBER': '+1-555-123-4567',
        'DNS_A': '93.184.216.34',
        'DNS_MX': 'mail.example.com',
        'DNS_NS': 'ns1.example.com',
        'DNS_TXT': 'v=spf1 include:_spf.example.com ~all',
        'WHOIS_REGISTRAR': 'Example Registrar Inc.',
        'WHOIS_REGISTRANT_EMAIL': 'registrant@example.com',
        'SSL_CERTIFICATE_ISSUED': 'CN=example.com',
        'VULNERABILITY': 'CVE-2021-12345: Example vulnerability'
    }


@pytest.fixture
def events_with_different_confidence(sample_event_data):
    """Create events with different confidence levels."""
    events = []
    confidence_levels = [25, 50, 75, 100]
    
    for i, confidence in enumerate(confidence_levels):
        event = SpiderFootEvent(
            eventType='INTERNET_NAME',
            data=f'test{i}.example.com',
            module='test_module'
        )
        event.confidence = confidence
        events.append(event)
    
    return events


@pytest.fixture
def events_with_different_risk(sample_event_data):
    """Create events with different risk levels."""
    events = []
    risk_levels = [0, 25, 50, 75, 100]
    
    for i, risk in enumerate(risk_levels):
        event = SpiderFootEvent(
            eventType='INTERNET_NAME',
            data=f'risk{i}.example.com',
            module='test_module'
        )
        event.risk = risk
        events.append(event)
    
    return events


@pytest.fixture
def malicious_events():
    """Create events representing malicious indicators."""
    events = []
    
    # Malicious IP
    malicious_ip = SpiderFootEvent(
        eventType='MALICIOUS_IPADDR',
        data='192.168.1.100',
        module='sfp_malwarepatrol'
    )
    malicious_ip.risk = 100
    events.append(malicious_ip)
    
    # Malicious domain
    malicious_domain = SpiderFootEvent(
        eventType='MALICIOUS_INTERNET_NAME',
        data='malicious.example.com',
        module='sfp_virustotal'
    )
    malicious_domain.risk = 90
    events.append(malicious_domain)
    
    # Vulnerability
    vulnerability = SpiderFootEvent(
        eventType='VULNERABILITY',
        data='Critical SQL injection vulnerability found',
        module='sfp_tool_nuclei'
    )
    vulnerability.risk = 85
    events.append(vulnerability)
    
    return events


@pytest.fixture
def event_serialization_data():
    """Data for testing event serialization."""
    return {
        'valid_event_dict': {
            'generated': int(time.time()),
            'type': 'INTERNET_NAME',
            'data': 'example.com',
            'module': 'sfp_dnsresolve',
            'source': 'ROOT'
        },
        'invalid_event_dict': {
            'generated': 'invalid_timestamp',
            'type': '',
            'data': None,
            'module': 123,
            'source': []
        }
    }


@pytest.fixture
def bulk_events():
    """Create bulk events for performance testing."""
    events = []
    event_types = ['INTERNET_NAME', 'IP_ADDRESS', 'DOMAIN_NAME', 'URL_FORM']
    
    for i in range(100):
        event_type = event_types[i % len(event_types)]
        event = SpiderFootEvent(
            eventType=event_type,
            data=f'test-data-{i}.example.com',
            module=f'test_module_{i % 10}'
        )
        events.append(event)
    
    return events


class EventBuilder:
    """Builder class for creating test events with specific properties."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset to default values."""
        self.event_type = 'INTERNET_NAME'
        self.data = 'example.com'
        self.module = 'test_module'
        self.source_event = None
        self.confidence = 100
        self.visibility = 100
        self.risk = 0
        return self
        
    def with_type(self, event_type):
        """Set event type."""
        self.event_type = event_type
        return self
        
    def with_data(self, data):
        """Set event data."""
        self.data = data
        return self
        
    def with_module(self, module):
        """Set module name."""
        self.module = module
        return self
        
    def with_source(self, source_event):
        """Set source event."""
        self.source_event = source_event
        return self
        
    def with_confidence(self, confidence):
        """Set confidence level."""
        self.confidence = confidence
        return self
        
    def with_risk(self, risk):
        """Set risk level."""
        self.risk = risk
        return self
        
    def build(self):
        """Build the event."""
        event = SpiderFootEvent(
            eventType=self.event_type,
            data=self.data,
            module=self.module,
            sourceEvent=self.source_event
        )
        event.confidence = self.confidence
        event.visibility = self.visibility
        event.risk = self.risk
        return event


@pytest.fixture
def event_builder():
    """Event builder fixture."""
    return EventBuilder()
