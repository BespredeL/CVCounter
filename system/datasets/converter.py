# -*- coding: utf-8 -*-
# ! python3

"""
Lossless Two-Way Dataset Converter for CVCounter.
Converts between YOLO TXT and COCO JSON formats without altering source files.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class DatasetConverter:
    """Provides non-destructive conversion between COCO and YOLO formats."""

    @staticmethod
    def yolo_to_coco(
        yolo_root: str | Path,
        output_dir: str | Path,
        classes: Optional[list[str] | dict[int, str]] = None,
        copy_images: bool = False,
    ) -> Path:
        """
        Convert a YOLO formatted dataset to COCO format under output_dir/coco/.
        Source dataset is never modified.
        """
        src = Path(yolo_root)
        dst = Path(output_dir)
        dst.mkdir(parents=True, exist_ok=True)

        # Resolve classes map
        classes_map: dict[int, str] = {}
        if isinstance(classes, dict):
            classes_map = {int(k): str(v) for k, v in classes.items()}
        elif isinstance(classes, list):
            classes_map = {i: str(n) for i, n in enumerate(classes)}
        else:
            # Check data.yaml
            yaml_path = src / "data.yaml"
            if yaml_path.is_file():
                try:
                    import yaml
                    with open(yaml_path, "r", encoding="utf-8") as yf:
                        yd = yaml.safe_load(yf)
                        if isinstance(yd, dict) and "names" in yd:
                            names = yd["names"]
                            if isinstance(names, dict):
                                classes_map = {int(k): str(v) for k, v in names.items()}
                            elif isinstance(names, list):
                                classes_map = {i: str(n) for i, n in enumerate(names)}
                except Exception:
                    pass

        anno_dir = dst / "annotations"
        anno_dir.mkdir(parents=True, exist_ok=True)

        splits = ["train", "val", "test"]
        for split in splits:
            img_dir = src / "images" / split
            if not img_dir.is_dir():
                img_dir = src / split / "images"
            if not img_dir.is_dir():
                img_dir = src / split
            if not img_dir.is_dir():
                continue

            lbl_dir = src / "labels" / split
            if not lbl_dir.is_dir():
                lbl_dir = src / split / "labels"
            if not lbl_dir.is_dir():
                lbl_dir = img_dir

            images_list = [f for f in img_dir.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
            if not images_list:
                continue

            coco_images = []
            coco_annotations = []
            anno_id = 1

            for img_idx, img_path in enumerate(sorted(images_list), start=1):
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                h, w = img.shape[:2]

                coco_images.append({
                    "id": img_idx,
                    "file_name": img_path.name,
                    "width": w,
                    "height": h,
                })

                label_file = lbl_dir / f"{img_path.stem}.txt"
                if label_file.is_file():
                    with open(label_file, "r", encoding="utf-8") as lf:
                        for line in lf:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                cid = int(parts[0])
                                cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])

                                # Convert YOLO cx,cy,w,h in [0,1] to COCO x,y,w,h in pixels
                                abs_w = bw * w
                                abs_h = bh * h
                                abs_x = (cx * w) - (abs_w / 2.0)
                                abs_y = (cy * h) - (abs_h / 2.0)

                                coco_annotations.append({
                                    "id": anno_id,
                                    "image_id": img_idx,
                                    "category_id": cid,
                                    "bbox": [round(abs_x, 2), round(abs_y, 2), round(abs_w, 2), round(abs_h, 2)],
                                    "area": round(abs_w * abs_h, 2),
                                    "iscrowd": 0,
                                })
                                anno_id += 1

                if copy_images:
                    split_dst_img = dst / "images" / split
                    split_dst_img.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(img_path, split_dst_img / img_path.name)

            # Build categories list
            categories = [
                {"id": cid, "name": cname}
                for cid, cname in sorted(classes_map.items())
            ]

            coco_data = {
                "info": {"description": f"Converted from YOLO: {src.name}"},
                "images": coco_images,
                "annotations": coco_annotations,
                "categories": categories,
            }

            out_json = anno_dir / f"instances_{split}.json"
            with open(out_json, "w", encoding="utf-8") as jf:
                json.dump(coco_data, jf, indent=2, ensure_ascii=False)

        return dst

    @staticmethod
    def coco_to_yolo(
        coco_json_path: str | Path,
        images_dir: str | Path,
        output_dir: str | Path,
        split: str = "train",
        copy_images: bool = False,
    ) -> Path:
        """
        Convert a COCO annotation file and image folder to YOLO format directory.
        Original files are never modified.
        """
        cjson = Path(coco_json_path)
        img_src = Path(images_dir)
        dst = Path(output_dir)

        with open(cjson, "r", encoding="utf-8") as f:
            data = json.load(f)

        img_dst = dst / "images" / split
        lbl_dst = dst / "labels" / split
        img_dst.mkdir(parents=True, exist_ok=True)
        lbl_dst.mkdir(parents=True, exist_ok=True)

        images = {img["id"]: img for img in data.get("images", [])}
        annotations_by_img: dict[int, list[dict]] = {}
        for anno in data.get("annotations", []):
            annotations_by_img.setdefault(anno["image_id"], []).append(anno)

        for img_id, img_info in images.items():
            fn = img_info.get("file_name", "")
            src_file = img_src / fn
            w = float(img_info.get("width", 1))
            h = float(img_info.get("height", 1))

            if copy_images and src_file.is_file():
                shutil.copy2(src_file, img_dst / fn)

            lbl_file = lbl_dst / f"{Path(fn).stem}.txt"
            annos = annotations_by_img.get(img_id, [])

            lines = []
            for a in annos:
                cid = int(a.get("category_id", 0))
                bbox = a.get("bbox", [])
                if len(bbox) == 4 and w > 0 and h > 0:
                    bx, by, bw, bh = bbox
                    cx = (bx + bw / 2.0) / w
                    cy = (by + bh / 2.0) / h
                    nw = bw / w
                    nh = bh / h
                    lines.append(f"{cid} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

            with open(lbl_file, "w", encoding="utf-8") as lf:
                lf.write("\n".join(lines) + ("\n" if lines else ""))

        # Write data.yaml if categories are available
        cats = {c["id"]: c.get("name", f"class_{c['id']}") for c in data.get("categories", [])}
        if cats:
            yaml_path = dst / "data.yaml"
            import yaml
            payload = {
                "path": str(dst.resolve()).replace("\\", "/"),
                "train": "images/train",
                "val": "images/val",
                "names": {i: cats[i] for i in sorted(cats.keys())},
            }
            with open(yaml_path, "w", encoding="utf-8") as yf:
                yaml.dump(payload, yf, sort_keys=False)

        return dst

