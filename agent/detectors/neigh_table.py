import concurrent.futures
import ipaddress
import logging
import re
import subprocess

from ..utils import normalize_mac
from .base import Detector

logger = logging.getLogger(__name__)

_NEIGH_MAC_RE = re.compile(r'lladdr\s+([0-9a-fA-F:]{17})')


class NeighTableDetector(Detector):
    """Unprivileged fallback: reads the OS neighbor/ARP table (`ip neigh`).

    Needs no raw sockets or root, but only reports devices this host has
    already exchanged traffic with. To increase the catch rate, it can
    optionally run a plain ICMP ping sweep first (ordinary `ping`, no
    special privileges on Linux) to nudge the kernel into populating
    fresh neighbor entries.
    """

    def __init__(self, subnet_cidr: str | None = None, ping_sweep: bool = True):
        self.subnet_cidr = subnet_cidr
        self.ping_sweep = ping_sweep and bool(subnet_cidr)

    def scan(self) -> set[str]:
        if self.ping_sweep:
            self._sweep()
        return self._read_neigh_table()

    def _sweep(self) -> None:
        if not self.subnet_cidr:
            return
        try:
            network = ipaddress.ip_network(self.subnet_cidr, strict=False)
        except ValueError:
            logger.warning('Invalid SUBNET_CIDR %r, skipping ping sweep', self.subnet_cidr)
            return

        hosts = list(network.hosts())
        if len(hosts) > 1024:
            logger.warning(
                'Subnet %s has %d hosts, too large for a ping sweep; skipping. '
                'Narrow SUBNET_CIDR or rely on organic traffic.',
                self.subnet_cidr, len(hosts),
            )
            return

        def ping(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
            subprocess.run(
                ['ping', '-c', '1', '-W', '1', str(ip)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
            list(pool.map(ping, hosts))

    def _read_neigh_table(self) -> set[str]:
        try:
            result = subprocess.run(
                ['ip', 'neigh', 'show'], capture_output=True, text=True, timeout=10, check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise RuntimeError(f'Unable to read neighbor table via `ip neigh show`: {exc}') from exc

        macs: set[str] = set()
        for line in result.stdout.splitlines():
            if ' FAILED' in line or ' INCOMPLETE' in line:
                continue
            match = _NEIGH_MAC_RE.search(line)
            if match:
                mac = normalize_mac(match.group(1))
                if mac:
                    macs.add(mac)
        return macs
