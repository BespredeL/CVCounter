# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name


from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import cv2
import yaml
from system.datasets.annotation_store import AnnotationStore

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')

DATASET_FORMAT_ALIASES = {
    'yolo': 'yolo',
    'yolo_txt': 'yolo',
    'yolotxt': 'yolo',
    'txt': 'yolo',
    'coco': 'coco',
    'coco_json': 'coco',
    'json': 'coco',
    'both': 'both',
    'all': 'both',
}


def normalize_dataset_format(dataset_format: Optional[str]) -> str:
    """
    Resolve a dataset export format alias.

    Args:
        dataset_format (Optional[str]): Requested format, e.g. 'coco' or 'coco_json'

    Returns:
        str: One of 'yolo', 'coco', 'both'
    """
    key = str(dataset_format or 'yolo').strip().lower().replace('-', '_')
    if key not in DATASET_FORMAT_ALIASES:
        supported = ', '.join(sorted(DATASET_FORMAT_ALIASES))
        raise ValueError(f"Unsupported dataset format: '{dataset_format}'. Supported: {supported}")
    return DATASET_FORMAT_ALIASES[key]


def _class_index(classes: list[str], label: str) -> Optional[int]:
    """
    Get the index of a class.
    
    Args:
        classes (list[str]): The list of classes
        label (str): The label to get the index of
    
    Returns:
        Optional[int]: The index of the class
    """
    if label in classes:
        return classes.index(label)
    try:
        idx = int(label)
        if 0 <= idx < len(classes):
            return idx
    except (TypeError, ValueError):
        pass
    return None


def rectangle_to_yolo(points: list[float]) -> tuple[float, float, float, float]:
    """
    Normalize a rectangle to cx,cy,w,h.
    
    Args:
        points (list[float]): The points of the rectangle
    
    Returns:
        tuple[float, float, float, float]: The normalized rectangle
    """
    x1, y1, x2, y2 = points[:4]
    x_min, x_max = sorted((float(x1), float(x2)))
    y_min, y_max = sorted((float(y1), float(y2)))
    w = max(0.0, x_max - x_min)
    h = max(0.0, y_max - y_min)
    cx = x_min + w / 2.0
    cy = y_min + h / 2.0
    return cx, cy, w, h


def shape_to_yolo_line(shape: dict[str, Any], classes: list[str], task: str) -> Optional[str]:
    """
    Convert a shape to a YOLO line.
    
    Args:
        shape (dict[str, Any]): The shape to convert
        classes (list[str]): The list of classes
        task (str): The task to convert the shape for
    
    Returns:
        Optional[str]: The YOLO line
    """
    label = shape.get('label', '')
    cls_idx = _class_index(classes, str(label))
    if cls_idx is None:
        return None
    stype = shape.get('type', 'rectangle')
    points = [float(p) for p in shape.get('points') or []]

    if task == 'segment' and stype == 'polygon' and len(points) >= 6:
        coords = ' '.join(f'{p:.6f}' for p in points)
        return f'{cls_idx} {coords}'

    if stype == 'rectangle' and len(points) >= 4:
        cx, cy, w, h = rectangle_to_yolo(points)
        if task == 'segment':
            # rectangle as 4-point polygon
            x1, y1 = cx - w / 2, cy - h / 2
            x2, y2 = cx + w / 2, cy + h / 2
            poly = [x1, y1, x2, y1, x2, y2, x1, y2]
            coords = ' '.join(f'{p:.6f}' for p in poly)
            return f'{cls_idx} {coords}'
        return f'{cls_idx} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}'

    if stype == 'polygon' and len(points) >= 6 and task == 'detect':
        xs = points[0::2]
        ys = points[1::2]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        cx = (x_min + x_max) / 2.0
        cy = (y_min + y_max) / 2.0
        w = x_max - x_min
        h = y_max - y_min
        return f'{cls_idx} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}'

    return None


def keypoints_to_yolo_line(entry: dict[str, Any], classes: list[str]) -> Optional[str]:
    """
    Convert a keypoints entry to a YOLO line.
    
    Args:
        entry (dict[str, Any]): The keypoints entry to convert
        classes (list[str]): The list of classes
    
    Returns:
        Optional[str]: The YOLO line
    """
    label = entry.get('label', '')
    cls_idx = _class_index(classes, str(label))
    if cls_idx is None:
        return None
    bbox = entry.get('bbox') or []
    kpts = entry.get('points') or []
    if len(bbox) < 4:
        return None
    cx, cy, w, h = rectangle_to_yolo(bbox)
    parts = [str(cls_idx), f'{cx:.6f}', f'{cy:.6f}', f'{w:.6f}', f'{h:.6f}']
    for i in range(0, len(kpts), 3):
        if i + 2 >= len(kpts):
            break
        parts.extend([f'{float(kpts[i]):.6f}', f'{float(kpts[i + 1]):.6f}', str(int(kpts[i + 2]))])
    return ' '.join(parts)


def write_yolo_label(label_path: Path, doc: dict[str, Any], classes: list[str], task: str) -> int:
    """
    Write a YOLO label file.
    
    Args:
        label_path (Path): The path to the label file
        doc (dict[str, Any]): The document to write the label for
        classes (list[str]): The list of classes
        task (str): The task to write the label for
    
    Returns:
        int: The number of lines written
    """
    lines: list[str] = []
    if task == 'classify':
        # YOLO classify uses folder layout; labels txt not used the same way.
        return 0
    if task == 'pose':
        for entry in doc.get('keypoints') or []:
            line = keypoints_to_yolo_line(entry, classes)
            if line:
                lines.append(line)
        # Also allow shapes with keypoints embedded
        for shape in doc.get('shapes') or []:
            if shape.get('keypoints'):
                line = keypoints_to_yolo_line({
                    'label': shape.get('label'),
                    'bbox': shape.get('points'),
                    'points': shape.get('keypoints'),
                }, classes)
                if line:
                    lines.append(line)
    else:
        for shape in doc.get('shapes') or []:
            line = shape_to_yolo_line(shape, classes, task)
            if line:
                lines.append(line)

    label_path.parent.mkdir(parents=True, exist_ok=True)
    with open(label_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
        if lines:
            fh.write('\n')
    return len(lines)


def export_split_labels(
        dataset_root: Path,
        split: str,
        classes: list[str],
        task: str,
        store: Optional[AnnotationStore] = None,
) -> int:
    """
    Write YOLO labels for all images in a split that have annotations.
    
    Args:
        dataset_root (Path): The root of the dataset
        split (str): The split to write the labels for
        classes (list[str]): The list of classes
        task (str): The task to write the labels for
        store (Optional[AnnotationStore]): The annotation store to use
    
    Returns:
        int: The number of labels written
    """
    store = store or AnnotationStore(dataset_root)
    images_dir = dataset_root / 'images' / split
    labels_dir = dataset_root / 'labels' / split
    labels_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    if not images_dir.is_dir():
        return 0
    for image_path in sorted(images_dir.iterdir()):
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if not store.exists(image_path.name) and not store.exists(image_path.stem):
            # Keep existing YOLO txt if no JSON yet
            continue
        doc = store.load(image_path.name)
        count = write_yolo_label(labels_dir / f'{image_path.stem}.txt', doc, classes, task)
        if count:
            written += 1
    return written


def write_data_yaml(
        dataset_root: Path,
        classes: list[str],
        cfg_path: Path,
        task: str = 'detect',
) -> Path:
    """
    Write Ultralytics data.yaml pointing at the dataset root.
    
    Args:
        dataset_root (Path): The root of the dataset
        classes (list[str]): The list of classes
        cfg_path (Path): The path to the data.yaml file
        task (str): The task to write the data.yaml for
    
    Returns:
        Path: The path to the data.yaml file
    """
    names = {i: name for i, name in enumerate(classes)}
    payload: dict[str, Any] = {
        'path': str(dataset_root.resolve()).replace('\\', '/'),
        'train': 'images/train',
        'val': 'images/val',
        'names': names,
    }
    if task == 'segment':
        payload['task'] = 'segment'
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, 'w', encoding='utf-8') as fh:
        yaml.safe_dump(payload, fh, allow_unicode=True, sort_keys=False)
    return cfg_path


COCO_EXPORT_TASKS = ('detect', 'segment')


def _clip_pixel(value: float, limit: float) -> float:
    """
    Clamp a coordinate to the image bounds.

    Args:
        value (float): The coordinate in pixels
        limit (float): The image size along that axis

    Returns:
        float: The clamped coordinate
    """
    return min(max(float(value), 0.0), float(limit))


def _polygon_area(xs: list[float], ys: list[float]) -> float:
    """
    Return the shoelace area of a closed polygon.

    Args:
        xs (list[float]): The polygon x coordinates
        ys (list[float]): The polygon y coordinates

    Returns:
        float: The area in pixels
    """
    total = 0.0
    for i in range(len(xs) - 1):
        total += xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
    return abs(total) / 2.0


def shape_to_coco_entry(
        shape: dict[str, Any],
        classes: list[str],
        task: str,
        width: int,
        height: int,
) -> Optional[dict[str, Any]]:
    """
    Convert one normalized annotation shape to a COCO annotation fragment.

    Args:
        shape (dict[str, Any]): The shape to convert
        classes (list[str]): The list of classes
        task (str): The task to convert the shape for
        width (int): The image width in pixels
        height (int): The image height in pixels

    Returns:
        Optional[dict[str, Any]]: The COCO annotation fragment without id/image_id, or None
    """
    cls_idx = _class_index(classes, str(shape.get('label', '')))
    if cls_idx is None:
        return None
    points = [float(p) for p in shape.get('points') or []]
    stype = shape.get('type', 'rectangle')

    xs: list[float] = []
    ys: list[float] = []
    segmentation: list[list[float]] = []
    if stype == 'rectangle' and len(points) >= 4:
        x0 = _clip_pixel(min(points[0], points[2]) * width, width)
        x1 = _clip_pixel(max(points[0], points[2]) * width, width)
        y0 = _clip_pixel(min(points[1], points[3]) * height, height)
        y1 = _clip_pixel(max(points[1], points[3]) * height, height)
        if task == 'segment':
            segmentation = [[x0, y0, x1, y0, x1, y1, x0, y1]]
    elif stype == 'polygon' and len(points) >= 6:
        xs = [_clip_pixel(p * width, width) for p in points[0::2]]
        ys = [_clip_pixel(p * height, height) for p in points[1::2]]
        if task == 'segment':
            segmentation = [[v for pair in zip(xs, ys) for v in pair]]
    else:
        return None

    if xs:
        left, right = min(xs), max(xs)
        top, bottom = min(ys), max(ys)
    else:
        left, right = x0, x1
        top, bottom = y0, y1

    box_w = max(0.0, right - left)
    box_h = max(0.0, bottom - top)
    if box_w <= 0.0 or box_h <= 0.0:
        return None

    if segmentation:
        flat = segmentation[0]
        area = _polygon_area(flat[0::2], flat[1::2])
    else:
        area = box_w * box_h

    return {
        'category_id': cls_idx + 1,
        'bbox': [round(left, 3), round(top, 3), round(box_w, 3), round(box_h, 3)],
        'area': round(area, 3),
        'segmentation': segmentation,
        'iscrowd': 0,
    }


def image_dimensions(doc: dict[str, Any], image_path: Path) -> tuple[int, int]:
    """
    Read the pixel size of an image, preferring the annotation document.

    Args:
        doc (dict[str, Any]): The annotation document
        image_path (Path): The path to the image

    Returns:
        tuple[int, int]: The width and height in pixels
    """
    width = int(doc.get('width') or 0)
    height = int(doc.get('height') or 0)
    if width > 0 and height > 0:
        return width, height
    frame = cv2.imread(str(image_path))
    if frame is None:
        raise ValueError(f'Cannot read image dimensions for {image_path.name}')
    return int(frame.shape[1]), int(frame.shape[0])


def export_coco_dataset(
        dataset_root: Path,
        classes: list[str],
        task: str = 'detect',
        splits: tuple[str, ...] = ('train', 'val'),
        store: Optional[AnnotationStore] = None,
) -> dict[str, Any]:
    """
    Write framework-neutral COCO JSON files for every split of a dataset.

    Args:
        dataset_root (Path): The root of the dataset
        classes (list[str]): The list of classes
        task (str): The task to export
        splits (tuple[str, ...]): The splits to export
        store (Optional[AnnotationStore]): The annotation store to use

    Returns:
        dict[str, Any]: The export results with per-split JSON paths and counters
    """
    if task not in COCO_EXPORT_TASKS:
        raise ValueError(
            f"COCO export supports {', '.join(COCO_EXPORT_TASKS)} tasks; task '{task}' "
            'has no COCO representation in this project'
        )
    store = store or AnnotationStore(dataset_root)
    annotations_dir = dataset_root / 'coco' / 'annotations'
    annotations_dir.mkdir(parents=True, exist_ok=True)

    categories = [
        {'id': index + 1, 'name': name, 'supercategory': 'none'}
        for index, name in enumerate(classes)
    ]
    paths: dict[str, str] = {}
    image_counts: dict[str, int] = {}
    annotation_counts: dict[str, int] = {}
    annotation_id = 1

    for split in splits:
        images_dir = dataset_root / 'images' / split
        images: list[dict[str, Any]] = []
        annotations: list[dict[str, Any]] = []
        if images_dir.is_dir():
            for image_id, image_path in enumerate(
                    sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS),
                    start=1,
            ):
                if not store.exists(image_path.name) and not store.exists(image_path.stem):
                    continue
                doc = store.load(image_path.name)
                width, height = image_dimensions(doc, image_path)
                images.append({
                    'id': image_id,
                    'file_name': image_path.name,
                    'width': width,
                    'height': height,
                    'path': f'images/{split}/{image_path.name}',
                })
                for shape in doc.get('shapes') or []:
                    entry = shape_to_coco_entry(shape, classes, task, width, height)
                    if entry is None:
                        continue
                    entry['id'] = annotation_id
                    entry['image_id'] = image_id
                    annotation_id += 1
                    annotations.append(entry)

        payload = {
            'info': {
                'description': f'{dataset_root.name} ({split})',
                'version': '1.0',
                'date_created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            },
            'licenses': [],
            'categories': categories,
            'images': images,
            'annotations': annotations,
            'task': task,
            'split': split,
            'root': str(dataset_root.resolve()).replace('\\', '/'),
        }
        out_path = annotations_dir / f'instances_{split}.json'
        with open(out_path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        paths[split] = str(out_path)
        image_counts[split] = len(images)
        annotation_counts[split] = len(annotations)

    return {
        'annotations': paths,
        'images': image_counts,
        'instances': annotation_counts,
        'categories': len(categories),
        'root': str(dataset_root.resolve()),
        'task': task,
    }
