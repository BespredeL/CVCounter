# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Keep Ultralytics settings inside this project.

Ultralytics reads YOLO_CONFIG_DIR once, at import, and otherwise stores
settings.json under the user profile (on Windows: %APPDATA%\\Ultralytics).
Importing this module points that directory at config/ultralytics before any
Ultralytics import. The library still adds its own Ultralytics subdirectory.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ULTRALYTICS_ROOT = PROJECT_ROOT / 'config' / 'ultralytics'


def _profile_settings_file() -> Path:
    """Default settings file Ultralytics would use when YOLO_CONFIG_DIR is unset."""
    if sys.platform == 'win32':
        base = Path.home() / 'AppData' / 'Roaming' / 'Ultralytics'
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support' / 'Ultralytics'
    else:
        base = Path(os.getenv('XDG_CONFIG_HOME', Path.home() / '.config')) / 'Ultralytics'
    return base / 'settings.json'


def ensure_ultralytics_config_dir() -> Path:
    """Point YOLO_CONFIG_DIR at the project and return the settings directory."""
    os.environ.setdefault('YOLO_CONFIG_DIR', str(ULTRALYTICS_ROOT))
    settings_dir = Path(os.environ['YOLO_CONFIG_DIR']).expanduser() / 'Ultralytics'
    settings_dir.mkdir(parents=True, exist_ok=True)

    destination = settings_dir / 'settings.json'
    source = _profile_settings_file()
    if not destination.exists() and source.is_file() and source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    return settings_dir


def pin_ultralytics_directories() -> None:
    """Store datasets, weights and training runs next to the rest of the project data."""
    ensure_ultralytics_config_dir()
    from ultralytics import settings

    from system.utils.paths import resolve_training_paths

    _cfg, models, runs, datasets = resolve_training_paths(PROJECT_ROOT)
    for path in (models, runs, datasets):
        path.mkdir(parents=True, exist_ok=True)
    desired = {
        'datasets_dir': str(datasets.resolve()),
        'weights_dir': str(models.resolve()),
        'runs_dir': str(runs.resolve()),
    }
    current = {key: str(Path(settings.get(key, '')).resolve()) for key in desired}
    if current != desired:
        settings.update(desired)


def prepare_ultralytics() -> None:
    """Set the project settings directory, then align its directory entries."""
    ensure_ultralytics_config_dir()
    pin_ultralytics_directories()


ensure_ultralytics_config_dir()
