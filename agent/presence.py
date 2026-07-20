from datetime import datetime, timedelta, timezone


class PresenceTracker:
    """Smooths transient scan misses.

    A MAC address stays "active" until it hasn't been observed for
    `timeout_seconds`, even if a single scan cycle misses it (e.g. a
    phone briefly drops off WiFi to sleep its radio). The Supabase RPC
    applies its own server-side absence timeout as the ultimate source
    of truth, so this is purely a local smoothing layer.
    """

    def __init__(self, timeout_seconds: int):
        self.timeout = timedelta(seconds=timeout_seconds)
        self._last_seen: dict[str, datetime] = {}

    def observe(self, detected: set[str]) -> set[str]:
        now = datetime.now(timezone.utc)
        for mac in detected:
            self._last_seen[mac] = now

        active = {mac for mac, ts in self._last_seen.items() if now - ts <= self.timeout}

        # Prune entries well past the timeout so the dict doesn't grow forever.
        stale_before = now - (self.timeout * 3)
        self._last_seen = {mac: ts for mac, ts in self._last_seen.items() if ts >= stale_before}

        return active
