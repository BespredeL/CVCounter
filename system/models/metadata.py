# -*- coding: utf-8 -*-
# ! python3

"""
Model Metadata representation for CVCounter.
Provides structured storage of model architecture, capabilities, training lineage, and licensing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ModelMetadata:
    model_id: str
    architecture: str
    model_variant: str = ""
    version: str = "1.0.0"
    weights_path: str = ""
    num_classes: int = 0
    class_names: list[str] = field(default_factory=list)
    trained_date: Optional[str] = None
    dataset_name: Optional[str] = None
    training_parameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    supported_backends: list[str] = field(default_factory=lambda: ["pytorch", "onnx"])
    license: str = "Proprietary / Custom"
    author_or_source: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelMetadata:
        clean = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**clean)

    def save(self, filepath: str | Path) -> None:
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, filepath: str | Path) -> ModelMetadata:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
