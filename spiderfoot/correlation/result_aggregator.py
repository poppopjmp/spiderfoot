# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot Correlation Engine
# Purpose:      Common functions for enriching events with contextual information.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
import logging

class ResultAggregator:
    def __init__(self):
        self.log = logging.getLogger("spiderfoot.correlation.aggregator")

    def aggregate(self, results, method='count'):
        # Example: aggregate results by method
        if method == 'count':
            return len(results)
        # Add more aggregation methods as needed
        return results
