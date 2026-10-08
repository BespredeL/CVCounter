# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 28.07.2026
# Updated: 29.07.2026
# Website: https://bespredel.name


from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
import yaml
from system.datasets.annotation_store import AnnotationStore

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')


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
