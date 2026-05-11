
from __future__ import annotations
import logging

logger = logging.getLogger("storage_adapter")

# Configure a conservative default logger; applications can override.
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)s storage_adapter %(message)s',
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
