# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 28.07.2026
# Updated: 29.07.2026
# Website: https://bespredel.name


from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path
from typing import Any, Optional

import cv2

from system.datasets.annotation_store import AnnotationStore
from system.datasets.exporters import IMAGE_EXTENSIONS


def yolo_box_to_rect(cx: float, cy: float, w: float, h: float) -> list[float]:
    """
    Convert a YOLO box to a rectangle.
    
    Args:
        cx (float): The center x coordinate
        cy (float): The center y coordinate
        w (float): The width
        h (float): The height
    
    Returns:
        list[float]: The rectangle
    """
    x1 = cx - w / 2.0
    y1 = cy - h / 2.0
    x2 = cx + w / 2.0
    y2 = cy + h / 2.0
    return [x1, y1, x2, y2]


def _canonical_image_name(name: str) -> str:
    """
    Get the canonical image name.
    
    Args:
        name (str): The name of the image
    
    Returns:
        str: The canonical image name
    """
    base = Path(name).name
    stem = Path(base).stem
    suffix = Path(base).suffix.lower() or '.jpg'
    return f'{stem}{suffix}'


def copy_images_into_split(
        sources: list[Path],
        dest_dir: Path,
        existing_names: Optional[set[str]] = None,
) -> tuple[list[str], int]:
    """
    Copy images into dest_dir.

    Skips files whose basename already exists in ``existing_names`` (or dest_dir),
    so re-import does not create ``name_1.jpg`` duplicates.

    Args:
        sources (list[Path]): The sources to copy
        dest_dir (Path): The destination directory
        existing_names (Optional[set[str]]): The existing names to skip
    
    Returns:
        tuple[list[str], int]: The imported basenames and skipped count
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    used = existing_names if existing_names is not None else {
        p.name.lower() for p in dest_dir.iterdir() if p.is_file()
    }
    imported: list[str] = []
    skipped = 0
    for src in sources:
        if not src.is_file() or src.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        name = _canonical_image_name(src.name)
        key = name.lower()
        if key in used:
            skipped += 1
            continue
        shutil.copy2(src, dest_dir / name)
        used.add(key)
        imported.append(name)
    return imported, skipped


def import_from_folder(
        folder: Path,
        dest_dir: Path,
        recursive: bool = False,
        existing_names: Optional[set[str]] = None,
) -> tuple[list[str], int]:
    """
    Import images from a folder.
    
    Args:
        folder (Path): The folder to import from
        dest_dir (Path): The destination directory
        recursive (bool): Whether to import recursively
        existing_names (Optional[set[str]]): The existing names to skip
    
    Returns:
        tuple[list[str], int]: The imported basenames and skipped count
    """
    if not folder.is_dir():
        return [], 0
    pattern = '**/*' if recursive else '*'
    sources = [
        p for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    sources.sort()
    return copy_images_into_split(sources, dest_dir, existing_names=existing_names)


def import_uploaded_files(
        files,
        dest_dir: Path,
        existing_names: Optional[set[str]] = None,
) -> tuple[list[str], int]:
    """
    Import Werkzeug FileStorage list into dest_dir. Skips existing basenames.
    
    Args:
        files (list[FileStorage]): The files to import
        dest_dir (Path): The destination directory
        existing_names (Optional[set[str]]): The existing names to skip
    
    Returns:
        tuple[list[str], int]: The imported basenames and skipped count
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    used = existing_names if existing_names is not None else {
        p.name.lower() for p in dest_dir.iterdir() if p.is_file()
    }
    imported: list[str] = []
    skipped = 0
    for storage in files:
        filename = Path(storage.filename or '').name
        if not filename:
            continue
        suffix = Path(filename).suffix.lower()
        if suffix == '.zip':
            zip_imported, zip_skipped = _import_zip_bytes(storage.read(), dest_dir, used)
            imported.extend(zip_imported)
            skipped += zip_skipped
            continue
        if suffix not in IMAGE_EXTENSIONS:
            continue
        name = _canonical_image_name(filename)
        key = name.lower()
        if key in used:
            skipped += 1
            continue
        storage.save(str(dest_dir / name))
        used.add(key)
        imported.append(name)
    return imported, skipped


def _import_zip_bytes(data: bytes, dest_dir: Path, used: set[str]) -> tuple[list[str], int]:
    """
    Import zip bytes into dest_dir.
    
    Args:
        data (bytes): The data to import
        dest_dir (Path): The destination directory
        used (set[str]): The existing names to skip
    
    Returns:
        tuple[list[str], int]: The imported basenames and skipped count
    """
    imported: list[str] = []
    skipped = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            if Path(name).suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            safe = _canonical_image_name(name)
            key = safe.lower()
            if key in used:
                skipped += 1
                continue
            with zf.open(info) as src, open(dest_dir / safe, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            used.add(key)
            imported.append(safe)
    return imported, skipped


def parse_yolo_label_line(line: str, classes: list[str], task: str = 'detect') -> Optional[dict[str, Any]]:
    """
    Parse a YOLO label line.
    
    Args:
        line (str): The line to parse
        classes (list[str]): The list of classes
        task (str): The task to parse the line for
    
    Returns:
        Optional[dict[str, Any]]: The parsed line
    """
    parts = line.strip().split()
    if len(parts) < 5:
        return None
    try:
        cls_idx = int(float(parts[0]))
    except ValueError:
        return None
    label = classes[cls_idx] if 0 <= cls_idx < len(classes) else str(cls_idx)
    nums = [float(x) for x in parts[1:]]

    if task == 'segment' or (len(nums) > 4 and len(nums) % 2 == 0 and len(nums) >= 6 and task != 'pose'):
        # polygon or detect with many coords treated as poly if > 4
        if len(nums) > 4 and len(nums) % 2 == 0:
            return {
                'id': AnnotationStore.new_shape_id(),
                'type': 'polygon',
                'label': label,
                'points': nums,
                'track_id': None,
                'attributes': {},
            }

    if task == 'pose' and len(nums) >= 4:
        bbox = yolo_box_to_rect(nums[0], nums[1], nums[2], nums[3])
        kpts = nums[4:]
        return {
            'id': AnnotationStore.new_shape_id(),
            'type': 'rectangle',
            'label': label,
            'points': bbox,
            'keypoints': kpts,
            'track_id': None,
            'attributes': {},
        }

    if len(nums) >= 4:
        return {
            'id': AnnotationStore.new_shape_id(),
            'type': 'rectangle',
            'label': label,
            'points': yolo_box_to_rect(nums[0], nums[1], nums[2], nums[3]),
            'track_id': None,
            'attributes': {},
        }
    return None


def import_yolo_labels_to_store(
        dataset_root: Path,
        classes: list[str],
        task: str = 'detect',
        splits: tuple[str, ...] = ('train', 'val', 'inbox'),
) -> int:
    """
    Convert existing YOLO .txt labels into AnnotationStore JSON. Returns converted count.
    
    Args:
        dataset_root (Path): The root of the dataset
        classes (list[str]): The list of classes
        task (str): The task to convert the labels for
        splits (tuple[str, ...]): The splits to convert the labels for
    
    Returns:
        int: The number of labels converted
    """
    store = AnnotationStore(dataset_root)
    converted = 0
    for split in splits:
        images_dir = dataset_root / 'images' / split
        labels_dir = dataset_root / 'labels' / split
        if not images_dir.is_dir():
            continue
        for image_path in images_dir.iterdir():
            if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if store.exists(image_path.name):
                continue
            label_path = labels_dir / f'{image_path.stem}.txt'
            if not label_path.is_file():
                continue
            shapes: list[dict[str, Any]] = []
            with open(label_path, encoding='utf-8') as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    shape = parse_yolo_label_line(line, classes, task)
                    if shape:
                        shapes.append(shape)
            if not shapes:
                continue
            width, height = _probe_image_size(image_path)
            doc = AnnotationStore.empty_doc(image_path.name, width, height)
            doc['shapes'] = shapes
            store.save(image_path.name, doc)
            converted += 1
    return converted


def _probe_image_size(path: Path) -> tuple[int, int]:
    """
    Probe the size of an image.
    
    Args:
        path (Path): The path to the image
    
    Returns:
        tuple[int, int]: The width and height of the image
    """
    if cv2 is None:
        return 0, 0
    try:
        img = cv2.imread(str(path))
        if img is not None:
            h, w = img.shape[:2]
            return int(w), int(h)
    except Exception:
        pass
    return 0, 0


def extract_frames_from_video(
        video_path: Path,
        dest_dir: Path,
        every_n: int = 10,
        max_frames: int = 500,
        prefix: Optional[str] = None,
        existing_names: Optional[set[str]] = None,
) -> tuple[list[str], int]:
    """
    Extract frames from a video into dest_dir. Skips frames that already exist.
    
    Args:
        video_path (Path): The path to the video
        dest_dir (Path): The destination directory
        every_n (int): The number of frames to skip
        max_frames (int): The maximum number of frames to extract
        prefix (Optional[str]): The prefix to add to the frames
        existing_names (Optional[set[str]]): The existing names to skip
    
    Returns:
        tuple[list[str], int]: The imported basenames and skipped count
    """
    if cv2 is None:
        raise ImportError(str(_cv2_import_error or 'cv2 not available'))

    dest_dir.mkdir(parents=True, exist_ok=True)
    used = existing_names if existing_names is not None else {
        p.name.lower() for p in dest_dir.iterdir() if p.is_file()
    }
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return [], 0
    stem = prefix or video_path.stem
    imported: list[str] = []
    skipped = 0
    idx = 0
    saved = 0
    try:
        while saved < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % max(1, every_n) == 0:
                name = _canonical_image_name(f'{stem}_{idx:06d}.jpg')
                key = name.lower()
                if key in used:
                    skipped += 1
                else:
                    cv2.imwrite(str(dest_dir / name), frame)
                    used.add(key)
                    imported.append(name)
                saved += 1
            idx += 1
    finally:
        cap.release()
    return imported, skipped
