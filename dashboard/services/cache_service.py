"""Fingerprint-based memory caching service with scenario isolation.

Ensures immutable artifact caching, scenario isolation, and safe key generation.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple


class CacheService:
    """Safe in-memory cache manager with content-hash invalidation and scenario scoping."""

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[str, Any]] = {}  # key -> (fingerprint, data)

    @staticmethod
    def compute_file_fingerprint(path: Path | str) -> str:
        """Compute SHA256 hex digest of file content to detect on-disk mutations."""
        p = Path(path).resolve()
        if not p.exists() or not p.is_file():
            return "NON_EXISTENT"
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def compute_dict_fingerprint(data: Dict[str, Any]) -> str:
        """Compute deterministic SHA256 hex digest of dictionary structure."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_cache_key(
        scenario_id: str,
        resource_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a scenario-isolated cache key.

        Guarantees scenario separation so Scenario A cannot contaminate Scenario B.
        """
        if not scenario_id:
            raise ValueError("scenario_id is required to prevent cross-scenario contamination")

        # Sanitize parameters
        clean_params = params or {}
        param_hash = CacheService.compute_dict_fingerprint(clean_params)
        return f"{scenario_id}::{resource_type}::{param_hash[:16]}"

    def get_or_set(
        self,
        cache_key: str,
        fingerprint: str,
        loader_fn: Callable[[], Any],
    ) -> Any:
        """Retrieve cached value if fingerprint matches, otherwise load, cache, and return."""
        if cache_key in self._store:
            stored_fingerprint, cached_data = self._store[cache_key]
            if stored_fingerprint == fingerprint:
                return cached_data

        # Cache miss or stale fingerprint
        data = loader_fn()
        self._store[cache_key] = (fingerprint, data)
        return data

    def invalidate(self, cache_key: Optional[str] = None) -> None:
        """Invalidate a specific cache key or clear the entire store."""
        if cache_key:
            self._store.pop(cache_key, None)
        else:
            self._store.clear()

    def size(self) -> int:
        """Return total items currently cached."""
        return len(self._store)


# Global default cache service instance
DEFAULT_CACHE_SERVICE = CacheService()
