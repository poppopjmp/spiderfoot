# Legacy stub for test compatibility

from __future__ import annotations

"""Legacy stub providing a no-op search_base function for test compatibility."""

def search_base(config, *args, **kwargs) -> list:
    """Stub for legacy search_base utility. Returns empty list for test compatibility.
    Args:
        config: Configuration object
        *args: Additional positional arguments
        **kwargs: Additional keyword arguments
    Returns:
        list: Always returns an empty list
    """
    return []
