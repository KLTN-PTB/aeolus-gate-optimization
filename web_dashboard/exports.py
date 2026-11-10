"""Explicit export members, checksums, and atomic ZIP publication."""
import hashlib
import json
from pathlib import Path
import time
import uuid
import zipfile


def file_digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def replace_retry(source, destination):
    for attempt in range(61):
        try:
            source.replace(destination)
            return
        except PermissionError:
            if attempt == 60:
                raise
            time.sleep(.05)


def write_bundle(directory, names):
    members = sorted(set(names))
    if any(Path(name).name != name for name in members):
        raise ValueError('Export member must be a local file name')
    checksums = {name: file_digest(directory / name) for name in members}
    token = uuid.uuid4().hex
    checksum_temp = directory / f'checksums.{token}.tmp'
    temporary = directory / f'bundle.{token}.tmp'
    try:
        metadata = {'export_schema_version': 2, 'files': checksums}
        checksum_temp.write_text(json.dumps(metadata, sort_keys=True), encoding='utf-8')
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in members:
                archive.write(directory / name, name)
            archive.write(checksum_temp, 'checksums.json')
        metadata['bundle_sha256'] = file_digest(temporary)
        checksum_temp.write_text(json.dumps(metadata, sort_keys=True), encoding='utf-8')
        replace_retry(temporary, directory / 'bundle.zip')
        replace_retry(checksum_temp, directory / 'checksums.json')
    finally:
        checksum_temp.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)


def verify_exports(directory):
    metadata = json.loads((directory / 'checksums.json').read_text(encoding='utf-8'))
    if metadata.get('export_schema_version') != 2:
        raise ValueError('Unsupported export schema')
    for name, expected in metadata['files'].items():
        if Path(name).name != name or file_digest(directory / name) != expected:
            raise ValueError(f'Export file checksum mismatch: {name}')
    if file_digest(directory / 'bundle.zip') != metadata['bundle_sha256']:
        raise ValueError('Export bundle checksum mismatch')


def assignment_table(rows, *, waiting=False):
    import pandas as pd
    if rows:
        return pd.DataFrame(rows)
    types = dict(flight_id='string', gate_id='string', flight_index='int64', gate_index='int64',
        is_overflow='bool', is_reassignment='bool', occupancy_start_min='int64', occupancy_end_min='int64', assignment_state='string')
    if waiting:
        types.update(gate_wait_min='int64', additional_departure_delay_min='int64')
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in types.items()})
