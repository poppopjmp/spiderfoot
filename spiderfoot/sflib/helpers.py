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
from publicsuffixlist import PublicSuffixList
from spiderfoot import SpiderFootHelpers

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

def normalizeDNS(res: list) -> list:
    ret = list()
    if not res:
        return ret
    for addr in res:
        if isinstance(addr, list):
            ret.extend(addr)
        else:
            ret.append(addr)
    return ret
