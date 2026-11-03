# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

""" torchvision training provider: fine-tunes open detection models from COCO JSON. """

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from system.training.base import (
    BaseTrainingProvider,
    TrainingCancelledError,
    TrainingRequest,
    TrainingResult,
)

DEFAULT_BASE_MODEL = 'fasterrcnn_resnet50_fpn_v2.pth'
DEFAULT_LR = 0.005
DEFAULT_SEED = 42
FALLBACK_BATCH = 2

BASE_MODELS: dict[str, dict[str, Any]] = {
    'fasterrcnn_resnet50_fpn_v2.pth': {
        'name': 'Faster R-CNN ResNet-50 FPN v2',
        'task': 'detect',
        'size_mb': 167.1,
        'speed': 'Medium',
        'recommended': True,
        'description': (
            'Открытая детекторная архитектура torchvision (BSD-3): COCO-предобученный '
            'Faster R-CNN без зависимости от Ultralytics и его AGPL-лицензии.'
        ),
        'url': 'https://download.pytorch.org/models/fasterrcnn_resnet50_fpn_v2_coco-dd69338a.pth',
    },
}


def _load_coco_payload(path: Path) -> dict[str, Any]:
    """
    Read one COCO annotation file.

    Args:
        path (Path): Path to instances_<split>.json

    Returns:
        dict[str, Any]: The parsed COCO payload
    """
    with open(path, encoding='utf-8') as fh:
        payload = json.load(fh)
    if not payload.get('images'):
        raise ValueError(f'COCO annotation file has no labeled images: {path}')
    return payload


def collate_coco(batch):
    """
    Collate (image, target) pairs in the torchvision convention.

    Args:
        batch (list): List of (image, target) tuples

    Returns:
        tuple: (list of image tensors, list of target dicts)
    """
    return tuple(zip(*batch))


class CocoDetectionDataset:
    """COCO JSON dataset producing the (image, target) pairs torchvision expects."""

    def __init__(self, annotation_path: Path, max_size: int, training: bool, seed: int = DEFAULT_SEED):
        """
        Args:
            annotation_path (Path): The instances_<split>.json file
            max_size (int): Longest output side in pixels
            training (bool): Apply the training-time transform
            seed (int): Seed for the deterministic flip decision
        """
        from torchvision import transforms

        self.max_size = int(max_size)
        self.training = training
        self.seed = int(seed)
        self.transform = transforms.ToTensor()

        payload = _load_coco_payload(annotation_path)
        self.root = Path(payload.get('root') or str(Path(annotation_path).resolve().parents[2]))

        by_image: dict[int, list[dict[str, Any]]] = {}
        for ann in payload.get('annotations') or []:
            by_image.setdefault(ann['image_id'], []).append(ann)

        self.records = []
        for image in payload['images']:
            path = self.root / image['path']
            if not path.is_file():
                raise FileNotFoundError(f'COCO image listed by {annotation_path.name} is missing: {path}')
            self.records.append((image, path, by_image.get(image['id'], [])))

    def __len__(self) -> int:
        """Number of labeled images in this split."""
        return len(self.records)

    def __getitem__(self, index: int):
        """
        Load one image with its torchvision target.

        Args:
            index (int): Record index

        Returns:
            tuple: (image tensor, target dict)
        """
        import torch
        from PIL import Image
        from torchvision.transforms import functional as F

        image_info, path, annotations = self.records[index]
        with Image.open(path) as handle:
            image = handle.convert('RGB')

        scale = self.max_size / max(image.size)
        new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        image = F.resize(image, new_size)
        flip = self.training and random.Random(f'{self.seed}:{index}').random() < 0.5
        if flip:
            image = F.hflip(image)

        boxes: list[list[float]] = []
        labels: list[int] = []
        for ann in annotations:
            x, y, w, h = ann['bbox']
            x0, x1 = x * scale, (x + w) * scale
            y0, y1 = y * scale, (y + h) * scale
            if flip:
                x0, x1 = new_size[0] - x1, new_size[0] - x0
            boxes.append([x0, y0, x1, y1])
            labels.append(int(ann['category_id']))

        target = {
            'boxes': torch.tensor(boxes, dtype=torch.float32) if boxes
            else torch.zeros((0, 4), dtype=torch.float32),
            'labels': torch.tensor(labels, dtype=torch.int64) if labels
            else torch.zeros((0,), dtype=torch.int64),
            'image_id': torch.tensor([image_info['id']]),
            'width': torch.tensor([new_size[0]]),
            'height': torch.tensor([new_size[1]]),
        }
        if boxes:
            target['area'] = (
                (target['boxes'][:, 2] - target['boxes'][:, 0])
                * (target['boxes'][:, 3] - target['boxes'][:, 1])
            )
            target['iscrowd'] = torch.zeros((len(boxes),), dtype=torch.int64)
        return self.transform(image), target


class TorchVisionTrainingProvider(BaseTrainingProvider):
    """Fine-tune torchvision detection models from a framework-neutral COCO export."""

    id = 'torchvision'
    tasks = ('detect',)
    dataset_formats = ('coco',)

    def prepare(self, request: TrainingRequest) -> None:
        """
        Validate that both COCO splits are exported.

        Args:
            request (TrainingRequest): The job to validate

        Returns:
            None
        """
        super().prepare(request)
        for split in ('train', 'val'):
            path = request.dataset_paths.get(split)
            if not path:
                raise ValueError(
                    f"torchvision training needs the '{split}' COCO JSON; export the dataset "
                    "with format 'coco' first"
                )
            if not Path(path).is_file():
                raise FileNotFoundError(f'COCO annotation file not found: {path}')

    def base_models(self) -> list[dict[str, Any]]:
        """Return the torchvision checkpoints with their install status."""
        models_dir = self.models_dir()
        catalog = []
        for name, info in BASE_MODELS.items():
            local = models_dir / name
            installed = local.is_file()
            catalog.append({
                'name': name,
                'display_name': info['name'],
                'task': info['task'],
                'task_type': info['task'],
                'size_mb': round(local.stat().st_size / (1024 * 1024), 1) if installed else info['size_mb'],
                'speed': info['speed'],
                'recommended': info['recommended'],
                'description': info['description'],
                'installed': installed,
                'path': str(local) if installed else None,
            })
        return catalog

    def curated_models(self) -> dict[str, Any]:
        """Return the downloadable torchvision start checkpoints."""
        return BASE_MODELS

    def download_base_model(self, model_name: str, progress_callback=None) -> Path:
        """
        Download a torchvision checkpoint into the provider model directory.

        Args:
            model_name (str): Checkpoint filename
            progress_callback: Optional callback receiving progress dicts

        Returns:
            Path: The local checkpoint path
        """
        from system.utils.downloads import download_file

        clean_name = Path(model_name).name
        info = BASE_MODELS.get(clean_name)
        if info is None:
            raise ValueError(
                f"Unknown torchvision base model '{clean_name}'. Supported: {', '.join(BASE_MODELS)}"
            )
        return download_file([info['url']], self.models_dir() / clean_name, clean_name, progress_callback)

    def _resolve_base_model(self, request: TrainingRequest, progress) -> tuple[dict[str, Any], Path]:
        import shutil

        clean_name = Path(request.base_model).name
        info = BASE_MODELS.get(clean_name)
        if info is None:
            raise ValueError(
                f"Unknown torchvision base model '{request.base_model}'. "
                f"Supported: {', '.join(BASE_MODELS)}"
            )

        dest = self.models_dir() / clean_name
        if dest.is_file():
            return info, dest

        source = Path(request.base_model)
        if source.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            return info, dest

        if progress is not None:
            progress({
                'event': 'log',
                'message': f"Base checkpoint '{clean_name}' is not local; downloading it...",
            })
        return info, self.download_base_model(clean_name, progress_callback=progress)

    def train(self, request: TrainingRequest) -> TrainingResult:
        """
        Fine-tune a torchvision detection model on a COCO export.

        Args:
            request (TrainingRequest): The job to run

        Returns:
            TrainingResult: Trained checkpoint and per-epoch loss metrics
        """
        import torch
        from torch.utils.data import DataLoader
        from torchvision.models.detection import fasterrcnn_resnet50_fpn_v2
        from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

        self.prepare(request)
        progress = request.progress_callback
        cancel_check = request.cancel_check
        device = torch.device(self.resolve_device(str(request.device)))

        info, checkpoint = self._resolve_base_model(request, progress)
        seed = int(request.options.get('seed', DEFAULT_SEED))
        train_set = CocoDetectionDataset(
            Path(request.dataset_paths['train']), request.img_size, True, seed)
        val_set = CocoDetectionDataset(
            Path(request.dataset_paths['val']), request.img_size, False, seed)

        num_classes = len(request.classes) + 1
        model = fasterrcnn_resnet50_fpn_v2(weights=None, weights_backbone=None)
        state = torch.load(checkpoint, map_location='cpu', weights_only=True)
        for wrapper in ('state_dict', 'model'):
            if isinstance(state, dict) and wrapper in state:
                state = state[wrapper]
        model.load_state_dict(state)
        in_features = model.roi_heads.box_predictor.cls_score.in_features
        model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
        model.to(device)

        batch = request.batch if request.batch and request.batch > 0 else FALLBACK_BATCH
        train_loader = DataLoader(
            train_set, batch_size=batch, shuffle=True, num_workers=0, collate_fn=collate_coco)
        val_loader = DataLoader(
            val_set, batch_size=batch, shuffle=False, num_workers=0, collate_fn=collate_coco)

        optimizer = torch.optim.SGD(
            model.parameters(),
            lr=float(request.options.get('lr', DEFAULT_LR)),
            momentum=0.9,
            weight_decay=0.0005,
            nesterov=True,
        )
        scheduler = torch.optim.lr_scheduler.StepLR(
            optimizer, step_size=max(1, request.epochs // 3), gamma=0.5)

        run_dir = request.run_dir or (self.runs_dir(request.project_root) / request.task / request.run_name)
        weights_dir = run_dir / 'weights'
        weights_dir.mkdir(parents=True, exist_ok=True)
        best_weights = weights_dir / 'best.pt'
        final_weights = weights_dir / 'model_final.pt'

        if progress is not None:
            progress({
                'event': 'start',
                'provider': self.id,
                'config': request.run_name,
                'epochs': request.epochs,
                'imgsz': request.img_size,
                'batch': batch,
                'device': str(device),
                'model': info['name'],
                'images': {'train': len(train_set), 'val': len(val_set)},
            })

        best_loss = float('inf')
        metrics: dict[str, Any] = {}
        for epoch in range(1, request.epochs + 1):
            if cancel_check is not None and cancel_check():
                raise TrainingCancelledError('Training was cancelled by user')

            train_loss = self._run_epoch(model, train_loader, optimizer, device, True, cancel_check)
            with torch.no_grad():
                val_loss = self._run_epoch(model, val_loader, None, device, False, cancel_check)

            scheduler.step()
            payload = {
                'event': 'epoch_end',
                'epoch': epoch,
                'epochs': request.epochs,
                'metrics': {'train_loss': round(train_loss, 6), 'val_loss': round(val_loss, 6)},
            }
            metrics[f'epoch_{epoch}'] = payload['metrics']
            if progress is not None:
                progress(payload)

            if val_loss < best_loss:
                best_loss = val_loss
                torch.save({'model': model.state_dict(), 'classes': list(request.classes)}, best_weights)

        torch.save({'model': model.state_dict(), 'classes': list(request.classes)}, final_weights)
        if not best_weights.is_file():
            best_weights = final_weights

        if progress is not None:
            progress({'event': 'complete', 'weights': str(best_weights), 'provider': self.id})

        return TrainingResult(
            weights=best_weights,
            run_dir=run_dir,
            metrics={'best_val_loss': best_loss, 'model': info['name'], 'epochs': metrics},
        )

    def _run_epoch(self, model, loader, optimizer, device, training: bool, cancel_check) -> float:
        """
        Run one epoch and return its mean total loss.

        Args:
            model: The torchvision detection model
            loader: DataLoader yielding (images, targets)
            optimizer: Optimizer used while training
            device: Torch device
            training (bool): Training mode flag
            cancel_check: Optional callback returning True when cancelling

        Returns:
            float: Mean loss over the epoch
        """
        import torch

        if training:
            model.train()
        else:
            model.eval()

        total = 0.0
        batches = 0
        for images, targets in loader:
            images = [image.to(device) for image in images]
            targets = [{key: value.to(device) for key, value in target.items()} for target in targets]
            loss_dict = model(images, targets)
            loss = torch.stack(list(loss_dict.values())).sum()

            if training:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()

            total += float(loss.item())
            batches += 1
            if cancel_check is not None and cancel_check():
                raise TrainingCancelledError('Training was cancelled by user')
        return total / batches if batches else 0.0
