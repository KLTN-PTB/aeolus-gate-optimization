"""Bounded structural inspection for raw Aeolus Flight Chain archives.

The inspector reads only the ZIP central directory and the small ``data.pkl``
metadata member from each PyTorch archive. Tensor storage members are never
opened, extracted, deserialized, or loaded into RAM.
"""

from __future__ import annotations

import io
import json
import pickle
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from src.data.access_guard import assert_data_access_allowed
from src.data.load_aeolus import load_base_config, resolve_project_root


CHAIN_AUDIT_VERSION: Final = "v1"
EXPECTED_YEARS: Final = tuple(range(2016, 2025))
EXPECTED_SPLITS: Final = ("train", "val", "test")
MAX_PICKLE_METADATA_BYTES: Final = 64 * 1024
CHAIN_FILENAME_PATTERNS: Final = (
    re.compile(r"^(train|val|test)_flight_chain_(20(?:1[6-9]|2[0-4]))\.pt$"),
    re.compile(r"^flight_chain_(train|val|test)_(20(?:1[6-9]|2[0-4]))\.pt$"),
)
STORAGE_DTYPES: Final = {
    "FloatStorage": "float32",
    "DoubleStorage": "float64",
    "HalfStorage": "float16",
    "BFloat16Storage": "bfloat16",
    "ByteStorage": "uint8",
    "CharStorage": "int8",
    "ShortStorage": "int16",
    "IntStorage": "int32",
    "LongStorage": "int64",
    "BoolStorage": "bool",
}


@dataclass(frozen=True)
class _StorageTag:
    name: str
    dtype: str


@dataclass(frozen=True)
class _StorageMetadata:
    storage_type: str
    dtype: str
    key: str
    device: str
    numel: int


@dataclass(frozen=True)
class TensorMetadata:
    storage_type: str
    dtype: str
    storage_key: str
    storage_numel: int
    storage_offset: int
    shape: tuple[int, ...]
    stride: tuple[int, ...]
    requires_grad: bool


class _TensorDatasetMetadata:
    """Passive target used in place of torch.utils.data.TensorDataset."""


def _rebuild_tensor_metadata(
    storage: _StorageMetadata,
    storage_offset: int,
    size: tuple[int, ...],
    stride: tuple[int, ...],
    requires_grad: bool,
    _backward_hooks: Any,
) -> TensorMetadata:
    if not isinstance(storage, _StorageMetadata):
        raise pickle.UnpicklingError("Unexpected tensor storage metadata")
    return TensorMetadata(
        storage_type=storage.storage_type,
        dtype=storage.dtype,
        storage_key=storage.key,
        storage_numel=storage.numel,
        storage_offset=int(storage_offset),
        shape=tuple(int(value) for value in size),
        stride=tuple(int(value) for value in stride),
        requires_grad=bool(requires_grad),
    )


class _MetadataOnlyUnpickler(pickle.Unpickler):
    """Restricted unpickler that reconstructs passive metadata objects only."""

    def find_class(self, module: str, name: str) -> Any:
        if module == "torch.utils.data.dataset" and name == "TensorDataset":
            return _TensorDatasetMetadata
        if module == "torch._utils" and name == "_rebuild_tensor_v2":
            return _rebuild_tensor_metadata
        if module == "torch" and name in STORAGE_DTYPES:
            return _StorageTag(name=name, dtype=STORAGE_DTYPES[name])
        if module == "collections" and name == "OrderedDict":
            from collections import OrderedDict

            return OrderedDict
        raise pickle.UnpicklingError(f"Unsupported pickle global: {module}.{name}")

    def persistent_load(self, persistent_id: Any) -> _StorageMetadata:
        if not isinstance(persistent_id, tuple) or len(persistent_id) != 5:
            raise pickle.UnpicklingError("Unexpected persistent storage identifier")
        kind, storage_tag, key, device, numel = persistent_id
        if kind != "storage" or not isinstance(storage_tag, _StorageTag):
            raise pickle.UnpicklingError("Unsupported persistent object")
        return _StorageMetadata(
            storage_type=storage_tag.name,
            dtype=storage_tag.dtype,
            key=str(key),
            device=str(device),
            numel=int(numel),
        )


def _relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _parse_chain_filename(filename: str) -> tuple[str, int]:
    for pattern in CHAIN_FILENAME_PATTERNS:
        match = pattern.fullmatch(filename)
        if match is not None:
            split, year_text = match.groups()
            return split, int(year_text)
    raise ValueError(f"Unexpected Flight Chain filename: {filename}")


def inspect_chain_archive(path: Path, *, project_root: Path | None = None) -> dict[str, Any]:
    """Inspect one Chain archive without reading any tensor storage payload."""
    root = resolve_project_root(project_root)
    source = path.resolve()
    split, year = _parse_chain_filename(source.name)
    year_text = str(year)
    expected_parent = (root / "data" / "raw" / "chain" / year_text).resolve()
    if source.parent != expected_parent:
        raise ValueError(f"Flight Chain path/year mismatch: {_relative_path(source, root)}")

    assert_data_access_allowed(year, "schema_audit")
    stat_before = source.stat()
    with zipfile.ZipFile(source, mode="r") as archive:
        members = archive.infolist()
        pickle_members = [member for member in members if member.filename.endswith("/data.pkl")]
        if len(pickle_members) != 1:
            raise ValueError(f"Expected one data.pkl member in {source.name}")
        pickle_member = pickle_members[0]
        if pickle_member.file_size > MAX_PICKLE_METADATA_BYTES:
            raise ValueError(
                f"Refusing metadata pickle larger than {MAX_PICKLE_METADATA_BYTES} bytes"
            )
        storage_members = [
            member
            for member in members
            if "/data/" in member.filename and not member.is_dir()
        ]
        pickle_bytes = archive.read(pickle_member)

    dataset = _MetadataOnlyUnpickler(io.BytesIO(pickle_bytes)).load()
    tensors = getattr(dataset, "tensors", None)
    if not isinstance(tensors, tuple) or not tensors:
        raise ValueError(f"No TensorDataset tensor metadata found in {source.name}")
    if not all(isinstance(tensor, TensorMetadata) for tensor in tensors):
        raise ValueError(f"Unexpected object in TensorDataset metadata for {source.name}")

    stat_after = source.stat()
    if stat_before.st_size != stat_after.st_size or stat_before.st_mtime_ns != stat_after.st_mtime_ns:
        raise RuntimeError(f"Raw archive changed during inspection: {source.name}")

    tensor_payload = [asdict(tensor) for tensor in tensors]
    return {
        "year": year,
        "split": split,
        "source_relative_path": _relative_path(source, root),
        "file_size_bytes": stat_before.st_size,
        "mtime_ns": stat_before.st_mtime_ns,
        "container": "pytorch_zip_archive",
        "archive_member_count": len(members),
        "pickle_metadata_member": pickle_member.filename,
        "pickle_metadata_bytes_read": len(pickle_bytes),
        "storage_member_count": len(storage_members),
        "storage_payload_bytes_declared": sum(member.file_size for member in storage_members),
        "storage_payload_bytes_read": 0,
        "tensor_count": len(tensor_payload),
        "sample_count": tensor_payload[0]["shape"][0],
        "tensors": tensor_payload,
    }


def audit_chain_archives(*, project_root: Path | None = None) -> dict[str, Any]:
    """Audit all 27 archives sequentially and return a versioned manifest."""
    root = resolve_project_root(project_root)
    config = load_base_config(project_root=root)
    chain_root = root / config["data"]["raw_chain_path"]
    files = sorted(chain_root.rglob("*.pt"), key=lambda item: item.as_posix())
    if len(files) != len(EXPECTED_YEARS) * len(EXPECTED_SPLITS):
        raise ValueError(f"Expected 27 Chain files, found {len(files)}")

    reports: list[dict[str, Any]] = []
    for year in EXPECTED_YEARS:
        year_files = sorted((chain_root / str(year)).glob("*.pt"), key=lambda item: item.name)
        observed_splits = {_parse_chain_filename(item.name)[0] for item in year_files}
        if len(year_files) != 3 or observed_splits != set(EXPECTED_SPLITS):
            raise ValueError(f"Expected train/val/test archives for {year}")
        for path in year_files:
            reports.append(inspect_chain_archive(path, project_root=root))

    signatures = {
        tuple(
            (tensor["dtype"], tuple(tensor["shape"][1:]), tuple(tensor["stride"][1:]))
            for tensor in report["tensors"]
        )
        for report in reports
    }
    manifest = {
        "audit_version": CHAIN_AUDIT_VERSION,
        "config_version": str(config["project"]["version"]),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "ZIP central directory plus restricted data.pkl metadata only",
        "safety": {
            "one_file_at_a_time": True,
            "torch_load_used": False,
            "tensor_storage_payload_read": False,
            "csv_content_read": False,
            "model_performance_access": False,
        },
        "file_count": len(reports),
        "years": list(EXPECTED_YEARS),
        "splits_per_year": list(EXPECTED_SPLITS),
        "total_source_bytes": sum(report["file_size_bytes"] for report in reports),
        "cross_year_structure_consistent": len(signatures) == 1,
        "reports": reports,
    }
    return manifest


def write_chain_audit_manifest(
    manifest: dict[str, Any], *, project_root: Path | None = None
) -> Path:
    """Write generated evidence outside raw-data directories."""
    root = resolve_project_root(project_root)
    output = root / "artifacts" / "manifests" / "flight_chain_structure_audit_v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output
