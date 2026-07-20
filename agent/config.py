import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None or val == '':
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


@dataclass(frozen=True)
class Config:
    supabase_url: str
    supabase_service_key: str
    agent_id: str
    detector: str
    scan_interval: int
    presence_timeout: int
    subnet_cidr: str | None
    ping_sweep: bool
    arp_scan_interface: str | None


def load_config() -> Config:
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    if not url or not key:
        raise RuntimeError(
            'SUPABASE_URL and SUPABASE_SERVICE_KEY must be set. Copy .env.example to .env and fill it in.'
        )
    return Config(
        supabase_url=url,
        supabase_service_key=key,
        agent_id=os.getenv('AGENT_ID', 'ada-agent'),
        detector=os.getenv('DETECTOR', 'neigh_table'),
        scan_interval=_env_int('SCAN_INTERVAL', 30),
        presence_timeout=_env_int('PRESENCE_TIMEOUT', 120),
        subnet_cidr=os.getenv('SUBNET_CIDR') or None,
        ping_sweep=_env_bool('PING_SWEEP', True),
        arp_scan_interface=os.getenv('ARP_SCAN_INTERFACE') or None,
    )
