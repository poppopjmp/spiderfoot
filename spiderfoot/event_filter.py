"""Backward compatibility shim for spiderfoot.event_filter.

Please import from spiderfoot.events.event_filter instead.
"""

from __future__ import annotations

from .events.event_filter import FilterAction, FilterResult, FilterStats, EventFilter, TypeFilter, PatternFilter, RiskFilter, PredicateFilter, ModuleFilter, EventFilterChain

__all__ = ['FilterAction', 'FilterResult', 'FilterStats', 'EventFilter', 'TypeFilter', 'PatternFilter', 'RiskFilter', 'PredicateFilter', 'ModuleFilter', 'EventFilterChain']
