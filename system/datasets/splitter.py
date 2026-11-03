# -*- coding: utf-8 -*-
# ! python3

"""
Sequence-Aware Dataset Splitter for CVCounter.
Splits images and annotations into train/val/test while keeping video sequences together
to prevent data leakage.
"""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class DatasetSplitter:
    """Splits dataset samples by sequence group to avoid video frame leakage."""

    @staticmethod
    def extract_sequence_id(filename: str) -> str:
        stem = Path(filename).stem
        match = re.match(r"^(.*?)[_ -]*(?:\d+|frame\d+|seq\d+)$", stem, re.IGNORECASE)
        if match and match.group(1):
            return match.group(1).lower()
        return stem.lower()

    @classmethod
    def split_items(
        cls,
        items: list[str],
        train_ratio: float = 0.8,
        val_ratio: float = 0.15,
        test_ratio: float = 0.05,
        seed: int = 42,
    ) -> dict[str, list[str]]:
        """Group filenames by sequence and distribute groups to train/val/test."""
        groups: dict[str, list[str]] = {}
        for item in items:
            seq_id = cls.extract_sequence_id(item)
            groups.setdefault(seq_id, []).append(item)

        seq_keys = list(groups.keys())
        rng = random.Random(seed)
        rng.shuffle(seq_keys)

        total_groups = len(seq_keys)
        n_train = max(1, int(round(total_groups * train_ratio)))
        n_val = int(round(total_groups * val_ratio))

        train_seqs = set(seq_keys[:n_train])
        val_seqs = set(seq_keys[n_train : n_train + n_val])
        test_seqs = set(seq_keys[n_train + n_val :])

        splits: dict[str, list[str]] = {"train": [], "val": [], "test": []}
        for seq_id, file_list in groups.items():
            if seq_id in train_seqs:
                splits["train"].extend(file_list)
            elif seq_id in val_seqs:
                splits["val"].extend(file_list)
            else:
                splits["test"].extend(file_list)

        return splits
