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
from __future__ import annotations

"""Aggregates correlation rule results using configurable methods."""

import logging

class ResultAggregator:
    """Aggregates correlation rule results using configurable methods."""
    def __init__(self) -> None:
        """Initialize the result aggregator with a logger."""
        self.log = logging.getLogger("spiderfoot.correlation.aggregator")

    def aggregate(self, results, method='count') -> int | list:
        """Aggregate correlation results using the specified method."""
        # Example: aggregate results by method
        if method == 'count':
            return len(results)
        # Add more aggregation methods as needed
        return results
