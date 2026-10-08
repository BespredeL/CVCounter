# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 28.07.2026
# Updated: 29.07.2026
# Website: https://bespredel.name


from __future__ import annotations
import json
import random
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import yaml
import cv2
from system.datasets.annotation_store import AnnotationStore
from system.datasets.exporters import (
    IMAGE_EXTENSIONS,
    export_split_labels,
    write_data_yaml,
)
from system.datasets.importers import (
    extract_frames_from_video,
    import_from_folder,
    import_uploaded_files,
    import_yolo_labels_to_store,
)
from system.training.yolo_trainer import CFG_DIR, setup_directories
from system.utils.paths import ensure_dir, get_project_root, resolve_project_path
from system.utils.utils import slug

VALID_TASKS = ('detect', 'segment', 'classify', 'pose')
SPLITS = ('train', 'val', 'inbox')


def _normalize_split(split: str | None) -> str:
    """
    Normalize a split name.
    
    Args:
        split (str | None): The split name to normalize
    
    Returns:
        str: The normalized split name
    """
    value = (split or 'inbox').strip()
    if value not in SPLITS:
        raise ValueError(f'Invalid split: {value}')
    return value


class DatasetService:
    """Manage YOLO-oriented datasets under ``storage/datasets``."""

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root or get_project_root())
        self.datasets_dir = Path(resolve_project_path('storage/datasets', str(self.project_root)))
        ensure_dir(str(self.datasets_dir))

    def _meta_path(self, name: str) -> Path:
        """
        Get the path for the meta file.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            Path: The path for the meta file
        """
        return self.root(name) / 'meta.json'

    def root(self, name: str) -> Path:
        """
        Get the root path for a dataset.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            Path: The root path for the dataset
        """
        safe = self._safe_name(name)
        return self.datasets_dir / safe

    @staticmethod
    def _safe_name(name: str) -> str:
        """
        Safely clean a dataset name.
        
        Args:
            name (str): The name to clean
        
        Returns:
            str: The cleaned name
        """
        cleaned = slug(name) if name else ''
        cleaned = re.sub(r'[^a-zA-Z0-9_\-]+', '-', cleaned).strip('-_')
        if not cleaned:
            raise ValueError('Invalid dataset name')
        return cleaned

    def store(self, name: str) -> AnnotationStore:
        """
        Get the annotation store for a dataset.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            AnnotationStore: The annotation store for the dataset
        """
        return AnnotationStore(self.root(name))

    def load_meta(self, name: str) -> dict[str, Any]:
        """
        Load the meta data for a dataset.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            dict[str, Any]: The meta data for the dataset
        """
        path = self._meta_path(name)
        if not path.is_file():
            # Bootstrap meta for legacy YOLO folders
            root = self.root(name)
            if not root.is_dir():
                raise FileNotFoundError(f'Dataset not found: {name}')
            classes = self._guess_classes_from_yaml(name)
            meta = {
                'name': self._safe_name(name),
                'display_name': name,
                'task': 'detect',
                'classes': classes or ['object'],
                'attributes': [],
                'keypoints_schema': [],
                'autolabel_detector': '',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            self.save_meta(name, meta)
            return meta
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)

    def save_meta(self, name: str, meta: dict[str, Any]) -> None:
        """
        Save the meta data for a dataset.
        
        Args:
            name (str): The name of the dataset
            meta (dict[str, Any]): The meta data to save
        """
        root = self.root(name)
        root.mkdir(parents=True, exist_ok=True)
        meta = dict(meta)
        meta['name'] = self._safe_name(name)
        meta['updated_at'] = datetime.now(timezone.utc).isoformat()
        with open(self._meta_path(name), 'w', encoding='utf-8') as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)

    def _guess_classes_from_yaml(self, name: str) -> list[str]:
        """
        Guess the classes from a YAML file.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            list[str]: The classes from the YAML file
        """
        setup_directories(self.project_root)
        yaml_path = CFG_DIR / f'{self._safe_name(name)}.yaml'
        if not yaml_path.is_file():
            return []
        if yaml is None:
            return []
        try:
            with open(yaml_path, encoding='utf-8') as fh:
                data = yaml.safe_load(fh) or {}
            names = data.get('names') or {}
            if isinstance(names, dict):
                return [names[k] for k in sorted(names, key=lambda x: int(x))]
            if isinstance(names, list):
                return list(names)
        except Exception:
            return []
        return []

    def ensure_layout(self, name: str) -> Path:
        """
        Ensure the layout for a dataset.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            Path: The root path for the dataset
        """
        root = self.root(name)
        for split in SPLITS:
            (root / 'images' / split).mkdir(parents=True, exist_ok=True)
            (root / 'labels' / split).mkdir(parents=True, exist_ok=True)
        (root / 'annotations').mkdir(parents=True, exist_ok=True)
        (root / '.thumbs').mkdir(parents=True, exist_ok=True)
        return root

    def list_datasets(self) -> list[dict[str, Any]]:
        """
        List all datasets.
        
        Returns:
            list[dict[str, Any]]: The list of datasets
        """
        items = []
        if not self.datasets_dir.is_dir():
            return items
        for path in sorted(self.datasets_dir.iterdir()):
            if not path.is_dir() or path.name.startswith('.'):
                continue
            try:
                summary = self.get_summary(path.name)
                items.append(summary)
            except Exception:
                items.append({
                    'name': path.name,
                    'display_name': path.name,
                    'error': 'unreadable',
                })
        return items

    def create(
            self,
            name: str,
            classes: Optional[list[str]] = None,
            task: str = 'detect',
            attributes: Optional[list[dict]] = None,
            display_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a new dataset.
        
        Args:
            name (str): The name of the dataset
            classes (Optional[list[str]]): The classes for the dataset
            task (str): The task for the dataset
            attributes (Optional[list[dict]]): The attributes for the dataset
            display_name (Optional[str]): The display name for the dataset
        
        Returns:
            dict[str, Any]: The summary of the dataset
        """
        safe = self._safe_name(name)
        root = self.root(safe)
        if root.exists() and any(root.iterdir()):
            # Allow create if only empty dirs / missing meta
            if self._meta_path(safe).is_file():
                raise FileExistsError(f'Dataset already exists: {safe}')
        if task not in VALID_TASKS:
            raise ValueError(f'Unsupported task: {task}')
        self.ensure_layout(safe)
        meta = {
            'name': safe,
            'display_name': display_name or name,
            'task': task,
            'classes': classes or ['object'],
            'attributes': attributes or [],
            'keypoints_schema': [],
            'autolabel_detector': '',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        self.save_meta(safe, meta)
        return self.get_summary(safe)

    def delete(self, name: str) -> None:
        """
        Delete a dataset.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            None
        """
        root = self.root(name)
        if root.is_dir():
            shutil.rmtree(root)

    def update_meta(self, name: str, **fields) -> dict[str, Any]:
        """
        Update the meta data for a dataset.
        
        Args:
            name (str): The name of the dataset
            **fields: The fields to update
        
        Returns:
            dict[str, Any]: The updated meta data
        """
        meta = self.load_meta(name)
        if 'classes' in fields and fields['classes'] is not None:
            meta['classes'] = [str(c).strip() for c in fields['classes'] if str(c).strip()]
        if 'task' in fields and fields['task']:
            if fields['task'] not in VALID_TASKS:
                raise ValueError(f'Unsupported task: {fields["task"]}')
            meta['task'] = fields['task']
        if 'display_name' in fields and fields['display_name']:
            meta['display_name'] = fields['display_name']
        if 'attributes' in fields and fields['attributes'] is not None:
            meta['attributes'] = fields['attributes']
        if 'keypoints_schema' in fields and fields['keypoints_schema'] is not None:
            meta['keypoints_schema'] = fields['keypoints_schema']
        if 'autolabel_detector' in fields:
            value = fields['autolabel_detector']
            meta['autolabel_detector'] = str(value).strip() if value else ''
        self.save_meta(name, meta)
        return meta

    def list_images(
            self,
            name: str,
            split: Optional[str] = None,
            labeled: Optional[bool] = None,
            class_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        List the images in a dataset.
        
        Args:
            name (str): The name of the dataset
            split (Optional[str]): The split to list
            labeled (Optional[bool]): Whether to list labeled images
            class_filter (Optional[str]): The class filter
        
        Returns:
            list[dict[str, Any]]: The list of images
        """
        meta = self.load_meta(name)
        store = self.store(name)
        root = self.root(name)
        splits = [split] if split else list(SPLITS)
        result = []
        for sp in splits:
            images_dir = root / 'images' / sp
            if not images_dir.is_dir():
                continue
            for path in sorted(images_dir.iterdir()):
                if path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                is_lab = store.is_labeled(path.name, meta.get('task', 'detect'))
                if labeled is True and not is_lab:
                    continue
                if labeled is False and is_lab:
                    continue
                doc = store.load(path.name) if store.exists(path.name) else None
                labels = []
                if doc:
                    labels = sorted({s.get('label') for s in doc.get('shapes') or [] if s.get('label')})
                    if doc.get('image_label'):
                        labels.append(doc['image_label'])
                if class_filter and class_filter not in labels:
                    continue
                result.append({
                    'name': path.name,
                    'split': sp,
                    'labeled': is_lab,
                    'labels': labels,
                    'mtime': path.stat().st_mtime,
                })
        return result

    def get_summary(self, name: str) -> dict[str, Any]:
        """
        Get the summary of a dataset.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            dict[str, Any]: The summary of the dataset
        """
        meta = self.load_meta(name)
        images = self.list_images(name)
        total = len(images)
        labeled = sum(1 for i in images if i['labeled'])
        by_split = {s: 0 for s in SPLITS}
        per_class: dict[str, int] = {c: 0 for c in meta.get('classes') or []}
        store = self.store(name)
        for item in images:
            by_split[item['split']] = by_split.get(item['split'], 0) + 1
            if not item['labeled']:
                continue
            doc = store.load(item['name'])
            for shape in doc.get('shapes') or []:
                label = shape.get('label')
                if label is not None:
                    per_class[label] = per_class.get(label, 0) + 1
            if doc.get('image_label'):
                lab = doc['image_label']
                per_class[lab] = per_class.get(lab, 0) + 1
        return {
            'name': meta.get('name', name),
            'display_name': meta.get('display_name', name),
            'task': meta.get('task', 'detect'),
            'classes': meta.get('classes', []),
            'attributes': meta.get('attributes', []),
            'keypoints_schema': meta.get('keypoints_schema', []),
            'autolabel_detector': meta.get('autolabel_detector') or '',
            'total': total,
            'labeled': labeled,
            'unlabeled': total - labeled,
            'labeled_pct': round(100.0 * labeled / total, 1) if total else 0.0,
            'by_split': by_split,
            'per_class': per_class,
            'inbox_path': str((self.root(name) / 'images' / 'inbox').resolve()),
            'created_at': meta.get('created_at'),
            'updated_at': meta.get('updated_at'),
        }

    def image_path(self, name: str, image_name: str, split: Optional[str] = None) -> Path:
        """
        Get the path for an image.
        
        Args:
            name (str): The name of the dataset
            image_name (str): The name of the image
            split (Optional[str]): The split to get the path for
        
        Returns:
            Path: The path for the image
        """
        root = self.root(name)
        if split:
            path = root / 'images' / split / image_name
            if path.is_file():
                return path
        for sp in SPLITS:
            path = root / 'images' / sp / image_name
            if path.is_file():
                return path
        raise FileNotFoundError(f'Image not found: {image_name}')

    def find_image_split(self, name: str, image_name: str) -> str:
        """
        Find the split for an image.
        
        Args:
            name (str): The name of the dataset
            image_name (str): The name of the image
        
        Returns:
            str: The split for the image
        """
        root = self.root(name)
        for sp in SPLITS:
            if (root / 'images' / sp / image_name).is_file():
                return sp
        raise FileNotFoundError(f'Image not found: {image_name}')

    def delete_images(self, name: str, image_names: list[str]) -> int:
        """
        Delete images from a dataset.
        
        Args:
            name (str): The name of the dataset
            image_names (list[str]): The names of the images to delete
        
        Returns:
            int: The number of images deleted
        """
        store = self.store(name)
        removed = 0
        for image_name in image_names:
            try:
                split = self.find_image_split(name, image_name)
            except FileNotFoundError:
                continue
            path = self.root(name) / 'images' / split / image_name
            if path.is_file():
                path.unlink()
                removed += 1
            store.delete(image_name)
            label = self.root(name) / 'labels' / split / f'{Path(image_name).stem}.txt'
            if label.is_file():
                label.unlink()
        return removed

    def move_images(self, name: str, image_names: list[str], target_split: str) -> int:
        """
        Move images from one split to another.
        
        Args:
            name (str): The name of the dataset
            image_names (list[str]): The names of the images to move
            target_split (str): The target split
        
        Returns:
            int: The number of images moved
        """
        if target_split not in SPLITS:
            raise ValueError(f'Invalid split: {target_split}')
        moved = 0
        root = self.root(name)
        dest_dir = root / 'images' / target_split
        dest_dir.mkdir(parents=True, exist_ok=True)
        for image_name in image_names:
            try:
                src_split = self.find_image_split(name, image_name)
            except FileNotFoundError:
                continue
            if src_split == target_split:
                continue
            src = root / 'images' / src_split / image_name
            dest = dest_dir / image_name
            shutil.move(str(src), str(dest))
            # move label if present
            src_label = root / 'labels' / src_split / f'{Path(image_name).stem}.txt'
            if src_label.is_file():
                dest_label_dir = root / 'labels' / target_split
                dest_label_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_label), str(dest_label_dir / src_label.name))
            moved += 1
        return moved

    def _image_basenames(self, name: str) -> set[str]:
        """
        Lowercase basenames of all images across train/val/inbox.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            set[str]: The lowercase basenames of all images
        """
        names: set[str] = set()
        root = self.root(name)
        for split in SPLITS:
            folder = root / 'images' / split
            if not folder.is_dir():
                continue
            for path in folder.iterdir():
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                    names.add(path.name.lower())
        return names

    def import_saved_images(
            self,
            name: str,
            location: Optional[str] = None,
            split: str = 'inbox',
    ) -> dict[str, Any]:
        """
        Import saved images into a dataset.
        
        Args:
            name (str): The name of the dataset
            location (Optional[str]): The location of the images
            split (str): The split to import the images into
        
        Returns:
            dict[str, Any]: The import results
        """
        self.ensure_layout(name)
        split = _normalize_split(split)
        saved_root = Path(resolve_project_path('storage/saved_images', str(self.project_root)))
        if not saved_root.is_dir():
            raise FileNotFoundError('Saved images folder not found')

        if location:
            folder = saved_root / location
            if not folder.is_dir():
                raise FileNotFoundError(f'No saved images for location: {location}')
            folders = [folder]
        else:
            folders = [p for p in saved_root.iterdir() if p.is_dir()]
            # Also allow images placed directly under saved_images/
            root_images = [
                p for p in saved_root.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
            ]
            if root_images and not folders:
                folders = [saved_root]

        dest = self.root(name) / 'images' / split
        existing = self._image_basenames(name)
        imported: list[str] = []
        skipped = 0
        for folder in folders:
            # Recursive for camera subfolders; flat for files directly under saved_images.
            recursive = folder != saved_root
            batch, skip = import_from_folder(
                folder, dest, recursive=recursive, existing_names=existing,
            )
            imported.extend(batch)
            skipped += skip
        if location is None and any(folder != saved_root for folder in folders):
            batch, skip = import_from_folder(
                saved_root, dest, recursive=False, existing_names=existing,
            )
            imported.extend(batch)
            skipped += skip
        return {
            'imported': len(imported),
            'skipped': skipped,
            'images': imported,
            'split': split,
        }

    def import_uploads(self, name: str, files, split: str = 'inbox') -> dict[str, Any]:
        """
        Import uploaded files into a dataset.
        
        Args:
            name (str): The name of the dataset
            files: The uploaded files
            split (str): The split to import the files into
        
        Returns:
            dict[str, Any]: The import results
        """
        self.ensure_layout(name)
        split = _normalize_split(split)
        dest = self.root(name) / 'images' / split
        existing = self._image_basenames(name)
        imported, skipped = import_uploaded_files(files, dest, existing_names=existing)
        return {
            'imported': len(imported),
            'skipped': skipped,
            'images': imported,
            'split': split,
        }

    def adopt_existing(self, name: str) -> dict[str, Any]:
        """
        Ensure layout/meta and convert YOLO labels → JSON for an on-disk dataset.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            dict[str, Any]: The adoption results
        """
        self.ensure_layout(name)
        meta = self.load_meta(name)
        converted = import_yolo_labels_to_store(
            self.root(name),
            meta.get('classes') or [],
            meta.get('task', 'detect'),
        )
        return {'converted': converted, 'summary': self.get_summary(name)}

    def list_saved_image_locations(self) -> list[dict[str, Any]]:
        """
        List the saved image locations.
        
        Returns:
            list[dict[str, Any]]: The list of saved image locations
        """
        saved_root = Path(resolve_project_path('storage/saved_images', str(self.project_root)))
        if not saved_root.is_dir():
            return []
        result = []
        for path in sorted(saved_root.iterdir()):
            if not path.is_dir():
                continue
            count = sum(1 for p in path.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
            result.append({'location': path.name, 'count': count, 'path': str(path)})
        return result

    def list_recordings(self) -> list[dict[str, Any]]:
        """
        List the recordings.
        
        Returns:
            list[dict[str, Any]]: The list of recordings
        """
        rec_root = Path(resolve_project_path('storage/saved_recordings', str(self.project_root)))
        if not rec_root.is_dir():
            return []
        exts = {'.mp4', '.avi', '.mkv', '.mov', '.webm'}
        result = []
        for path in sorted(rec_root.rglob('*')):
            if path.is_file() and path.suffix.lower() in exts:
                result.append({
                    'name': path.name,
                    'path': str(path.relative_to(self.project_root)).replace('\\', '/'),
                    'size': path.stat().st_size,
                })
        return result

    def import_recording_frames(
            self,
            name: str,
            relative_path: str,
            every_n: int = 10,
            max_frames: int = 500,
            split: str = 'inbox',
    ) -> dict[str, Any]:
        """
        Import frames from a recording into a dataset.
        
        Args:
            name (str): The name of the dataset
            relative_path (str): The relative path to the recording
            every_n (int): The number of frames to skip
            max_frames (int): The maximum number of frames to import
            split (str): The split to import the frames into
        
        Returns:
            dict[str, Any]: The import results
        """
        self.ensure_layout(name)
        split = _normalize_split(split)
        video = Path(resolve_project_path(relative_path, str(self.project_root)))
        if not video.is_file():
            raise FileNotFoundError(f'Recording not found: {relative_path}')
        existing = self._image_basenames(name)
        imported, skipped = extract_frames_from_video(
            video,
            self.root(name) / 'images' / split,
            every_n=every_n,
            max_frames=max_frames,
            existing_names=existing,
        )
        return {
            'imported': len(imported),
            'skipped': skipped,
            'images': imported,
            'split': split,
        }

    def auto_split(self, name: str, val_ratio: float = 0.2, seed: int = 42) -> dict[str, Any]:
        """
        Move inbox+train images into train/val by ratio (labeled preferred for val).
        
        Args:
            name (str): The name of the dataset
            val_ratio (float): The ratio of validation images
            seed (int): The random seed
        
        Returns:
            dict[str, Any]: The split results
        """
        if not 0.0 < val_ratio < 1.0:
            raise ValueError('val_ratio must be between 0 and 1')
        items = self.list_images(name)
        # pool from inbox and train
        pool = [i for i in items if i['split'] in ('inbox', 'train')]
        rng = random.Random(seed)
        rng.shuffle(pool)
        val_count = max(1, int(round(len(pool) * val_ratio))) if pool else 0
        val_names = [i['name'] for i in pool[:val_count]]
        train_names = [i['name'] for i in pool[val_count:]]
        # also keep existing val
        moved_val = self.move_images(name, val_names, 'val')
        moved_train = self.move_images(name, train_names, 'train')
        return {
            'val': moved_val,
            'train': moved_train,
            'val_ratio': val_ratio,
        }

    def export_for_training(self, name: str) -> dict[str, Any]:
        """
        Write YOLO labels + data.yaml under config/ultralytics/cfg.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            dict[str, Any]: The export results
        """
        setup_directories(self.project_root)
        meta = self.load_meta(name)
        classes = meta.get('classes') or []
        task = meta.get('task', 'detect')
        root = self.root(name)
        for item in self.list_images(name, split='inbox', labeled=True):
            self.move_images(name, [item['name']], 'train')

        written_train = export_split_labels(root, 'train', classes, task, self.store(name))
        written_val = export_split_labels(root, 'val', classes, task, self.store(name))

        val_images = list((root / 'images' / 'val').glob('*'))
        val_images = [p for p in val_images if p.suffix.lower() in IMAGE_EXTENSIONS]
        if not val_images:
            train_images = [p for p in (root / 'images' / 'train').iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS]
            if train_images:
                sample = train_images[0]
                dest = root / 'images' / 'val' / sample.name
                if not dest.exists():
                    shutil.copy2(sample, dest)
                label_src = root / 'labels' / 'train' / f'{sample.stem}.txt'
                if label_src.is_file():
                    dest_l = root / 'labels' / 'val' / label_src.name
                    dest_l.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(label_src, dest_l)

        cfg_path = CFG_DIR / f'{self._safe_name(name)}.yaml'
        write_data_yaml(root, classes, cfg_path, task)
        return {
            'yaml': str(cfg_path),
            'train_labels': written_train,
            'val_labels': written_val,
            'task': task,
            'classes': classes,
        }

    def get_annotation(self, name: str, image_name: str) -> dict[str, Any]:
        """
        Get the annotation for an image.
        
        Args:
            name (str): The name of the dataset
            image_name (str): The name of the image
        
        Returns:
            dict[str, Any]: The annotation for the image
        """
        store = self.store(name)
        doc = store.load(image_name)
        try:
            split = self.find_image_split(name, image_name)
            path = self.image_path(name, image_name, split)
            if (not doc.get('width') or not doc.get('height')) and cv2 is not None:
                try:
                    img = cv2.imread(str(path))
                    if img is not None:
                        h, w = img.shape[:2]
                        doc['width'] = int(w)
                        doc['height'] = int(h)
                except Exception:
                    pass
            doc['split'] = split
        except FileNotFoundError:
            doc['split'] = None
        return doc

    def save_annotation(self, name: str, image_name: str, doc: dict[str, Any]) -> dict[str, Any]:
        """
        Save the annotation for an image.
        
        Args:
            name (str): The name of the dataset
            image_name (str): The name of the image
            doc (dict[str, Any]): The annotation to save
        
        Returns:
            dict[str, Any]: The save results
        """
        store = self.store(name)
        self.image_path(name, image_name)
        path = store.save(image_name, doc)
        return {'ok': True, 'path': str(path)}

    def copy_shapes_from_previous(self, name: str, image_name: str) -> dict[str, Any]:
        """
        Copy shapes from the previous image to the current image.
        
        Args:
            name (str): The name of the dataset
            image_name (str): The name of the image
        
        Returns:
            dict[str, Any]: The copy results
        """
        images = self.list_images(name)
        names = [i['name'] for i in images]
        if image_name not in names:
            raise FileNotFoundError(image_name)
        idx = names.index(image_name)
        if idx == 0:
            return self.get_annotation(name, image_name)
        prev = names[idx - 1]
        prev_doc = self.store(name).load(prev)
        doc = self.get_annotation(name, image_name)
        shapes = []
        for shape in prev_doc.get('shapes') or []:
            clone = dict(shape)
            clone['id'] = AnnotationStore.new_shape_id()
            shapes.append(clone)
        doc['shapes'] = shapes
        self.save_annotation(name, image_name, doc)
        return doc

    def interpolate_track(
            self,
            name: str,
            track_id: int,
            start_image: str,
            end_image: str,
    ) -> int:
        """
        Linearly interpolate rectangle tracks between two keyframes. Returns frames filled.
        
        Args:
            name (str): The name of the dataset
            track_id (int): The track ID
            start_image (str): The start image
            end_image (str): The end image
        
        Returns:
            int: The number of frames filled
        """
        images = self.list_images(name)
        names = [i['name'] for i in images]
        if start_image not in names or end_image not in names:
            raise ValueError('Start/end images not in dataset')
        i0, i1 = names.index(start_image), names.index(end_image)
        if i0 > i1:
            i0, i1 = i1, i0
            start_image, end_image = end_image, start_image
        if i1 - i0 < 2:
            return 0

        store = self.store(name)
        start_doc = store.load(start_image)
        end_doc = store.load(end_image)

        def _find_rect(doc):
            for s in doc.get('shapes') or []:
                if s.get('track_id') == track_id and s.get('type') == 'rectangle' and len(s.get('points') or []) >= 4:
                    return s
            return None

        a = _find_rect(start_doc)
        b = _find_rect(end_doc)
        if not a or not b:
            raise ValueError('Track rectangles not found on both keyframes')

        filled = 0
        steps = i1 - i0
        for step in range(1, steps):
            t = step / steps
            mid_name = names[i0 + step]
            points = [
                a['points'][i] + (b['points'][i] - a['points'][i]) * t
                for i in range(4)
            ]
            doc = store.load(mid_name)
            shapes = [s for s in (doc.get('shapes') or []) if s.get('track_id') != track_id]
            shapes.append({
                'id': AnnotationStore.new_shape_id(),
                'type': 'rectangle',
                'label': a.get('label'),
                'points': points,
                'track_id': track_id,
                'attributes': dict(a.get('attributes') or {}),
                'interpolated': True,
            })
            doc['shapes'] = shapes
            if not doc.get('width'):
                doc['width'] = start_doc.get('width', 0)
                doc['height'] = start_doc.get('height', 0)
            store.save(mid_name, doc)
            filled += 1
        return filled

    def qa_report(self, name: str) -> dict[str, Any]:
        """
        Get the QA report for a dataset.
        
        Args:
            name (str): The name of the dataset
        
        Returns:
            dict[str, Any]: The QA report
        """
        meta = self.load_meta(name)
        store = self.store(name)
        unlabeled = []
        out_of_bounds = []
        per_class = {c: 0 for c in meta.get('classes') or []}
        for item in self.list_images(name):
            if not item['labeled']:
                unlabeled.append(item['name'])
                continue
            doc = store.load(item['name'])
            for shape in doc.get('shapes') or []:
                label = shape.get('label')
                if label in per_class:
                    per_class[label] += 1
                else:
                    per_class[label] = per_class.get(label, 0) + 1
                pts = shape.get('points') or []
                if any(p < -0.01 or p > 1.01 for p in pts):
                    out_of_bounds.append({'image': item['name'], 'shape_id': shape.get('id')})
        counts = list(per_class.values()) or [0]
        imbalance = max(counts) / max(1, min(c for c in counts if c > 0) if any(counts) else 1)
        return {
            'unlabeled': unlabeled,
            'unlabeled_count': len(unlabeled),
            'out_of_bounds': out_of_bounds,
            'per_class': per_class,
            'imbalance_ratio': round(float(imbalance), 2) if any(counts) else 0,
            'imbalance_warning': imbalance >= 10 and sum(1 for c in counts if c > 0) > 1,
        }

    def reassign_class(self, name: str, from_label: str, to_label: str) -> int:
        """
        Reassign a class to a new class.
        
        Args:
            name (str): The name of the dataset
            from_label (str): The class to reassign
            to_label (str): The new class
        
        Returns:
            int: The number of images reclassified
        """
        meta = self.load_meta(name)
        store = self.store(name)
        changed = 0
        for item in self.list_images(name, labeled=True):
            doc = store.load(item['name'])
            dirty = False
            for shape in doc.get('shapes') or []:
                if shape.get('label') == from_label:
                    shape['label'] = to_label
                    dirty = True
            if doc.get('image_label') == from_label:
                doc['image_label'] = to_label
                dirty = True
            if dirty:
                store.save(item['name'], doc)
                changed += 1
        classes = meta.get('classes') or []
        if to_label not in classes:
            classes.append(to_label)
        if from_label in classes and from_label != to_label:
            # keep old class unless unused — leave for user; just ensure to_label exists
            pass
        meta['classes'] = classes
        self.save_meta(name, meta)
        return changed

    def merge_into(self, target: str, source: str, split: str = 'inbox') -> dict[str, Any]:
        """
        Copy images (+ annotations) from source dataset into target.
        
        Args:
            target (str): The name of the target dataset
            source (str): The name of the source dataset
            split (str): The split to merge into
        
        Returns:
            dict[str, Any]: The merge results
        """
        self.ensure_layout(target)
        src_root = self.root(source)
        if not src_root.is_dir():
            raise FileNotFoundError(source)
        split = _normalize_split(split)
        dest = self.root(target) / 'images' / split
        existing = self._image_basenames(target)
        imported: list[str] = []
        skipped = 0
        for src_split in ('train', 'val', 'inbox'):
            batch, skip = import_from_folder(
                src_root / 'images' / src_split,
                dest,
                recursive=False,
                existing_names=existing,
            )
            imported.extend(batch)
            skipped += skip
        # copy annotations by stem if present
        src_store = AnnotationStore(src_root)
        dst_store = self.store(target)
        for ann in src_store.list_annotation_files():
            doc = src_store.load(ann.stem)
            # rename image field if needed — best effort match by stem among imported
            matching = [n for n in imported if Path(n).stem == ann.stem or n == doc.get('image')]
            if matching:
                dst_store.save(matching[0], doc)
        # merge classes
        t_meta = self.load_meta(target)
        s_meta = self.load_meta(source)
        classes = list(t_meta.get('classes') or [])
        for c in s_meta.get('classes') or []:
            if c not in classes:
                classes.append(c)
        t_meta['classes'] = classes
        self.save_meta(target, t_meta)
        return {'imported': len(imported), 'skipped': skipped, 'images': imported}

    def uncertainty_rank(
            self,
            name: str,
            predictions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Rank unlabeled images by prediction uncertainty.

        predictions: [{image, max_conf, num_boxes}, ...]
        Lower max_conf / empty detections = higher priority.
        
        Args:
            name (str): The name of the dataset
            predictions (list[dict[str, Any]]): The predictions
        
        Returns:
            list[dict[str, Any]]: The ranked images
        """
        unlabeled = {i['name'] for i in self.list_images(name, labeled=False)}
        ranked = []
        for pred in predictions:
            img = pred.get('image')
            if img not in unlabeled:
                continue
            max_conf = float(pred.get('max_conf', 0.0) or 0.0)
            num_boxes = int(pred.get('num_boxes', 0) or 0)
            score = (1.0 - max_conf) if num_boxes else 1.5
            ranked.append({
                'image': img,
                'score': round(score, 4),
                'max_conf': max_conf,
                'num_boxes': num_boxes,
            })
        ranked.sort(key=lambda x: x['score'], reverse=True)
        return ranked
