"""Event Type Legacy Mapping for CSV Export Compatibility.

This module provides mapping from newer SpiderFoot event types to legacy
event types for backwards compatibility with existing Excel pivot table
workflows.

When exporting to CSV, new event types are automatically translated to
their legacy equivalents so existing reporting tools continue to work.
"""

# Mapping of new event types to legacy event types
# Format: 'NEW_TYPE': 'LEGACY_TYPE'
EVENT_TYPE_LEGACY_MAPPING = {
    # =========================================================================
    # VULNERABILITY TYPES -> Map to VULNERABILITY_DISCLOSURE (real type)
    # =========================================================================
    'VULNERABILITY_CVE_CRITICAL': 'VULNERABILITY_DISCLOSURE',
    'VULNERABILITY_CVE_HIGH': 'VULNERABILITY_DISCLOSURE',
    'VULNERABILITY_CVE_MEDIUM': 'VULNERABILITY_DISCLOSURE',
    'VULNERABILITY_CVE_LOW': 'VULNERABILITY_DISCLOSURE',
    'VULNERABILITY_GENERAL': 'VULNERABILITY_DISCLOSURE',

    # =========================================================================
    # COMPROMISED/BREACHED DATA -> Map to appropriate real types
    # =========================================================================
    'ACCOUNT_EXTERNAL_OWNED_COMPROMISED': 'ACCOUNT_EXTERNAL_OWNED',
    'ACCOUNT_EXTERNAL_USER_SHARED_COMPROMISED': 'ACCOUNT_EXTERNAL_OWNED',
    'PASSWORD_COMPROMISED': 'HASH',
    'HASH_COMPROMISED': 'HASH',
    'PHONE_NUMBER_COMPROMISED': 'PHONE_NUMBER',
    'LEAKSITE_CONTENT': 'LEAKSITE_URL',
    'DARKNET_MENTION_URL': 'LEAKSITE_URL',
    'DARKNET_MENTION_CONTENT': 'LEAKSITE_URL',

    # =========================================================================
    # DEFACEMENT TYPES -> Map to base entity types
    # =========================================================================
    'DEFACED_INTERNET_NAME': 'INTERNET_NAME',
    'DEFACED_IPADDR': 'IP_ADDRESS',
    'DEFACED_AFFILIATE_INTERNET_NAME': 'AFFILIATE_INTERNET_NAME',
    'DEFACED_COHOST': 'CO_HOSTED_SITE',
    'DEFACED_AFFILIATE_IPADDR': 'AFFILIATE_IPADDR',

    # =========================================================================
    # EMAIL SUBTYPES -> Map to base EMAILADDR
    # =========================================================================
    'EMAILADDR_DELIVERABLE': 'EMAILADDR',
    'EMAILADDR_DISPOSABLE': 'EMAILADDR',
    'EMAILADDR_GENERIC': 'EMAILADDR',
    'EMAILADDR_UNDELIVERABLE': 'EMAILADDR',

    # =========================================================================
    # CRYPTOCURRENCY -> Map Ethereum to Bitcoin equivalents
    # =========================================================================
    'ETHEREUM_ADDRESS': 'BITCOIN_ADDRESS',
    'ETHEREUM_BALANCE': 'BITCOIN_BALANCE',

    # =========================================================================
    # NETWORK/INFRASTRUCTURE TYPES
    # =========================================================================
    'BGP_AS_OWNER': 'BGP_AS_MEMBER',
    'NETBLOCK_OWNER': 'NETBLOCK_MEMBER',
    'NETBLOCKV6_OWNER': 'NETBLOCKV6_MEMBER',
    'NETBLOCK_WHOIS': 'DOMAIN_WHOIS',
    'UDP_PORT_OPEN': 'TCP_PORT_OPEN',
    'UDP_PORT_OPEN_INFO': 'TCP_PORT_OPEN_BANNER',
    'DNS_SRV': 'DNS_TEXT',
    'OPERATING_SYSTEM': 'SOFTWARE_USED',
    'DEVICE_TYPE': 'SOFTWARE_USED',

    # =========================================================================
    # SSL/TLS CERTIFICATE TYPES
    # =========================================================================
    'SSL_CERTIFICATE_EXPIRED': 'SSL_CERTIFICATE_EXPIRING',

    # =========================================================================
    # WEB CONTENT TYPES
    # =========================================================================
    'AFFILIATE_WEB_CONTENT': 'TARGET_WEB_CONTENT',
    'TARGET_WEB_COOKIE': 'TARGET_WEB_CONTENT',
    'SEARCH_ENGINE_WEB_CONTENT': 'TARGET_WEB_CONTENT',
    'URL_ADBLOCKED_EXTERNAL': 'LINKED_URL_EXTERNAL',
    'URL_ADBLOCKED_INTERNAL': 'LINKED_URL_INTERNAL',
    'URL_FLASH': 'URL_JAVASCRIPT',
    'URL_JAVA_APPLET': 'URL_JAVASCRIPT',

    # =========================================================================
    # HISTORIC URL TYPES -> Map to existing historic types
    # =========================================================================
    'URL_FORM_HISTORIC': 'INTERESTING_FILE_HISTORIC',
    'URL_FLASH_HISTORIC': 'URL_PASSWORD_HISTORIC',
    'URL_JAVASCRIPT_HISTORIC': 'URL_PASSWORD_HISTORIC',
    'URL_WEB_FRAMEWORK_HISTORIC': 'URL_PASSWORD_HISTORIC',
    'URL_JAVA_APPLET_HISTORIC': 'URL_PASSWORD_HISTORIC',
    'URL_STATIC_HISTORIC': 'URL_PASSWORD_HISTORIC',
    'URL_UPLOAD_HISTORIC': 'URL_PASSWORD_HISTORIC',

    # =========================================================================
    # PERSONAL/ENTITY INFORMATION
    # =========================================================================
    'PERSON_NAME': 'HUMAN_NAME',
    'DATE_HUMAN_DOB': 'HUMAN_NAME',
    'JOB_TITLE': 'HUMAN_NAME',
    'PHONE_NUMBER_TYPE': 'PHONE_NUMBER',
    'CREDIT_CARD_NUMBER': 'IBAN_NUMBER',

    # =========================================================================
    # MISCELLANEOUS TYPES
    # =========================================================================
    'AFFILIATE_DOMAIN_UNREGISTERED': 'AFFILIATE_DOMAIN_NAME',
    'CLOUD_STORAGE_BUCKET_OPEN': 'CLOUD_STORAGE_BUCKET',
    'BASE64_DATA': 'HASH',
    'ERROR_MESSAGE': 'HTTP_CODE',
    'JUNK_FILE': 'INTERESTING_FILE',
    'PROXY_HOST': 'IP_ADDRESS',
    'VPN_HOST': 'IP_ADDRESS',
    'TOR_EXIT_NODE': 'IP_ADDRESS',
    'PROVIDER_TELCO': 'PROVIDER_HOSTING',
    'SIMILAR_ACCOUNT_EXTERNAL': 'ACCOUNT_EXTERNAL_OWNED',
    'WIFI_ACCESS_POINT': 'GEOINFO',
    'WIKIPEDIA_PAGE_EDIT': 'PUBLIC_CODE_REPO',

    # =========================================================================
    # BLACKLIST/MALICIOUS TYPES
    # =========================================================================
    'BLACKLISTED_COHOST': 'BLACKLISTED_IPADDR',
    'BLACKLISTED_INTERNET_NAME': 'BLACKLISTED_IPADDR',
    'BLACKLISTED_NETBLOCK': 'BLACKLISTED_SUBNET',
    'MALICIOUS_ASN': 'MALICIOUS_IPADDR',
    'MALICIOUS_BITCOIN_ADDRESS': 'BITCOIN_ADDRESS',
    'MALICIOUS_INTERNET_NAME': 'MALICIOUS_IPADDR',
    'MALICIOUS_NETBLOCK': 'MALICIOUS_SUBNET',
    'MALICIOUS_PHONE_NUMBER': 'PHONE_NUMBER',
}

# Legacy types that are valid SpiderFoot event types
# (these are the actual types that exist in the SpiderFoot database)
LEGACY_EVENT_TYPES = {
    'ACCOUNT_EXTERNAL_OWNED',
    'AFFILIATE_COMPANY_NAME',
    'AFFILIATE_DESCRIPTION_ABSTRACT',
    'AFFILIATE_DESCRIPTION_CATEGORY',
    'AFFILIATE_DOMAIN_NAME',
    'AFFILIATE_DOMAIN_WHOIS',
    'AFFILIATE_EMAILADDR',
    'AFFILIATE_INTERNET_NAME',
    'AFFILIATE_INTERNET_NAME_HIJACKABLE',
    'AFFILIATE_INTERNET_NAME_UNRESOLVED',
    'AFFILIATE_IPADDR',
    'AFFILIATE_IPV6_ADDRESS',
    'APPSTORE_ENTRY',
    'BGP_AS_MEMBER',
    'BITCOIN_ADDRESS',
    'BITCOIN_BALANCE',
    'BLACKLISTED_AFFILIATE_INTERNET_NAME',
    'BLACKLISTED_AFFILIATE_IPADDR',
    'BLACKLISTED_IPADDR',
    'BLACKLISTED_SUBNET',
    'CLOUD_STORAGE_BUCKET',
    'CO_HOSTED_SITE',
    'CO_HOSTED_SITE_DOMAIN',
    'CO_HOSTED_SITE_DOMAIN_WHOIS',
    'COMPANY_NAME',
    'COUNTRY_NAME',
    'DESCRIPTION_ABSTRACT',
    'DESCRIPTION_CATEGORY',
    'DNS_SPF',
    'DNS_TEXT',
    'DOMAIN_NAME_PARENT',
    'DOMAIN_NAME',
    'DOMAIN_REGISTRAR',
    'DOMAIN_WHOIS',
    'EMAILADDR',
    'EMAILADDR_COMPROMISED',
    'GEOINFO',
    'HASH',
    'HTTP_CODE',
    'HUMAN_NAME',
    'IBAN_NUMBER',
    'INTERESTING_FILE',
    'INTERESTING_FILE_HISTORIC',
    'INTERNAL_IP_ADDRESS',
    'INTERNET_NAME',
    'INTERNET_NAME_UNRESOLVED',
    'IP_ADDRESS',
    'IPV6_ADDRESS',
    'LEAKSITE_URL',
    'LEI',
    'LINKED_URL_EXTERNAL',
    'LINKED_URL_INTERNAL',
    'MALICIOUS_AFFILIATE_INTERNET_NAME',
    'MALICIOUS_AFFILIATE_IPADDR',
    'MALICIOUS_COHOST',
    'MALICIOUS_EMAILADDR',
    'MALICIOUS_IPADDR',
    'MALICIOUS_SUBNET',
    'NETBLOCK_MEMBER',
    'NETBLOCKV6_MEMBER',
    'PGP_KEY',
    'PHONE_NUMBER',
    'PHYSICAL_ADDRESS',
    'PHYSICAL_COORDINATES',
    'PROVIDER_DNS',
    'PROVIDER_HOSTING',
    'PROVIDER_JAVASCRIPT',
    'PROVIDER_MAIL',
    'PUBLIC_CODE_REPO',
    'RAW_DNS_RECORDS',
    'RAW_FILE_META_DATA',
    'RAW_RIR_DATA',
    'SIMILARDOMAIN',
    'SIMILARDOMAIN_WHOIS',
    'SOCIAL_MEDIA',
    'SOFTWARE_USED',
    'SSL_CERTIFICATE_EXPIRING',
    'SSL_CERTIFICATE_ISSUED',
    'SSL_CERTIFICATE_ISSUER',
    'SSL_CERTIFICATE_MISMATCH',
    'SSL_CERTIFICATE_RAW',
    'TARGET_WEB_CONTENT',
    'TARGET_WEB_CONTENT_TYPE',
    'TCP_PORT_OPEN',
    'TCP_PORT_OPEN_BANNER',
    'URL_FORM',
    'URL_JAVASCRIPT',
    'URL_PASSWORD',
    'URL_PASSWORD_HISTORIC',
    'URL_STATIC',
    'URL_UPLOAD',
    'URL_WEB_FRAMEWORK',
    'USERNAME',
    'VULNERABILITY_DISCLOSURE',
    'WEB_ANALYTICS_ID',
    'WEBSERVER_BANNER',
    'WEBSERVER_HTTPHEADERS',
    'WEBSERVER_STRANGEHEADER',
    'WEBSERVER_TECHNOLOGY',
}


def translate_event_type(event_type: str, use_legacy: bool = True) -> str:
    """Translate a new event type to its legacy equivalent.

    Args:
        event_type: The event type to translate
        use_legacy: If True, translate new types to legacy types.
                   If False, return the original type unchanged.

    Returns:
        The legacy event type if a mapping exists, otherwise the original type.
    """
    if not use_legacy:
        return event_type

    return EVENT_TYPE_LEGACY_MAPPING.get(event_type, event_type)


def get_all_legacy_types() -> set:
    """Get the set of all legacy event types.

    Returns:
        Set of legacy event type strings.
    """
    return LEGACY_EVENT_TYPES.copy()


def get_mapping_info() -> dict:
    """Get information about the event type mappings.

    Returns:
        Dictionary with mapping statistics and details.
    """
    return {
        'total_mappings': len(EVENT_TYPE_LEGACY_MAPPING),
        'legacy_types_count': len(LEGACY_EVENT_TYPES),
        'mappings': EVENT_TYPE_LEGACY_MAPPING.copy(),
    }
