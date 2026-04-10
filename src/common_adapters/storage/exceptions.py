
from __future__ import annotations

class StorageError(Exception):
    """Base class for storage-related errors with provider-agnostic semantics."""

class NotFoundError(StorageError):
    pass

class ConflictError(StorageError):
    pass

class AuthError(StorageError):
    pass
