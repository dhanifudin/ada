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
        try:
            detected = detector.scan()
            active = tracker.observe(detected)
            logger.info('scan: %d detected, %d active', len(detected), len(active))
            if active:
                reporter.report(active)
        except PermissionError as exc:
            logger.error('Detector lost privileges (%s); switching to neigh_table', exc)
            detector = _neigh_table(cfg)
        except Exception:
            logger.exception('Scan cycle failed, will retry next interval')

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(0.0, cfg.scan_interval - elapsed))


if __name__ == '__main__':
    main()
