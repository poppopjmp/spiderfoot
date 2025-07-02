# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot SFLib Module
# Purpose:      Common functions for working with the database back-end.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
# Network, DNS, IP, socket, proxy, fetch, etc. utilities
import socket
import ssl
import requests
import OpenSSL
import cryptography
import dns.resolver
import urllib.parse
import time
import random
import inspect
from cryptography.hazmat.backends.openssl import backend
from spiderfoot import SpiderFootHelpers
from .helpers import validIP, validIP6
from datetime import datetime

def resolveHost(host: str) -> list:
    """Return a normalised IPv4 resolution of a hostname."""
    import socket
    from .helpers import normalizeDNS
    if not host:
        return []
    try:
        # Use gethostbyname_ex for patching/mocking compatibility in tests
        addrs = normalizeDNS(socket.gethostbyname_ex(host))
    except Exception:
        return []
    if not addrs:
        return []
    return list(set(addrs))

def resolveIP(ipaddr: str) -> list:
    """Return a normalised resolution of an IPv4 or IPv6 address as a flat list (not a tuple)."""
    import socket
    from .helpers import normalizeDNS, validIP, validIP6
    if not validIP(ipaddr) and not validIP6(ipaddr):
        return []
    try:
        addrs = normalizeDNS(socket.gethostbyaddr(ipaddr))
    except Exception:
        return []
    if not addrs:
        return []
    return list(set(addrs))

def resolveHost6(hostname: str) -> list:
    if not hostname:
        return []
    addrs = list()
    try:
        for r in socket.getaddrinfo(hostname, None, socket.AF_INET6):
            addrs.append(r[4][0])
    except Exception:
        return []
    if not addrs:
        return []
    return list(set(addrs))

def validateIP(host: str, ip: str) -> bool:
    if not host:
        return False
    addrs = []
    if validIP(ip):
        addrs = resolveHost(host)
    elif validIP6(ip):
        addrs = resolveHost6(host)
    else:
        return False
    if not addrs:
        return False
    return any(str(addr) == ip for addr in addrs)

def safeSocket(host: str, port: int, timeout: int) -> 'ssl.SSLSocket':
    sock = socket.create_connection((host, int(port)), int(timeout))
    sock.settimeout(int(timeout))
    return sock

def safeSSLSocket(host: str, port: int, timeout: int) -> 'ssl.SSLSocket':
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    s = socket.socket()
    s.settimeout(int(timeout))
    s.connect((host, int(port)))
    sock = context.wrap_socket(s, server_hostname=host)
    sock.do_handshake()
    return sock

def parseCert(rawcert: str, fqdn: str = None, expiringdays: int = 30) -> dict:
    if not rawcert:
        return {}
    ret = dict()
    if '\r' in rawcert:
        rawcert = rawcert.replace('\r', '')
    if isinstance(rawcert, str):
        rawcert = rawcert.encode('utf-8')
    cert = cryptography.x509.load_pem_x509_certificate(rawcert, backend)
    sslcert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, rawcert)
    sslcert_dump = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_TEXT, sslcert)
    ret['text'] = sslcert_dump.decode('utf-8', errors='replace')
    ret['issuer'] = str(cert.issuer)
    ret['altnames'] = list()
    ret['expired'] = False
    ret['expiring'] = False
    ret['mismatch'] = False
    ret['certerror'] = False
    ret['issued'] = str(cert.subject)
    # Expiry info
    try:
        not_after = cert.not_valid_after
        now = datetime.utcnow()
        if not_after < now:
            ret['expired'] = True
        elif (not_after - now).days < expiringdays:
            ret['expiring'] = True
    except Exception:
        pass
    # SANs
    try:
        ext = cert.extensions.get_extension_for_class(cryptography.x509.SubjectAlternativeName)
        ret['altnames'] = ext.value.get_values_for_type(cryptography.x509.DNSName)
    except Exception:
        pass
    certhosts = list()
    try:
        certhosts.append(cert.subject.get_attributes_for_oid(cryptography.x509.NameOID.COMMON_NAME)[0].value)
        certhosts.extend(ret['altnames'])
    except Exception:
        pass
    # Check for mismatch
    if fqdn and ret['issued']:
        if fqdn not in certhosts:
            ret['mismatch'] = True
    return ret

def getSession() -> 'requests.sessions.Session':
    session = requests.session()
    return session

def useProxyForUrl(url: str, opts=None, urlFQDN=None, isValidLocalOrLoopbackIp=None) -> bool:
    if opts is None:
        return False
    if urlFQDN is None:
        urlFQDN = lambda u: u
    if isValidLocalOrLoopbackIp is None:
        isValidLocalOrLoopbackIp = lambda ip: False
    host = urlFQDN(url).lower()
    if not opts.get('_socks1type'):
        return False
    proxy_host = opts.get('_socks2addr')
    if not proxy_host:
        return False
    proxy_port = opts.get('_socks3port')
    if not proxy_port:
        return False
    if host == proxy_host.lower():
        return False
    # Localhost and private IPs should not use proxy
    if host in ("localhost", "127.0.0.1", "::1"):
        return False
    if isValidLocalOrLoopbackIp(host):
        return False
    if validIP(host):
        # If it's a valid IP, check if it's local/private
        if isValidLocalOrLoopbackIp(host):
            return False
    return True

def fetchUrl(url: str, cookies: str = None, timeout: int = 30, useragent: str = "SpiderFoot", headers: dict = None, noLog: bool = False, postData: str = None, disableContentEncoding: bool = False, sizeLimit: int = None, headOnly: bool = False, verify: bool = True) -> dict:
    if not isinstance(url, str):
        return None
    if not url or not url.strip():
        return None
    url = url.strip()
    try:
        parsed_url = urllib.parse.urlparse(url)
    except Exception:
        return None
    if parsed_url.scheme not in ['http', 'https']:
        return None
    result = {
        'code': None,
        'status': None,
        'content': None,
        'headers': None,
        'realurl': url
    }
    url = url.strip()
    try:
        parsed_url = urllib.parse.urlparse(url)
    except Exception:
        return result
    if parsed_url.scheme not in ['http', 'https']:
        return result
    session = getSession()
    try:
        if headOnly:
            resp = session.head(url, timeout=timeout, headers=headers, verify=verify)
        elif postData:
            resp = session.post(url, data=postData, timeout=timeout, headers=headers, verify=verify)
        else:
            resp = session.get(url, timeout=timeout, headers=headers, verify=verify)
        result['code'] = str(resp.status_code)
        result['status'] = resp.reason
        result['content'] = resp.content.decode('utf-8', errors='replace')
        result['headers'] = dict(resp.headers)
        result['realurl'] = resp.url
    except Exception:
        pass
    return result


def checkDnsWildcard(target: str) -> bool:
    if not target:
        return False
    randpool = 'bcdfghjklmnpqrstvwxyz3456789'
    randhost = ''.join([random.SystemRandom().choice(randpool) for _ in range(10)])
    if not resolveHost(randhost + "." + target):
        return False
    return True
