from datetime import datetime, timezone

from supabase import Client, create_client


class PresenceReporter:
    """Thin wrapper around the Supabase `report_presence` RPC.

    Uses the service_role key (server-side only, never shipped to the
    browser) so it can write regardless of the read-only RLS policies
    that protect the anon key used by the web frontend.
    """

    def __init__(self, url: str, service_key: str, agent_id: str, absence_timeout: int):
        self._client: Client = create_client(url, service_key)
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
