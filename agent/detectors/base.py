from abc import ABC, abstractmethod


class Detector(ABC):
    """A source of "which MAC addresses are currently on the network".

    Implementations may be active (arp-scan), passive/unprivileged
    (reading the OS neighbor table), or API-based (a WiFi controller).
    """

    @abstractmethod
    def scan(self) -> set[str]:
        """Return the set of currently visible MAC addresses, normalized
        to lowercase colon form (see `agent.utils.normalize_mac`)."""
        raise NotImplementedError
