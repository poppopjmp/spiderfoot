"""Session security manager – lightweight stub.

Provides the ``SessionManager`` class expected by ``security_middleware.py``.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any


class SessionManager:
    """Track and validate user sessions."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        # session_id -> {ip, ua, last_active}
        self._sessions: dict[str, dict[str, Any]] = {}
        self._timeout: int = int(
            self.config.get("security.session_timeout", 3600)
        )

    def validate_session(
        self,
        session_id: str,
        client_ip: str,
        user_agent: str,
    ) -> bool:
        """Return True if the session is known and not expired."""
        info = self._sessions.get(session_id)
        if info is None:
            # first time – register
            self._sessions[session_id] = {
                "ip": client_ip,
                "ua": user_agent,
                "last_active": time.monotonic(),
            }
            return True

        # expiry check
        if time.monotonic() - info["last_active"] > self._timeout:
            del self._sessions[session_id]
            return False

        return True

    def update_session_activity(self, session_id: str) -> None:
        info = self._sessions.get(session_id)
        if info is not None:
            info["last_active"] = time.monotonic()
