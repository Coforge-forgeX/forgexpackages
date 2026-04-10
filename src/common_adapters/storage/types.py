
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class EncryptionOptions:
    """Provider-agnostic encryption options.

    For AWS S3:
      - sse: "AES256" or "aws:kms"
      - kms_key_id: KMS key ID or alias when sse == "aws:kms"
    For Azure Blob:
      - encryption_scope: Name of encryption scope (if used)
      - cpk: Dict with customer-provided key data (key, hash, algorithm), optional
    """

    sse: Optional[str] = None
    kms_key_id: Optional[str] = None
    encryption_scope: Optional[str] = None
    cpk: Optional[Dict[str, str]] = None
