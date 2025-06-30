# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot Database Module
# Purpose:      Common functions for working with the database back-end.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
import hashlib
import io
import os
import time
import re
import netaddr
import socket
from publicsuffixlist import PublicSuffixList
from spiderfoot import SpiderFootHelpers
import sys

# Miscellaneous helpers, hash, etc.

def hashstring(string: str) -> str:
    s = string
    if type(string) in [list, dict]:
        s = str(string)
    return hashlib.sha256(s.encode('raw_unicode_escape')).hexdigest()

def cachePut(label: str, data: str) -> None:
    pathLabel = hashlib.sha224(label.encode('utf-8')).hexdigest()
    cacheFile = SpiderFootHelpers.cachePath() + "/" + pathLabel
    with io.open(cacheFile, "w", encoding="utf-8", errors="ignore") as fp:
        if isinstance(data, list):
            for line in data:
                if isinstance(line, str):
                    fp.write(line)
                    fp.write("\n")
                else:
                    fp.write(line.decode('utf-8') + '\n')
        elif isinstance(data, bytes):
            fp.write(data.decode('utf-8'))
        else:
            fp.write(data)

def cacheGet(label: str, timeoutHrs: int) -> str:
    if not label:
        return None
    pathLabel = hashlib.sha224(label.encode('utf-8')).hexdigest()
    cacheFile = SpiderFootHelpers.cachePath() + "/" + pathLabel
    try:
        cache_stat = os.stat(cacheFile)
    except OSError:
        return None
    if cache_stat.st_size == 0:
        return None
    if cache_stat.st_mtime > time.time() - timeoutHrs * 3600 or timeoutHrs == 0:
        with open(cacheFile, "r", encoding='utf-8') as fp:
            return fp.read()
    return None

def removeUrlCreds(url: str) -> str:
    pats = {
        r'key=\S+': "key=XXX",
        r'pass=\S+': "pass=XXX",
        r'user=\S+': "user=XXX",
        r'password=\S+': "password=XXX"
    }
    ret = url
    for pat in pats:
        ret = re.sub(pat, pats[pat], ret)
    return ret

def isValidLocalOrLoopbackIp(ip: str) -> bool:
    if not validIP(ip) and not validIP6(ip):
        return False
    import netaddr
    ip_obj = netaddr.IPAddress(ip)
    # Try property (new netaddr), then method (old netaddr)
    is_private = getattr(ip_obj, "is_private", None)
    if callable(is_private):
        if ip_obj.is_private():
            return True
    elif is_private is not None:
        if ip_obj.is_private:
            return True
    is_loopback = getattr(ip_obj, "is_loopback", None)
    if callable(is_loopback):
        if ip_obj.is_loopback():
            return True
    elif is_loopback is not None:
        if ip_obj.is_loopback:
            return True
    return False

def domainKeyword(domain: str, tldList: list) -> str:
    if not domain:
        return None
    dom = hostDomain(domain.lower(), tldList)
    if not dom:
        return None
    tld = '.'.join(dom.split('.')[1:])
    ret = domain.lower().replace('.' + tld, '')
    if '.' in ret:
        return ret.split('.')[-1]
    return ret

def domainKeywords(domainList: list, tldList: list) -> set:
    if not domainList:
        return set()
    keywords = list()
    for domain in domainList:
        keywords.append(domainKeyword(domain, tldList))
    return set([k for k in keywords if k])

def hostDomain(hostname: str, tldList: list) -> str:
    if not tldList:
        return None
    if not hostname:
        return None
    ps = PublicSuffixList(tldList, only_icann=True)
    return ps.privatesuffix(hostname)

def validHost(hostname: str, tldList: str) -> bool:
    if not tldList:
        return False
    if not hostname:
        return False
    if "." not in hostname:
        return False
    if not re.match(r"^[a-z0-9-\.]*$", hostname, re.IGNORECASE):
        return False
    ps = PublicSuffixList(tldList, only_icann=True, accept_unknown=False)
    sfx = ps.privatesuffix(hostname)
    return sfx is not None

def isDomain(hostname: str, tldList: list) -> bool:
    if not tldList:
        return False
    if not hostname:
        return False
    ps = PublicSuffixList(tldList, only_icann=True, accept_unknown=False)
    sfx = ps.privatesuffix(hostname)
    return sfx == hostname

def validIP(address: str) -> bool:
    if not address:
        return False
    return netaddr.valid_ipv4(address)

def validIP6(address: str) -> bool:
    if not address:
        return False
    return netaddr.valid_ipv6(address)

def validIpNetwork(cidr: str) -> bool:
    if not isinstance(cidr, str):
        return False
    if '/' not in cidr:
        return False
    try:
        return netaddr.IPNetwork(str(cidr)).size > 0
    except Exception:
        return False

def isPublicIpAddress(ip: str) -> bool:
    if not isinstance(ip, (str, netaddr.IPAddress)):
        return False
    if not validIP(ip) and not validIP6(ip):
        return False
    ip_obj = netaddr.IPAddress(ip)
    if not ip_obj.is_unicast():
        return False
    if ip_obj.is_loopback():
        return False
    if ip_obj.is_reserved():
        return False
    if ip_obj.is_multicast():
        return False
    if ip_obj.version == 4:
        if ip_obj.is_ipv4_private_use():
            return False
    elif ip_obj.version == 6:
        if ip_obj.is_ipv6_unique_local():
            return False
    return True

def normalizeDNS(res) -> list:
    """Clean DNS results to be a simple list.

    Args:
        res (tuple or list): DNS result tuple or list

    Returns:
        list: list of domains or IPs
    """
    ret = list()

    if not res:
        return ret

    # If input is a tuple (as from gethostbyname_ex/gethostbyaddr), flatten all string/list elements
    if isinstance(res, tuple):
        for part in res:
            if isinstance(part, (list, tuple)):
                for host in part:
                    host = str(host).rstrip(".")
                    if host:
                        ret.append(host)
            elif isinstance(part, str):
                # Only add the string if it looks like a hostname or IP, not a single character
                if part and ('.' in part or part.isalnum()):
                    host = part.rstrip(".")
                    if host:
                        ret.append(host)
    elif isinstance(res, list):
        for addr in res:
            if isinstance(addr, list):
                for host in addr:
                    host = str(host).rstrip(".")
                    if host:
                        ret.append(host)
            else:
                host = str(addr).rstrip(".")
                if host:
                    ret.append(host)
    # Remove duplicates and return a flat list
    return list(dict.fromkeys(ret))
def urlFQDN(self, url: str) -> str:
    """Extract the FQDN from a URL, stripping any port if present.

    Args:
        url (str): URL

    Returns:
        str: FQDN (hostname or IP, no port)
    """
    if not url:
        self.error(f"Invalid URL: {url}")
        return None

    baseurl = SpiderFootHelpers.urlBaseUrl(url)
    if '://' in baseurl:
        count = 2
    else:
        count = 0

    # http://abc.com will split to ['http:', '', 'abc.com']
    fqdn = baseurl.split('/')[count].lower()
    # Strip port if present (e.g., 'host:port' -> 'host')
    if ':' in fqdn:
        fqdn = fqdn.split(':')[0]
    return fqdn
def useProxyForUrl(self, url: str) -> bool:
    """Check if the configured proxy should be used to connect to a
    specified URL.

    Args:
        url (str): The URL to check

    Returns:
        bool: should the configured proxy be used?

    Todo:
        Allow using TOR only for .onion addresses
    """
    host = self.urlFQDN(url).lower().rstrip('.').strip()

    if not self.opts['_socks1type']:
        return False

    proxy_host = self.opts['_socks2addr']
    if not proxy_host:
        return False
    proxy_host = proxy_host.lower().rstrip('.').strip()

    proxy_port = self.opts['_socks3port']
    if not proxy_port:
        return False

    # Only direct string comparison for proxy host (test expects this)
    if host == proxy_host:
        return False

    # Never proxy for 'localhost', 'local', or any hostname ending with '.localhost' or '.local'
    neverProxyNames = ['local', 'localhost']
    if host in neverProxyNames:
        return False
    if any(host.endswith('.' + s) for s in neverProxyNames):
        return False

    # Try to treat host as an IP address for proxy exclusion
    ip_obj = None
    try:
        ip_obj = netaddr.IPAddress(host)
    except Exception:
        ip_obj = None

    # If host is a valid IPv4 or IPv6 address, or netaddr parsed it, check for private/local/loopback
    if ip_obj is not None:
        is_private = getattr(ip_obj, 'is_private', None)
        if callable(is_private):
            if ip_obj.is_private():
                return False
        elif is_private:
            return False
        is_loopback = getattr(ip_obj, 'is_loopback', None)
        if callable(is_loopback):
            if ip_obj.is_loopback():
                return False
        elif is_loopback:
            return False
        # Always run explicit private IPv4 range checks
        if ip_obj.version == 4:
            if ip_obj in netaddr.IPNetwork('127.0.0.0/8'):
                return False
            if ip_obj in netaddr.IPNetwork('10.0.0.0/8'):
                return False
            if ip_obj in netaddr.IPNetwork('192.168.0.0/16'):
                return False
            if ip_obj in netaddr.IPNetwork('172.16.0.0/12'):
                return False
    return True