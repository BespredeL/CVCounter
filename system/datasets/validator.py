# -*- coding: utf-8 -*-
# ! python3

"""
Comprehensive Dataset Validator for CVCounter.
Validates COCO JSON and YOLO TXT datasets for structural integrity, coordinate validity,
annotation anomalies, and data leakage across splits.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import cv2

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class ValidationIssue:
    severity: str  # "error" or "warning"
    category: str
    message: str
    file_path: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    dataset_name: str
    dataset_format: str
    is_valid: bool
    total_images: int = 0
    total_annotations: int = 0
    num_classes: int = 0
    classes: dict[int, str] = field(default_factory=dict)
    splits: dict[str, int] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)
    leakage_detected: bool = False
    leakage_details: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            'dataset_name': self.dataset_name,
            'dataset_format': self.dataset_format,
            'is_valid': self.is_valid,
            'total_images': self.total_images,
            'total_annotations': self.total_annotations,
            'num_classes': self.num_classes,
            'classes': self.classes,
            'splits': self.splits,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'leakage_detected': self.leakage_detected,
            'leakage_details': self.leakage_details,
            'issues': [asdict(i) for i in self.issues],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class DatasetValidator:
    """Validates datasets against computer vision best practices and training standards."""

    def __init__(self, check_images_loadable: bool = True) -> None:
        self.check_images_loadable = check_images_loadable

    def validate(self, dataset_path: str | Path, dataset_format: Optional[str] = None) -> ValidationReport:
        path = Path(dataset_path)
        if not path.exists():
            report = ValidationReport(
                dataset_name=path.name,
                dataset_format="unknown",
                is_valid=False,
            )
            report.issues.append(
                ValidationIssue(severity="error", category="not_found", message=f"Path not found: {path}")
            )
            return report

        fmt = (dataset_format or self._detect_format(path)).lower()
        if fmt == "coco":
            return self._validate_coco(path)
        else:
            return self._validate_yolo(path)

    def _detect_format(self, path: Path) -> str:
        if path.is_file() and path.suffix.lower() == ".json":
            return "coco"
        if (path / "annotations").is_dir():
            return "coco"
        if list(path.glob("*.json")):
            return "coco"
        return "yolo"

    def _validate_yolo(self, path: Path) -> ValidationReport:
        dataset_name = path.name
        issues: list[ValidationIssue] = []
        classes_found: set[int] = set()
        splits_count: dict[str, int] = {}
        total_annotations = 0
        split_image_stems: dict[str, set[str]] = {}

        # Look for standard splits: train, val, test
        splits = ["train", "val", "test"]
        found_splits = False

        for split in splits:
            img_dir = path / "images" / split
            if not img_dir.is_dir():
                img_dir = path / split / "images"
            if not img_dir.is_dir():
                img_dir = path / split
            if not img_dir.is_dir():
                continue

            found_splits = True
            lbl_dir = path / "labels" / split
            if not lbl_dir.is_dir():
                lbl_dir = path / split / "labels"
            if not lbl_dir.is_dir():
                lbl_dir = img_dir

            images = [f for f in img_dir.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
            splits_count[split] = len(images)
            split_image_stems[split] = set()

            for img_path in images:
                stem = img_path.stem
                split_image_stems[split].add(self._extract_sequence_prefix(stem))

                if self.check_images_loadable:
                    img = cv2.imread(str(img_path))
                    if img is None:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                category="corrupted_image",
                                message=f"Cannot decode image: {img_path.name}",
                                file_path=str(img_path),
                            )
                        )
                        continue

                label_file = lbl_dir / f"{stem}.txt"
                if not label_file.is_file():
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="missing_label",
                            message=f"Missing label file for image: {img_path.name}",
                            file_path=str(label_file),
                        )
                    )
                    continue

                # Parse YOLO label
                try:
                    with open(label_file, "r", encoding="utf-8") as f:
                        lines = [l.strip() for l in f if l.strip()]

                    if not lines:
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                category="empty_annotation",
                                message=f"Empty annotation file: {label_file.name}",
                                file_path=str(label_file),
                            )
                        )

                    for line_idx, line in enumerate(lines):
                        parts = line.split()
                        if len(parts) < 5:
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    category="invalid_annotation",
                                    message=f"Invalid format line {line_idx+1} in {label_file.name}: '{line}'",
                                    file_path=str(label_file),
                                )
                            )
                            continue

                        try:
                            cid = int(parts[0])
                            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                        except ValueError:
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    category="invalid_annotation",
                                    message=f"Non-numeric values in line {line_idx+1}: {line}",
                                    file_path=str(label_file),
                                )
                            )
                            continue

                        if cid < 0:
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    category="negative_class_id",
                                    message=f"Negative class ID {cid} in {label_file.name}",
                                    file_path=str(label_file),
                                )
                            )

                        classes_found.add(cid)
                        total_annotations += 1

                        # Validate bounding box boundaries [0, 1]
                        if cx < 0.0 or cx > 1.0 or cy < 0.0 or cy > 1.0 or w <= 0.0 or w > 1.0 or h <= 0.0 or h > 1.0:
                            issues.append(
                                ValidationIssue(
                                    severity="warning",
                                    category="out_of_bounds",
                                    message=f"Box out of [0, 1] bounds ({cx:.3f}, {cy:.3f}, {w:.3f}, {h:.3f}) in {label_file.name}",
                                    file_path=str(label_file),
                                    details={'line': line_idx + 1, 'box': [cx, cy, w, h]},
                                )
                            )

                except Exception as e:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            category="unreadable_label",
                            message=f"Failed to read label {label_file.name}: {e}",
                            file_path=str(label_file),
                        )
                    )

        # Check for sequence / video data leakage across splits
        leakage_detected, leakage_details = self._check_leakage(split_image_stems)

        # Parse classes if data.yaml exists
        classes_map = {cid: f"class_{cid}" for cid in sorted(classes_found)}
        data_yaml = path / "data.yaml"
        if data_yaml.is_file():
            try:
                import yaml
                with open(data_yaml, "r", encoding="utf-8") as yf:
                    yd = yaml.safe_load(yf)
                    if isinstance(yd, dict) and "names" in yd:
                        names = yd["names"]
                        if isinstance(names, dict):
                            classes_map = {int(k): str(v) for k, v in names.items()}
                        elif isinstance(names, list):
                            classes_map = {i: str(n) for i, n in enumerate(names)}
            except Exception:
                pass

        total_imgs = sum(splits_count.values())
        is_valid = sum(1 for i in issues if i.severity == "error") == 0 and total_imgs > 0

        return ValidationReport(
            dataset_name=dataset_name,
            dataset_format="yolo",
            is_valid=is_valid,
            total_images=total_imgs,
            total_annotations=total_annotations,
            num_classes=len(classes_map),
            classes=classes_map,
            splits=splits_count,
            issues=issues,
            leakage_detected=leakage_detected,
            leakage_details=leakage_details,
        )

    def _validate_coco(self, path: Path) -> ValidationReport:
        dataset_name = path.name
        issues: list[ValidationIssue] = []
        total_annotations = 0
        total_images = 0
        splits_count: dict[str, int] = {}
        classes_map: dict[int, str] = {}
        split_image_stems: dict[str, set[str]] = {}

        # Look for json annotation files
        json_files: list[Path] = []
        if path.is_file() and path.suffix == ".json":
            json_files = [path]
        else:
            json_files = list(path.glob("**/*.json"))

        for jf in json_files:
            split_name = jf.stem.replace("instances_", "").replace("annotations_", "")
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="corrupt_json",
                        message=f"Failed to parse JSON file {jf.name}: {e}",
                        file_path=str(jf),
                    )
                )
                continue

            if not isinstance(data, dict):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="invalid_schema",
                        message=f"COCO file must contain a root JSON dictionary: {jf.name}",
                        file_path=str(jf),
                    )
                )
                continue

            images = data.get("images", [])
            annotations = data.get("annotations", [])
            categories = data.get("categories", [])

            for cat in categories:
                cid = cat.get("id")
                cname = cat.get("name", f"class_{cid}")
                if cid is not None:
                    classes_map[int(cid)] = cname

            total_images += len(images)
            total_annotations += len(annotations)
            splits_count[split_name] = len(images)
            split_image_stems[split_name] = set()

            image_ids: set[int] = set()
            for img_info in images:
                iid = img_info.get("id")
                file_name = img_info.get("file_name", "")
                if iid is not None:
                    if iid in image_ids:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                category="duplicate_image_id",
                                message=f"Duplicate image id {iid} in {jf.name}",
                            )
                        )
                    image_ids.add(iid)
                split_image_stems[split_name].add(self._extract_sequence_prefix(Path(file_name).stem))

            # Validate annotations
            anno_ids: set[int] = set()
            for anno in annotations:
                aid = anno.get("id")
                if aid is not None:
                    if aid in anno_ids:
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                category="duplicate_anno_id",
                                message=f"Duplicate annotation id {aid} in {jf.name}",
                            )
                        )
                    anno_ids.add(aid)

                bbox = anno.get("bbox", [])
                if len(bbox) != 4:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            category="invalid_bbox",
                            message=f"Invalid bbox length {len(bbox)} in annotation {aid}",
                        )
                    )
                else:
                    x, y, w, h = bbox
                    if w <= 0 or h <= 0:
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                category="zero_area_bbox",
                                message=f"BBox with non-positive dimensions ({w}, {h}) in annotation {aid}",
                            )
                        )

        leakage_detected, leakage_details = self._check_leakage(split_image_stems)
        is_valid = sum(1 for i in issues if i.severity == "error") == 0 and total_images > 0

        return ValidationReport(
            dataset_name=dataset_name,
            dataset_format="coco",
            is_valid=is_valid,
            total_images=total_images,
            total_annotations=total_annotations,
            num_classes=len(classes_map),
            classes=classes_map,
            splits=splits_count,
            issues=issues,
            leakage_detected=leakage_detected,
            leakage_details=leakage_details,
        )

    def _extract_sequence_prefix(self, stem: str) -> str:
        """
        Extract sequence identifier from filename (e.g. 'cam1_0042' -> 'cam1', 'videoA_frame10' -> 'videoA').
        """
        # Match trailing digits or frame numbers
        match = re.match(r"^(.*?)[_ -]*(?:\d+|frame\d+|seq\d+)$", stem, re.IGNORECASE)
        if match and match.group(1):
            return match.group(1).lower()
        return stem.lower()

    def _check_leakage(self, split_stems: dict[str, set[str]]) -> tuple[bool, list[str]]:
        """Check whether common sequence identifiers cross train and val/test splits."""
        details: list[str] = []
        splits = list(split_stems.keys())
        for i in range(len(splits)):
            for j in range(i + 1, len(splits)):
                s1, s2 = splits[i], splits[j]
                overlap = split_stems[s1].intersection(split_stems[s2])
                if overlap:
                    sample = list(overlap)[:5]
                    details.append(
                        f"Data leakage detected between '{s1}' and '{s2}': {len(overlap)} sequences shared (e.g. {sample})"
                    )

        return len(details) > 0, details
