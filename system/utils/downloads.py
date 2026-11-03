# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

""" Shared HTTP artifact download used by every training provider. """

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Optional

USER_AGENT = 'Mozilla/5.0 (CVCounterWEB Auto-Downloader)'
CHUNK_SIZE = 128 * 1024
MIN_ARTIFACT_BYTES = 1024 * 1024
PROGRESS_STEP = 5


def _emit(
        progress_callback: Optional[Callable[[dict], None]],
        name: str,
        percent: int,
        status: str = 'downloading',
        downloaded: Optional[int] = None,
        total: Optional[int] = None,
        message: str = '',
) -> None:
    """
    Send one download progress event.

    Args:
        progress_callback: Optional callback receiving progress dicts
        name (str): Artifact name
        percent (int): Completion percentage
        status (str): Lifecycle status
        downloaded (Optional[int]): Bytes written so far
        total (Optional[int]): Expected size in bytes
        message (str): Human readable status

    Returns:
        None
    """
    if progress_callback is None:
        return
    payload = {
        'status': status,
        'model': name,
        'model_name': name,
        'percent': percent,
        'progress': percent,
        'message': message or f'{name}: {percent}%',
    }
    if downloaded is not None:
        payload['downloaded'] = downloaded
    if total is not None:
        payload['total'] = total
    progress_callback(payload)


def _download_with_requests(
        url: str,
        tmp_path: Path,
        name: str,
        progress_callback: Optional[Callable[[dict], None]],
) -> bool:
    """
    Stream one URL to a temporary file, retrying once without TLS verification.

    Args:
        url (str): Download URL
        tmp_path (Path): Destination temporary path
        name (str): Artifact name used in progress events
        progress_callback: Optional callback receiving progress dicts

    Returns:
        bool: True when the full artifact was written
    """
    import requests
    import urllib3
    urllib3.disable_warnings()

    for verify_ssl in (True, False):
        try:
            with requests.get(
                url,
                stream=True,
                timeout=(10, 60),
                verify=verify_ssl,
                headers={'User-Agent': USER_AGENT},
            ) as response:
                if response.status_code != 200:
                    return False
                total_size = int(response.headers.get('Content-Length') or 0)
                downloaded = 0
                last_reported = 0
                with open(tmp_path, 'wb') as out_f:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        out_f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            if pct >= last_reported + PROGRESS_STEP or downloaded == total_size:
                                last_reported = pct
                                _emit(progress_callback, name, pct, downloaded, total_size,
                                      f'Downloading {name}: {pct}%')
                if total_size > 0 and downloaded < int(total_size * 0.95):
                    raise IOError(f'Incomplete download: {downloaded}/{total_size} bytes')
                return True
        except requests.exceptions.SSLError:
            if verify_ssl:
                continue
            raise
    return False


def _download_with_urllib(
        url: str,
        tmp_path: Path,
        name: str,
        progress_callback: Optional[Callable[[dict], None]],
) -> bool:
    """
    Stream one URL to a temporary file with the standard library.

    Args:
        url (str): Download URL
        tmp_path (Path): Destination temporary path
        name (str): Artifact name used in progress events
        progress_callback: Optional callback receiving progress dicts

    Returns:
        bool: True when the artifact was written
    """
    import urllib.request
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        total_size = int(response.headers.get('Content-Length') or 0)
        downloaded = 0
        last_reported = 0
        with open(tmp_path, 'wb') as out_f:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = int((downloaded / total_size) * 100)
                    if pct >= last_reported + PROGRESS_STEP or downloaded == total_size:
                        last_reported = pct
                        _emit(progress_callback, name, pct, downloaded, total_size,
                              f'Downloading {name}: {pct}%')
    return True


def download_file(
        urls: Iterable[str],
        dest_path: Path,
        name: Optional[str] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        min_bytes: int = MIN_ARTIFACT_BYTES,
) -> Path:
    """
    Download an artifact from the first working URL into dest_path.

    Args:
        urls (Iterable[str]): Candidate URLs in priority order
        dest_path (Path): Final file path
        name (Optional[str]): Artifact name used in progress events
        progress_callback: Optional callback receiving progress dicts
        min_bytes (int): Smallest accepted artifact size

    Returns:
        Path: The downloaded file

    Raises:
        RuntimeError: When every candidate URL failed
    """
    candidates = [url for url in urls if url]
    if not candidates:
        raise ValueError('download_file requires at least one URL')

    dest_path = Path(dest_path)
    artifact_name = name or dest_path.name
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(f'{dest_path.suffix}.tmp')
    last_error: Optional[Exception] = None

    _emit(progress_callback, artifact_name, 0, status='starting',
          message=f'Starting download of {artifact_name}...')

    for url in candidates:
        try:
            try:
                ok = _download_with_requests(url, tmp_path, artifact_name, progress_callback)
            except ImportError:
                ok = False
            if not ok:
                ok = _download_with_urllib(url, tmp_path, artifact_name, progress_callback)
            if ok and tmp_path.is_file() and tmp_path.stat().st_size >= min_bytes:
                if dest_path.is_file():
                    dest_path.unlink()
                tmp_path.replace(dest_path)
                _emit(progress_callback, artifact_name, 100, status='done',
                      message=f'Successfully downloaded {artifact_name}')
                return dest_path
            raise IOError(f'Downloaded artifact is missing or too small: {tmp_path}')
        except Exception as exc:
            last_error = exc
            if tmp_path.is_file():
                tmp_path.unlink(missing_ok=True)

    raise RuntimeError(
        f"Could not download '{artifact_name}': {last_error}. "
        f'Place the file manually at {dest_path} to continue.'
    )
