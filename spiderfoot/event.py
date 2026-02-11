# Backward compatibility shim for spiderfoot.event
# Please import from spiderfoot.events instead.

from __future__ import annotations

from .events.event import SpiderFootEvent

__all__ = ["SpiderFootEvent"]
