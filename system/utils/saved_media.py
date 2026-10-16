# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 29.07.2026
# Updated: 31.07.2026
# Website: https://bespredel.name

from __future__ import annotations

import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import cv2

from system.utils.logger import Logger
from system.utils.paths import get_project_root, resolve_project_path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.webm'}

# Browser-friendly encode candidates (OpenCV fourcc, output suffix).
_WEB_ENCODE_CANDIDATES = (
    ('avc1', '.mp4'),
    ('H264', '.mp4'),
    ('vp09', '.webm'),
    ('VP90', '.webm'),
)

_convert_locks: dict[str, threading.Lock] = {}
_convert_locks_guard = threading.Lock()
_logger = Logger()


def _safe_location_key(location: str) -> str:
    """
    Get the safe location key.
    
    Args:
        location (str): The location
    
    Returns:
        str: The safe location key
    """
    return re.sub(r'[^A-Za-z0-9-_]+', '', location or '')


def _is_safe_filename(filename: str) -> bool:
    """
    Check if the filename is safe.
    
    Args:
        filename (str): The filename
    
    Returns:
        bool: True if the filename is safe
    """
    if not filename or filename != Path(filename).name:
        return False
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    return True


def _format_size(num_bytes: int) -> str:
    """
    Format the size.
    
    Args:
        num_bytes (int): The number of bytes
    
    Returns:
        str: The formatted size
    """
    value = float(num_bytes)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            if unit == 'B':
                return f'{int(value)} {unit}'
            return f'{value:.1f} {unit}'
        value /= 1024.0
    return f'{num_bytes} B'


def _file_meta(path: Path) -> dict[str, Any]:
    """
    Get the file metadata.
    
    Args:
        path (Path): The path to the file
    
    Returns:
        dict[str, Any]: The file metadata
    """
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime)
    return {
        'name': path.name,
        'size': stat.st_size,
        'size_label': _format_size(stat.st_size),
        'mtime': mtime,
        'mtime_label': mtime.strftime('%d.%m.%Y %H:%M:%S'),
    }


def images_dir_for_location(location: str, config=None) -> Path:
    """
    Resolve the folder where capture images for ``location`` are stored.

    Prefers ``detections.<location>.dataset_create.path``, else
    ``storage/saved_images/<location>``.
    
    Args:
        location (str): The location
        config (Optional[dict]): The configuration
    
    Returns:
        Path: The path to the images directory
    """
    root = get_project_root()
    safe = _safe_location_key(location)
    custom = None
    if config is not None:
        custom = (config.get(f'detections.{location}.dataset_create.path')
                  or config.get(f'detections.{safe}.dataset_create.path'))
    if custom:
        return Path(resolve_project_path(custom, str(root)))
    return Path(resolve_project_path(f'storage/saved_images/{safe or location}', str(root)))


def recordings_dir_for_location(location: str, config=None) -> Path:
    """
    Resolve the folder where recordings for ``location`` are stored.

    Base path from ``detections.<location>.recording.path`` or detection_default,
    then ``/<safe_location>/``.
    
    Args:
        location (str): The location
        config (Optional[dict]): The configuration
    
    Returns:
        Path: The path to the recordings directory
    """
    root = get_project_root()
    safe = _safe_location_key(location)
    base = 'storage/saved_recordings'
    if config is not None:
        base = (
                config.get(f'detections.{location}.recording.path')
                or config.get(f'detections.{safe}.recording.path')
                or config.get('detection_default.recording.path')
                or base
        )
    base_path = Path(resolve_project_path(base, str(root)))
    return base_path / (safe or location)


def web_cache_dir_for_location(location: str) -> Path:
    """
    Get the cache directory for browser-playable re-encodes and poster frames.
    
    Args:
        location (str): The location
    
    Returns:
        Path: The path to the cache directory
    """
    root = get_project_root()
    safe = _safe_location_key(location)
    path = Path(resolve_project_path(f'storage/saved_recordings_web/{safe or location}', str(root)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_saved_images(
        location: str,
        config=None,
        limit: int = 200,
        offset: int = 0,
) -> list[dict[str, Any]]:
    """
    List the saved images.
    
    Args:
        location (str): The location
        config (Optional[dict]): The configuration
        limit (int): The limit
        offset (int): The offset (0-based) into the sorted results
    
    Returns:
        list[dict[str, Any]]: The list of saved images
    """
    folder = images_dir_for_location(location, config)
    if not folder.is_dir():
        return []
    files = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    offset = max(0, int(offset or 0))
    limit = max(0, int(limit or 0))
    if limit == 0:
        return []
    files = files[offset: offset + limit]
    return [_file_meta(p) for p in files]


def list_saved_recordings(
        location: str,
        config=None,
        limit: int = 100,
        offset: int = 0,
) -> list[dict[str, Any]]:
    """
    List the saved recordings.
    
    Args:
        location (str): The location
        config (Optional[dict]): The configuration
        limit (int): The limit
        offset (int): The offset (0-based) into the sorted results
    
    Returns:
        list[dict[str, Any]]: The list of saved recordings
    """
    folder = recordings_dir_for_location(location, config)
    if not folder.is_dir():
        return []
    files = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    offset = max(0, int(offset or 0))
    limit = max(0, int(limit or 0))
    if limit == 0:
        return []
    files = files[offset: offset + limit]
    return [_file_meta(p) for p in files]


def count_saved_images(location: str, config=None) -> int:
    """
    Count saved images for ``location``.

    This is used for server-side pagination on the reports page.
    """
    folder = images_dir_for_location(location, config)
    if not folder.is_dir():
        return 0
    return sum(
        1 for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def count_saved_recordings(location: str, config=None) -> int:
    """
    Count saved recordings for ``location``.

    This is used for server-side pagination on the reports page.
    """
    folder = recordings_dir_for_location(location, config)
    if not folder.is_dir():
        return 0
    return sum(
        1 for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )


def resolve_saved_image(location: str, filename: str, config=None) -> Optional[Path]:
    """
    Resolve the saved image.
    
    Args:
        location (str): The location
        filename (str): The filename
        config (Optional[dict]): The configuration
    
    Returns:
        Optional[Path]: The path to the saved image
    """
    if not _is_safe_filename(filename):
        return None
    if Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    folder = images_dir_for_location(location, config).resolve()
    path = (folder / filename).resolve()
    try:
        path.relative_to(folder)
    except ValueError:
        return None
    return path if path.is_file() else None


def resolve_saved_recording(location: str, filename: str, config=None) -> Optional[Path]:
    """
    Resolve the saved recording.
    
    Args:
        location (str): The location
        filename (str): The filename
        config (Optional[dict]): The configuration
    
    Returns:
        Optional[Path]: The path to the saved recording
    """
    if not _is_safe_filename(filename):
        return None
    if Path(filename).suffix.lower() not in VIDEO_EXTENSIONS:
        return None
    folder = recordings_dir_for_location(location, config).resolve()
    path = (folder / filename).resolve()
    try:
        path.relative_to(folder)
    except ValueError:
        return None
    return path if path.is_file() else None


def _file_contains(path: Path, needles: tuple[bytes, ...], max_bytes: int = 2_000_000) -> bool:
    """
    Check if the file contains the needles.
    
    Args:
        path (Path): The path to the file
        needles (tuple[bytes, ...]): The needles
        max_bytes (int): The maximum number of bytes to read
    
    Returns:
        bool: True if the file contains the needles
    """
    try:
        data = path.read_bytes()[:max_bytes]
    except OSError:
        return False
    # Also check near the end (moov / codec boxes often sit there).
    try:
        size = path.stat().st_size
        if size > max_bytes:
            with path.open('rb') as fh:
                fh.seek(max(0, size - max_bytes))
                data += fh.read()
    except OSError:
        pass
    return any(n in data for n in needles)


def is_browser_playable_video(path: Path) -> bool:
    """
    Check if the video is browser-playable.
    
    Args:
        path (Path): The path to the video
    
    Returns:
        bool: True if the video is browser-playable
    """
    suffix = path.suffix.lower()
    if suffix == '.webm':
        return _file_contains(path, (b'V_VP8', b'V_VP9', b'V_AV1'))
    if suffix in {'.mp4', '.m4v', '.mov'}:
        return _file_contains(path, (b'avc1', b'avcC', b'hvc1', b'hev1', b'vp09'))
    return False


def _lock_for(key: str) -> threading.Lock:
    """
    Get the lock for the key.
    
    Args:
        key (str): The key
    
    Returns:
        threading.Lock: The lock for the key
    """
    with _convert_locks_guard:
        lock = _convert_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _convert_locks[key] = lock
        return lock


def _transcode_to_web(src: Path, dest: Path, max_width: int = 1280) -> Optional[Path]:
    """
    Re-encode ``src`` to a browser-friendly file at ``dest`` (suffix may change).
    
    Args:
        src (Path): The path to the source video
        dest (Path): The path to the destination video
        max_width (int): The maximum width
    
    Returns:
        Optional[Path]: The path to the transcoded video
    """
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        return None

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 25.0
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if src_w <= 0 or src_h <= 0:
        ok, probe = cap.read()
        if not ok or probe is None:
            cap.release()
            return None
        src_h, src_w = probe.shape[:2]
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    if src_w > max_width:
        scale = max_width / float(src_w)
        out_w = max_width
        out_h = max(2, int(round(src_h * scale / 2) * 2))
    else:
        out_w = src_w if src_w % 2 == 0 else src_w - 1
        out_h = src_h if src_h % 2 == 0 else src_h - 1
        out_w = max(2, out_w)
        out_h = max(2, out_h)

    # Prefer MP4/H.264 path; fall back may rewrite suffix to .webm.
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + '.tmp' + dest.suffix)

    writer = None
    out_path = tmp
    for fourcc_name, suffix in _WEB_ENCODE_CANDIDATES:
        candidate = tmp.with_suffix(suffix)
        if candidate.exists():
            try:
                candidate.unlink()
            except OSError:
                pass
        fourcc = cv2.VideoWriter_fourcc(*fourcc_name)
        wr = cv2.VideoWriter(str(candidate), fourcc, fps, (out_w, out_h))
        if wr.isOpened():
            writer = wr
            out_path = candidate
            break
        wr.release()

    if writer is None:
        cap.release()
        return None

    wrote = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if frame.shape[1] != out_w or frame.shape[0] != out_h:
                frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA)
            writer.write(frame)
            wrote += 1
    finally:
        writer.release()
        cap.release()

    if wrote <= 0 or not out_path.is_file() or out_path.stat().st_size < 64:
        try:
            out_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None

    final = dest.with_suffix(out_path.suffix)
    if final.exists():
        try:
            final.unlink()
        except OSError:
            pass
    out_path.replace(final)
    return final if is_browser_playable_video(final) or final.suffix.lower() in {'.mp4', '.webm'} else None


def ensure_web_playable_video(src: Path, location: str) -> Path:
    """
    Return a path suitable for HTML5 ``<video>``.

    Re-encodes OpenCV ``mp4v`` (and similar) into H.264/VP9 once, caching under
    ``storage/saved_recordings_web/<location>/``.
    
    Args:
        src (Path): The path to the source video
        location (str): The location
    
    Returns:
        Path: The path to the browser-playable video
    """
    src = src.resolve()
    if is_browser_playable_video(src):
        return src

    cache_dir = web_cache_dir_for_location(location)
    # Stable cache name from original stem; suffix finalized by encoder.
    preferred = cache_dir / f'{src.stem}.web.mp4'
    # Accept any existing cached sibling with known web suffix.
    for suffix in ('.mp4', '.webm'):
        existing = cache_dir / f'{src.stem}.web{suffix}'
        if existing.is_file() and existing.stat().st_mtime >= src.stat().st_mtime:
            if existing.stat().st_size > 64:
                return existing

    lock = _lock_for(str(src))
    with lock:
        for suffix in ('.mp4', '.webm'):
            existing = cache_dir / f'{src.stem}.web{suffix}'
            if existing.is_file() and existing.stat().st_mtime >= src.stat().st_mtime:
                if existing.stat().st_size > 64:
                    return existing

        _logger.info(f'Converting recording for browser playback: {src.name}')
        result = _transcode_to_web(src, preferred)
        if result is not None:
            return result
        _logger.error(f'Failed to convert recording for browser playback: {src.name}')
        return src


def ensure_video_poster(src: Path, location: str) -> Optional[Path]:
    """
    Extract / cache a JPEG poster frame for a recording.
    
    Args:
        src (Path): The path to the source video
        location (str): The location
    
    Returns:
        Optional[Path]: The path to the poster frame
    """
    src = src.resolve()
    cache_dir = web_cache_dir_for_location(location)
    poster = cache_dir / f'{src.stem}.poster.jpg'
    if poster.is_file() and poster.stat().st_mtime >= src.stat().st_mtime and poster.stat().st_size > 0:
        return poster

    lock = _lock_for(f'poster:{src}')
    with lock:
        if poster.is_file() and poster.stat().st_mtime >= src.stat().st_mtime and poster.stat().st_size > 0:
            return poster
        cap = cv2.VideoCapture(str(src))
        if not cap.isOpened():
            return None
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            return None
        # Slightly downscale large posters for the grid.
        h, w = frame.shape[:2]
        max_w = 640
        if w > max_w:
            scale = max_w / float(w)
            frame = cv2.resize(frame, (max_w, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
        cache_dir.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(poster), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82]):
            return None
        return poster if poster.is_file() else None


def resolve_video_poster(location: str, filename: str, config=None) -> Optional[Path]:
    """
    Resolve the video poster.
    
    Args:
        location (str): The location
        filename (str): The filename
        config (Optional[dict]): The configuration
    
    Returns:
        Optional[Path]: The path to the video poster
    """
    src = resolve_saved_recording(location, filename, config=config)
    if src is None:
        return None
    return ensure_video_poster(src, location)


def warm_web_videos(location: str, config=None, limit: int = 3) -> None:
    """
    Background-friendly helper: pre-convert the newest recordings.
    
    Args:
        location (str): The location
        config (Optional[dict]): The configuration
        limit (int): The limit
    
    Returns:
        None
    """
    for item in list_saved_recordings(location, config=config, limit=limit):
        path = resolve_saved_recording(location, item['name'], config=config)
        if path is None:
            continue
        try:
            ensure_video_poster(path, location)
            ensure_web_playable_video(path, location)
        except Exception as exc:
            _logger.error(f'Warm web video failed for {item["name"]}: {exc}')
