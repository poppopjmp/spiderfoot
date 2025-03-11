# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         sfscan
# Purpose:      Scanning control functionality
#
# Author:       Steve Micallef <steve@binarypool.com>
# Maintainer:   poppopjmp
#
# Created:      11/03/2013
# Copyright:    (c) Steve Micallef 2013
# License:      MIT
# -----------------------------------------------------------------
import socket
import time
import queue
from time import sleep
from copy import deepcopy
from contextlib import suppress
from collections import OrderedDict

import dns.resolver

from sflib import SpiderFoot
from spiderfoot import (
    SpiderFootDb,
    SpiderFootEvent,
    SpiderFootPlugin,
    SpiderFootTarget,
    SpiderFootHelpers,
    SpiderFootThreadPool,
    SpiderFootCorrelator,
    logger,
)
