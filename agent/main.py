import logging
import time

from .config import Config, load_config
from .detectors.arp_scan import ArpScanDetector
from .detectors.base import Detector
from .detectors.controller import ControllerDetector
from .detectors.neigh_table import NeighTableDetector
from .presence import PresenceTracker
from .supabase_client import PresenceReporter

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('ada.agent')

# While a device-registration detection window is open (see
# rdosen4/supabase/schema.sql: dosen4.detection_windows), scan at this
# cadence instead of the normal SCAN_INTERVAL, so a Wi-Fi reconnect gets
# picked up quickly.
BURST_INTERVAL = 5.0

# While idle (no window open), still cheaply re-check for one opening
# this often -- a scan-free probe, not a full network scan -- instead of
# only checking once per SCAN_INTERVAL. Keeps "how soon do we notice a
# window opened" decoupled from "how often do we do a full scan".
IDLE_POLL_INTERVAL = 5.0


def _neigh_table(cfg: Config) -> NeighTableDetector:
    return NeighTableDetector(subnet_cidr=cfg.subnet_cidr, ping_sweep=cfg.ping_sweep)


DETECTOR_FACTORIES = {
    'arp_scan': lambda cfg: ArpScanDetector(interface=cfg.arp_scan_interface),
    'neigh_table': _neigh_table,
    'controller': lambda _cfg: ControllerDetector(),
}


def build_detector(cfg: Config) -> Detector:
    factory = DETECTOR_FACTORIES.get(cfg.detector)
    if factory is None:
        raise ValueError(f'Unknown DETECTOR {cfg.detector!r}; choose from {list(DETECTOR_FACTORIES)}')
    try:
        return factory(cfg)
    except (PermissionError, FileNotFoundError) as exc:
        if cfg.detector == 'arp_scan':
            logger.warning('%s -- falling back to neigh_table detector', exc)
            return _neigh_table(cfg)
        raise


def _run_cycle(detector: Detector, tracker: PresenceTracker, reporter: PresenceReporter) -> tuple[bool, float]:
    """Scan, report presence, and feed the detection-window RPC. Returns
    (window_open, seconds_remaining)."""
    detected = detector.scan()
    active = tracker.observe(detected)
    logger.info('scan: %d detected, %d active', len(detected), len(active))
    if active:
        reporter.report(active)
    # Detection cares about literal fresh appearances, so it gets the raw
    # per-cycle detected set, not the timeout-smoothed active set.
    return reporter.observe_detection(detected)


def main() -> None:
    cfg = load_config()
    detector = build_detector(cfg)
    tracker = PresenceTracker(timeout_seconds=cfg.presence_timeout)
    reporter = PresenceReporter(
        url=cfg.supabase_url,
        service_key=cfg.supabase_service_key,
        agent_id=cfg.agent_id,
        absence_timeout=cfg.presence_timeout,
        schema=cfg.supabase_schema,
    )

    logger.info(
        'ada agent starting: detector=%s schema=%s interval=%ss timeout=%ss',
        cfg.detector, cfg.supabase_schema, cfg.scan_interval, cfg.presence_timeout,
    )

    while True:
        cycle_start = time.monotonic()
        window_open = False
        remaining = 0.0
        try:
            window_open, remaining = _run_cycle(detector, tracker, reporter)
        except PermissionError as exc:
            logger.error('Detector lost privileges (%s); switching to neigh_table', exc)
            detector = _neigh_table(cfg)
        except Exception:
            logger.exception('Scan cycle failed, will retry next interval')

        if window_open:
            logger.info('detection window open, %.0fs remaining -- bursting', remaining)
            time.sleep(min(BURST_INTERVAL, max(1.0, remaining)))
            continue

        # Idle: sleep out the normal cadence in short increments, cheaply
        # re-checking (no network scan) for a newly-opened window so we
        # don't sit blind for the full SCAN_INTERVAL before noticing one.
        elapsed = time.monotonic() - cycle_start
        idle_remaining = max(0.0, cfg.scan_interval - elapsed)
        while idle_remaining > 0:
            nap = min(IDLE_POLL_INTERVAL, idle_remaining)
            time.sleep(nap)
            idle_remaining -= nap
            try:
                if reporter.is_detection_window_open():
                    break  # a window just opened -- go run a real cycle now
            except Exception:
                logger.exception('detection-window poll failed, continuing normal cadence')


if __name__ == '__main__':
    main()
