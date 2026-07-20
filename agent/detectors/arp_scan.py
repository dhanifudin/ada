import logging
import shutil
import subprocess

from ..utils import normalize_mac
from .base import Detector

logger = logging.getLogger(__name__)


class ArpScanDetector(Detector):
    """Active scan using the `arp-scan` tool.

    Reliable and fast, but needs elevated privileges to send raw ARP
    requests. Grant the capability once instead of running the whole
    agent as root:

        sudo setcap cap_net_raw+ep $(which arp-scan)

    If the capability isn't available, `scan()` raises PermissionError so
    the caller (see agent/main.py) can fall back to NeighTableDetector.
    """

    def __init__(self, interface: str | None = None):
        if shutil.which('arp-scan') is None:
            raise FileNotFoundError(
                "'arp-scan' binary not found. Install it (e.g. `apt install arp-scan`) "
                'or set DETECTOR=neigh_table in .env.'
            )
        self.interface = interface

    def scan(self) -> set[str]:
        cmd = ['arp-scan', '--localnet', '--quiet', '--ignoredups']
        if self.interface:
            cmd += ['--interface', self.interface]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or '').lower()
            if 'operation not permitted' in stderr or 'permission denied' in stderr:
                raise PermissionError(
                    'arp-scan lacks CAP_NET_RAW. Run '
                    '`sudo setcap cap_net_raw+ep $(which arp-scan)` or set DETECTOR=neigh_table.'
                ) from exc
            raise

        macs: set[str] = set()
        for line in result.stdout.splitlines():
            # arp-scan output is tab-separated: "<ip>\t<mac>\t<vendor>"
            parts = line.split('\t')
            if len(parts) >= 2:
                mac = normalize_mac(parts[1])
                if mac:
                    macs.add(mac)
        return macs
