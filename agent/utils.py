import re

_HEX12_RE = re.compile(r'^[0-9a-fA-F]{12}$')


def normalize_mac(raw: str | None) -> str | None:
    """Normalize any common MAC representation to lowercase colon form.

    Accepts "AA:BB:CC:DD:EE:FF", "aa-bb-cc-dd-ee-ff", "aabb.ccdd.eeff", or a
    bare "aabbccddeeff". Returns None if `raw` isn't a valid 48-bit MAC.
    """
    if not raw:
        return None
    hex_only = re.sub(r'[^0-9a-fA-F]', '', raw)
    if not _HEX12_RE.match(hex_only):
        return None
    hex_only = hex_only.lower()
    return ':'.join(hex_only[i:i + 2] for i in range(0, 12, 2))
