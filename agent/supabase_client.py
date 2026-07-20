from datetime import datetime, timezone

from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions


class PresenceReporter:
    """Thin wrapper around the Supabase `report_presence` RPC.

    Uses the service_role key (server-side only, never shipped to the
    browser) so it can write regardless of the read-only RLS policies
    that protect the anon key used by the web frontend.
    """

    def __init__(
        self, url: str, service_key: str, agent_id: str, absence_timeout: int,
        schema: str = 'dosen4',
    ):
        # All attendance objects live in the `dosen4` schema (not `public`)
        # -- see rdosen4/supabase/schema.sql -- so the client must target it.
        self._client: Client = create_client(
            url, service_key, options=SyncClientOptions(schema=schema)
        )
        self.agent_id = agent_id
        self.absence_timeout = absence_timeout

    def report(self, macs: set[str]) -> None:
        seen_at = datetime.now(timezone.utc).isoformat()
        self._client.rpc('report_presence', {
            'macs': sorted(macs),
            'seen_at': seen_at,
            'agent_id': self.agent_id,
            'absence_timeout_seconds': self.absence_timeout,
        }).execute()

    def observe_detection(self, macs: set[str]) -> tuple[bool, float]:
        """Report the current raw scan to the device-registration detection-window
        RPC. A no-op server-side when no registration window is open. Returns
        (window_open, seconds_remaining) so the caller can decide how soon to
        scan again without a second round-trip.
        """
        resp = self._client.rpc('observe_macs_for_detection', {'p_macs': sorted(macs)}).execute()
        rows = resp.data or []
        if not rows:
            return False, 0.0
        row = rows[0]
        return bool(row.get('window_open')), float(row.get('seconds_remaining') or 0.0)

    def is_detection_window_open(self) -> bool:
        """Cheap, scan-free probe -- no network scan involved -- so the agent
        can poll frequently during its idle cadence without the cost of a
        full scan, to notice a newly-opened registration window sooner.
        """
        resp = self._client.rpc('is_detection_window_open', {}).execute()
        return bool(resp.data)
