from .base import Detector


class ControllerDetector(Detector):
    """Placeholder for a future WiFi-controller/AP-API detector.

    Once the campus's WiFi infrastructure is known (Unifi Controller,
    Mikrotik RouterOS API, OpenWRT ubus/SSH, etc.), implement `scan()` to
    authenticate to it and return the set of currently-associated client
    MAC addresses. This avoids relying on ARP/neighbor visibility and
    works even across multiple APs/subnets.
    """

    def __init__(self, **_kwargs):
        raise NotImplementedError(
            'ControllerDetector is not implemented yet. Use DETECTOR=arp_scan or '
            'DETECTOR=neigh_table until a controller API integration is written.'
        )

    def scan(self) -> set[str]:
        raise NotImplementedError
