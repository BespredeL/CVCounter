# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations
import copy
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional


class AnnotationStore:
    """Read/write annotation JSON files under ``<dataset>/annotations/``."""

    def __init__(self, dataset_root: Path):
        self.root = Path(dataset_root)
        self.ann_dir = self.root / 'annotations'
        self.ann_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple[int, int, dict[str, Any]]] = {}

    @staticmethod
    def empty_doc(image_name: str, width: int = 0, height: int = 0) -> dict[str, Any]:
        """
        Create an empty annotation document.
        
        Args:
            image_name (str): The name of the image
            width (int): The width of the image
            height (int): The height of the image
        
        Returns:
            dict[str, Any]: The empty annotation document
        """
        return {
            'image': image_name,
            'width': int(width or 0),
            'height': int(height or 0),
            'image_label': None,
            'shapes': [],
            'keypoints': [],
        }

    @staticmethod
    def new_shape_id() -> str:
        """
        Generate a new shape ID.
        
        Returns:
            str: The new shape ID
        """
        return f's{uuid.uuid4().hex[:10]}'

    def path_for(self, image_name: str) -> Path:
        """
        Get the path for an annotation file.
        
        Args:
            image_name (str): The name of the image
        
        Returns:
            Path: The path for the annotation file
        """
        stem = Path(image_name).stem
        return self.ann_dir / f'{stem}.json'

    def exists(self, image_name: str) -> bool:
        """
        Check if an annotation file exists.
        
        Args:
            image_name (str): The name of the image
        
        Returns:
            bool: True if the annotation file exists
        """
        return self.path_for(image_name).is_file()

    def load(self, image_name: str) -> dict[str, Any]:
        """
        Load an annotation document.
        
        Args:
            image_name (str): The name of the image
        
        Returns:
            dict[str, Any]: The annotation document
        """
        path = self.path_for(image_name)
        if not path.is_file():
            return self.empty_doc(image_name)
        stat = path.stat()
        cached = self._cache.get(image_name)
        if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
            return copy.deepcopy(cached[2])
        try:
            with path.open(encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read annotation '{path}': {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Annotation '{path}' must contain a JSON object")
        data.setdefault('image', image_name)
        data.setdefault('width', 0)
        data.setdefault('height', 0)
        data.setdefault('image_label', None)
        data.setdefault('shapes', [])
        data.setdefault('keypoints', [])
        self._cache[image_name] = (stat.st_mtime_ns, stat.st_size, copy.deepcopy(data))
        return data

    def save(self, image_name: str, doc: dict[str, Any]) -> Path:
        """
        Save an annotation document.
        
        Args:
            image_name (str): The name of the image
            doc (dict[str, Any]): The annotation document
        
        Returns:
            Path: The path for the saved annotation file
        """
        path = self.path_for(image_name)
        if not isinstance(doc, dict):
            raise TypeError('Annotation document must be a dictionary')
        payload = copy.deepcopy(doc)
        payload['image'] = image_name
        payload.setdefault('shapes', [])
        payload.setdefault('keypoints', [])
        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=self.ann_dir,
                prefix=f'.{path.stem}.',
                suffix='.tmp',
                delete=False,
            ) as fh:
                temp_path = Path(fh.name)
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
        stat = path.stat()
        self._cache[image_name] = (stat.st_mtime_ns, stat.st_size, copy.deepcopy(payload))
        return path

    def delete(self, image_name: str) -> bool:
        """
        Delete an annotation file.
        
        Args:
            image_name (str): The name of the image
        
        Returns:
            bool: True if the annotation file was deleted
        """
        self._cache.pop(image_name, None)
        path = self.path_for(image_name)
        if path.is_file():
            path.unlink()
            return True
        return False

    def is_labeled(self, image_name: str, task: str = 'detect') -> bool:
        """
        Check if an image is labeled.
        
        Args:
            image_name (str): The name of the image
            task (str): The task to check
        
        Returns:
            bool: True if the image is labeled
        """
        if not self.exists(image_name):
            return False
        doc = self.load(image_name)
        if task == 'classify':
            return bool(doc.get('image_label'))
        if task == 'pose':
            return bool(doc.get('keypoints')) or bool(doc.get('shapes'))
        return bool(doc.get('shapes'))

    def list_annotation_files(self) -> list[Path]:
        """
        List all annotation files.
        
        Returns:
            list[Path]: The list of annotation files
        """
        if not self.ann_dir.is_dir():
            return []
        return sorted(self.ann_dir.glob('*.json'))
