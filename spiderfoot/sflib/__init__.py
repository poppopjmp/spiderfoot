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
"""SpiderFoot core library (sflib).

Re-exports the main :class:`SpiderFoot` object together with configuration
serialisation helpers and common utility functions used across the entire
codebase.
"""

from .core import SpiderFoot
from .config import configSerialize, configUnserialize
from .helpers import *  # Expose other helpers as needed

__all__ = [
    'SpiderFoot',
    'configSerialize',
    'configUnserialize',
    # Re-exported from helpers
    'hashstring',
    'cachePut',
    'cacheGet',
    'removeUrlCreds',
    'isValidLocalOrLoopbackIp',
    'domainKeyword',
    'domainKeywords',
    'hostDomain',
    'validHost',
    'isDomain',
    'validIP',
    'validIP6',
    'validIpNetwork',
    'isPublicIpAddress',
    'normalizeDNS',
]
