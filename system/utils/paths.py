# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import os
from pathlib import Path
from typing import Optional

_PROJECT_ROOT: Optional[str] = None


def project_root_from_config_path(config_path: str) -> str:
    """
    Return project root for config stored at `<root>/config/config.json`.

    Args:
        config_path (str): The path to the config file.

    Returns:
        str: The project root.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(config_path)))


def set_project_root(project_root: str) -> None:
    """
    Set the project root.

    Args:
        project_root (str): The project root.

    Returns:
        None
    """
    global _PROJECT_ROOT
    _PROJECT_ROOT = os.path.abspath(project_root)


def get_project_root() -> str:
    """
    Get the project root.

    Args:
        None

    Returns:
        str: The project root.
    """
    if _PROJECT_ROOT:
        return _PROJECT_ROOT

    try:
        from system.managers.config_manager import config
        if config is not None and hasattr(config, 'project_root'):
            return config.project_root
    except (ImportError, AttributeError):
        pass

    return os.getcwd()


def resolve_training_paths(project_root: Optional[Path | str] = None) -> tuple[Path, Path, Path, Path]:
    """Resolve legacy-compatible training paths without importing a trainer."""
    root = Path(project_root) if project_root else Path(get_project_root())
    ultralytics_root = root / 'config' / 'ultralytics'
    legacy_root = root / 'config'

    def resolve_dir(name: str) -> Path:
        modern = ultralytics_root / name
        legacy = legacy_root / name
        return modern if modern.is_dir() or not legacy.is_dir() else legacy

    return (
        resolve_dir('cfg'),
        resolve_dir('models'),
        resolve_dir('runs'),
        root / 'storage' / 'datasets',
    )


def resolve_provider_training_paths(
        provider_id: str,
        project_root: Optional[Path | str] = None,
) -> tuple[Path, Path, Path]:
    """
    Resolve cfg/models/runs directories owned by one training provider.

    Ultralytics keeps the historic layout (config/ultralytics with a legacy
    config/ fallback); every other provider gets its own config/<provider> tree.

    Args:
        provider_id (str): Canonical training provider id.
        project_root (Optional[Path | str]): Project root override.

    Returns:
        tuple[Path, Path, Path]: cfg, models and runs directories.
    """
    root = Path(project_root) if project_root else Path(get_project_root())
    normalized = (provider_id or 'ultralytics').strip().lower()
    if normalized == 'ultralytics':
        cfg, models, runs, _ = resolve_training_paths(root)
        return cfg, models, runs
    provider_root = root / 'config' / normalized
    return provider_root / 'cfg', provider_root / 'models', provider_root / 'runs'


def resolve_project_path(relative_path: Optional[str], project_root: Optional[str] = None) -> Optional[str]:
    """
    Resolve a project path.

    Args:
        relative_path (str): The relative path to resolve.
        project_root (str, optional): The project root.

    Returns:
        str: The resolved path.
    """
    if not relative_path:
        return relative_path
    if os.path.isabs(relative_path):
        return os.path.normpath(relative_path)
    root = project_root or get_project_root()
    return os.path.normpath(os.path.join(root, relative_path))


def ensure_dir(path: Optional[str]) -> None:
    """
    Ensure a directory exists.

    Args:
        path (str): The path to ensure.

    Returns:
        None
    """
    if not path:
        return
    os.makedirs(path, exist_ok=True)


def ensure_parent_dir(path: Optional[str]) -> None:
    """
    Ensure a parent directory exists.

    Args:
        path (str): The path to ensure.

    Returns:
        None
    """
    if not path:
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def resolve_sqlite_uri(uri: str, project_root: Optional[str] = None) -> str:
    """
    Resolve a SQLite URI.

    Args:
        uri (str): The URI to resolve.
        project_root (str, optional): The project root.

    Returns:
        str: The resolved URI.
    """
    if not uri.startswith('sqlite:///'):
        return uri

    db_path = uri.replace('sqlite:///', '', 1)
    if not db_path or db_path == ':memory:':
        return uri

    resolved = resolve_project_path(db_path, project_root)
    ensure_parent_dir(resolved)
    return 'sqlite:///' + resolved.replace('\\', '/')


def ensure_storage_layout(project_root: Optional[str] = None) -> None:
    """
    Ensure the storage layout exists.

    Args:
        project_root (str, optional): The project root.

    Returns:
        None
    """
    root = project_root or get_project_root()
    for relative_dir in (
            'storage/logs',
            'storage/saved_recordings',
            'storage/saved_images',
            'storage/counter_previews',
            'storage/datasets',
    ):
        ensure_dir(resolve_project_path(relative_dir, root))
