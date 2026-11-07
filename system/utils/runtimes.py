# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from system.utils.hardware import (
    compute_cap_to_sm,
    detect_hardware_profile,
    resolve_pytorch_builds,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PYTORCH_DISTRIBUTIONS: Tuple[str, ...] = ('torch', 'torchvision')

# Bundles are the only installable units the web UI may trigger: every key maps to a closed
# set of pip arguments, so no request can supply an arbitrary package name or command.
PACKAGE_BUNDLES: Dict[str, Dict[str, Any]] = {
    'pytorch': {
        'name': 'PyTorch',
        'description': 'Core deep-learning runtime. Installs the CUDA build matching your NVIDIA '
                       'GPU, or a lightweight CPU build when no GPU is present.',
        'build': 'pytorch',
        'requires_gpu': False,
        'license': 'BSD-3-Clause',
        'provides': ['torch', 'torchvision'],
    },
    'onnxruntime': {
        'name': 'ONNX Runtime (CPU)',
        'description': 'MIT-licensed ONNX inference on CPU - run exported .onnx models without '
                       'installing AGPL-licensed Ultralytics.',
        'requires_gpu': False,
        'license': 'MIT',
        'requirements_file': 'requirements-onnxruntime.txt',
        'provides': ['onnxruntime'],
    },
    'onnx_runtime_gpu': {
        'name': 'ONNX Runtime (CUDA GPU)',
        'description': 'High-performance ONNX Runtime with NVIDIA CUDA acceleration.',
        'requires_gpu': True,
        'license': 'MIT',
        'packages': ['onnxruntime-gpu>=1.18.0'],
        'provides': ['onnxruntime-gpu'],
    },
    'onnx_runtime_directml': {
        'name': 'ONNX Runtime (DirectML)',
        'description': 'DirectML acceleration for AMD Radeon GPUs on Windows - .onnx inference '
                       'without CUDA and without AGPL Ultralytics.',
        'requires_vendor': 'amd',
        'supported_platforms': ('win32',),
        'unsupported_reason': 'DirectML acceleration is only available on Windows',
        'license': 'MIT',
        'packages': ['onnxruntime-directml>=1.18.0'],
        'provides': ['onnxruntime-directml'],
    },
    'onnx_export': {
        'name': 'ONNX Export & Tools',
        'description': 'Tools for exporting models to ONNX and optimizing graphs (onnx, onnxslim).',
        'requires_gpu': False,
        'license': 'MIT',
        'requirements_file': 'requirements-onnx-export.txt',
        'provides': ['onnx', 'onnxslim'],
    },
    'tensorrt': {
        'name': 'TensorRT Acceleration',
        'description': 'NVIDIA TensorRT runtime for ultra-fast GPU inference on .engine models.',
        'requires_gpu': True,
        'license': 'NVIDIA Proprietary',
        'requirements_file': 'requirements-tensorrt.txt',
        'provides': ['tensorrt'],
    },
    'openvino': {
        'name': 'Intel OpenVINO',
        'description': 'Intel OpenVINO runtime for Intel CPU, iGPU/dGPU and NPU acceleration.',
        'requires_gpu': False,
        'license': 'Apache-2.0',
        'requirements_file': 'requirements-openvino.txt',
        'provides': ['openvino'],
    },
    'ultralytics': {
        'name': 'Ultralytics YOLO',
        'description': 'YOLO .pt inference and training. Licensed AGPL-3.0: a commercial license is '
                       'required for closed-source deployments.',
        'requires_gpu': False,
        'requires_pytorch': True,
        'license': 'AGPL-3.0',
        'requirements_file': 'requirements-ultralytics.txt',
        'provides': ['ultralytics'],
    },
    'rf_detr': {
        'name': 'Roboflow RF-DETR',
        'description': 'RF-DETR detection models with Apache-2.0 licensed weights.',
        'requires_gpu': False,
        'requires_pytorch': True,
        'license': 'Apache-2.0',
        'requirements_file': 'requirements-rfdetr.txt',
        'provides': ['rfdetr'],
    },
    'd_fine': {
        'name': 'D-FINE',
        'description': 'D-FINE detector runtime (pyyaml, scipy, onnx) for the vendored model graph.',
        'requires_gpu': False,
        'requires_pytorch': True,
        'license': 'Apache-2.0',
        'requirements_file': 'requirements-dfine.txt',
        'provides': ['pyyaml', 'scipy', 'onnx', 'onnxslim'],
    },
    'rtmdet': {
        'name': 'OpenMMLab RTMDet',
        'description': 'RTMDet via OpenMMLab: installs openmim, then mmengine, mmcv and mmdet '
                       'through mim (pre-built wheels where available).',
        'requires_gpu': False,
        'requires_pytorch': True,
        'license': 'Apache-2.0',
        'requirements_file': 'requirements-rtmdet.txt',
        'provides': ['openmim'],
        'extra_provides': ['mmengine', 'mmcv', 'mmdet'],
        'post_steps': [
            {'label': 'mim install mmengine', 'module': 'mim', 'args': ['install', 'mmengine']},
            {'label': 'mim install mmcv>=2.0.0', 'module': 'mim', 'args': ['install', 'mmcv>=2.0.0']},
            {'label': 'mim install mmdet', 'module': 'mim', 'args': ['install', 'mmdet']},
        ],
    },
}

_HARDWARE_CACHE_TTL_SECONDS = 120.0
_hardware_cache: Dict[str, Any] = {'value': None, 'expires_at': 0.0}
_requirements_cache: Dict[str, Tuple[float, List[str]]] = {}


def is_package_installed(package_name: str) -> bool:
    """Check if a Python package is installed."""
    try:
        importlib.metadata.version(package_name)
        return True
    except (importlib.metadata.PackageNotFoundError, Exception):
        # Fallback to module spec check
        try:
            return importlib.util.find_spec(package_name.replace('-', '_')) is not None
        except Exception:
            return False


def get_package_version(package_name: str) -> Optional[str]:
    """Get the installed version of a Python package."""
    try:
        return importlib.metadata.version(package_name)
    except Exception:
        try:
            mod = __import__(package_name.replace('-', '_'))
            return getattr(mod, '__version__', None)
        except Exception:
            return None


def get_gpu_info() -> Dict[str, Any]:
    """Get GPU and CUDA information."""
    info: Dict[str, Any] = {
        'has_nvidia_gpu': False,
        'cuda_available': False,
        'device_name': None,
        'cuda_version': None,
        'driver_version': None,
        'device_count': 0,
        'device_arch': None,
        'arch_supported': True,
    }

    try:
        from system.utils.utils import _nvidia_smi_query
        name = _nvidia_smi_query('name')
        driver = _nvidia_smi_query('driver_version')
        if name:
            info['has_nvidia_gpu'] = True
            info['device_name'] = name.split('\n')[0].strip()
        if driver:
            info['driver_version'] = driver.split('\n')[0].strip()
    except Exception:
        pass

    try:
        import torch
        if torch.cuda.is_available():
            info['cuda_available'] = True
            info['device_count'] = torch.cuda.device_count()
            if not info['device_name'] and info['device_count'] > 0:
                info['device_name'] = torch.cuda.get_device_name(0)
            info['cuda_version'] = torch.version.cuda
            info['has_nvidia_gpu'] = True
            # A wheel built for newer silicon installs fine and only fails at inference time,
            # so the arch list is compared against the device while torch is right here.
            major, minor = torch.cuda.get_device_capability(0)
            device_sm = f"sm_{major}{minor}"
            info['device_arch'] = device_sm
            try:
                info['arch_supported'] = device_sm in torch.cuda.get_arch_list()
            except Exception:
                info['arch_supported'] = True
    except Exception:
        pass

    return info


def get_hardware_profile(refresh: bool = False) -> Dict[str, Any]:
    """Detect the install-target hardware profile, reusing the result for a short window."""
    now = time.monotonic()
    if not refresh and _hardware_cache['value'] is not None and now < _hardware_cache['expires_at']:
        return _hardware_cache['value']
    profile = detect_hardware_profile()
    _hardware_cache['value'] = profile
    _hardware_cache['expires_at'] = now + _HARDWARE_CACHE_TTL_SECONDS
    return profile


def describe_hardware(hw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Human-readable summary of what the installer will target."""
    hardware = hw or get_hardware_profile()
    labels = {
        'nvidia_cuda': 'NVIDIA CUDA',
        'amd_directml': 'AMD DirectML (Windows)',
        'amd': 'AMD GPU',
        'intel_openvino': 'Intel OpenVINO',
        'cpu': 'CPU only',
    }
    profile = hardware.get('profile') or 'cpu'
    build = resolve_pytorch_builds(hardware)[0]
    compute_cap = hardware.get('compute_cap')
    return {
        'profile': profile,
        'profile_label': labels.get(profile, profile),
        'gpu_name': hardware.get('name'),
        'driver_missing': bool(hardware.get('driver_missing')),
        'cuda_version': hardware.get('cuda_version'),
        'compute_cap': compute_cap,
        'device_arch': compute_cap_to_sm(compute_cap),
        'pytorch_build': build['label'],
        'pytorch_index_url': build['index_url'],
        'pytorch_packages': _pytorch_distributions(build),
        'pytorch_note': build.get('note'),
    }


def _distribution_name(requirement: str) -> str:
    """Extract the distribution name from a PEP 508 requirement line."""
    for separator in ('=', '<', '>', '!', '~', ';', '[', ' ', '@'):
        requirement = requirement.split(separator)[0]
    return requirement.strip()


def read_requirement_names(path: Path) -> List[str]:
    """Read requirement lines from a requirements file (cached by modification time)."""
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    cached = _requirements_cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        raw = path.read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return []
    names: List[str] = []
    for line in raw.splitlines():
        entry = line.split('#')[0].strip()
        if not entry or entry.startswith('-'):
            continue
        names.append(entry)
    _requirements_cache[key] = (mtime, names)
    return names


def bundle_provides(bundle_name: str) -> List[str]:
    """Distribution names a bundle is expected to make available once installed."""
    bundle = PACKAGE_BUNDLES.get(bundle_name) or {}
    provides = list(bundle.get('provides') or [])
    provides.extend(bundle.get('extra_provides') or [])
    if provides:
        return provides
    if bundle.get('requirements_file'):
        return [_distribution_name(req)
                for req in read_requirement_names(PROJECT_ROOT / bundle['requirements_file'])]
    return [_distribution_name(req) for req in bundle.get('packages') or []]


def _norm_dist(name: str) -> str:
    """Compare distribution names the way pip does: case and dash/underscore do not matter."""
    return (name or '').strip().lower().replace('_', '-')


def is_distribution_installed(package_name: str) -> bool:
    """True only when the pip distribution itself is installed.

    Unlike ``is_package_installed``, this does not fall back to an importable module.
    ONNX Runtime wheels all import as ``onnxruntime``, so a module check would treat the
    CPU package as installed whenever the CUDA wheel is present.
    """
    try:
        importlib.metadata.version(package_name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False
    except Exception:
        return False


def bundle_distributions(bundle_name: str) -> List[str]:
    """Pip distributions this bundle installs, excluding the PyTorch base unless it is PyTorch.

    Torch is owned by the ``pytorch`` bundle. Plugin requirements that pin torch are skipped
    so removing a plugin never schedules ``torch`` itself for deletion.
    """
    bundle = PACKAGE_BUNDLES.get(bundle_name) or {}
    names: List[str] = []
    torch_names = {_norm_dist(name) for name in PYTORCH_DISTRIBUTIONS}
    if bundle.get('build') == 'pytorch':
        names.extend(PYTORCH_DISTRIBUTIONS)
    else:
        for req in bundle.get('packages') or []:
            names.append(_distribution_name(req))
        if bundle.get('requirements_file'):
            for req in read_requirement_names(PROJECT_ROOT / bundle['requirements_file']):
                dist = _distribution_name(req)
                if _norm_dist(dist) in torch_names:
                    continue
                names.append(dist)
        names.extend(bundle.get('extra_provides') or [])

    ordered: List[str] = []
    seen = set()
    for name in names:
        key = _norm_dist(name)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(name)
    return ordered


def _core_distribution_names() -> set:
    """Distributions the application itself imports. They are never uninstalled from the UI."""
    return {
        _norm_dist(_distribution_name(req))
        for req in read_requirement_names(PROJECT_ROOT / 'requirements.txt')
    }


def _protected_distributions(bundle_name: str, hw: Dict[str, Any], gpu: Dict[str, Any]) -> set:
    """Packages that must stay when this bundle is removed.

    Core requirements always stay. Another bundle keeps a shared package only when that
    bundle is installed on its own: it has at least one installed distribution that this
    bundle does not provide and that the application itself does not require. Otherwise
    two bundles that list the same optional packages would block each other forever.
    """
    own = {_norm_dist(name) for name in bundle_distributions(bundle_name)}
    core = _core_distribution_names()
    protected = set(core)
    for other_name in PACKAGE_BUNDLES:
        if other_name == bundle_name:
            continue
        status = get_bundle_status(other_name, hw, gpu)
        if not status or not status.get('installed'):
            continue
        other_dists = bundle_distributions(other_name)
        independent = [
            name for name in other_dists
            if _norm_dist(name) not in own
            and _norm_dist(name) not in core
            and is_distribution_installed(name)
        ]
        if not independent:
            continue
        protected.update(_norm_dist(name) for name in other_dists)
    return protected


def _installed_pytorch_dependents(hw: Dict[str, Any], gpu: Dict[str, Any]) -> List[str]:
    """Display names of installed bundles that cannot run without PyTorch."""
    names: List[str] = []
    for other_name, bundle in PACKAGE_BUNDLES.items():
        if other_name == 'pytorch' or not bundle.get('requires_pytorch'):
            continue
        status = get_bundle_status(other_name, hw, gpu)
        if status and status.get('installed'):
            names.append(bundle['name'])
    return names


def plan_uninstall(bundle_name: str) -> Dict[str, Any]:
    """Decide which distributions a bundle removal may delete.

    Shared packages stay installed. PyTorch stays until every plugin that needs it is gone,
    because removing torch while those plugins remain leaves them installed and broken.
    """
    if bundle_name not in PACKAGE_BUNDLES:
        return {
            'ok': False,
            'reason': "Unknown bundle '{bundle}'.",
            'reason_params': {'bundle': bundle_name},
        }

    hw = get_hardware_profile()
    gpu = get_gpu_info()
    status = get_bundle_status(bundle_name, hw, gpu)
    if not status or not status.get('installed'):
        return {'ok': False, 'reason': 'This component is not installed.'}

    if bundle_name == 'pytorch':
        dependents = _installed_pytorch_dependents(hw, gpu)
        if dependents:
            return {
                'ok': False,
                'reason': 'Remove the plugins that depend on PyTorch first: {names}',
                'reason_params': {'names': ', '.join(dependents)},
            }

    protected = _protected_distributions(bundle_name, hw, gpu)
    packages = [
        name for name in reversed(bundle_distributions(bundle_name))
        if _norm_dist(name) not in protected and is_distribution_installed(name)
    ]
    if not packages:
        return {
            'ok': False,
            'reason': 'There is nothing to remove. These packages are still required by '
                      'the application or by another installed component.',
        }
    return {'ok': True, 'packages': packages}


def _cuda_build_mismatch(hw: Dict[str, Any], gpu: Dict[str, Any]) -> bool:
    """True when a CUDA build is wanted but the installed torch cannot drive this GPU."""
    if (hw.get('profile') or '') != 'nvidia_cuda':
        return False
    if hw.get('driver_missing'):
        return False
    return not gpu.get('cuda_available') or not gpu.get('arch_supported', True)


def _needs_pytorch_build(hw: Dict[str, Any], gpu: Dict[str, Any]) -> bool:
    """True when PyTorch is absent, or is a build without CUDA on a CUDA-capable machine."""
    if not is_package_installed('torch'):
        return True
    return _cuda_build_mismatch(hw, gpu)


def _pytorch_distributions(build: Dict[str, Any]) -> List[str]:
    """Wheel names for one build: the pinned set for old architectures, plain torch otherwise."""
    return list(build.get('packages') or PYTORCH_DISTRIBUTIONS)


def _pytorch_step(hw: Dict[str, Any], gpu: Dict[str, Any]) -> Dict[str, Any]:
    """PyTorch install step: hardware-matched wheel index variants, then plain PyPI fallback."""
    force_reinstall = is_package_installed('torch') and _cuda_build_mismatch(hw, gpu)
    variants: List[Dict[str, Any]] = []
    for build in resolve_pytorch_builds(hw):
        args = ['install']
        if force_reinstall and build['force_reinstall']:
            args.append('--force-reinstall')
        args += _pytorch_distributions(build) + ['--index-url', build['index_url']]
        variants.append({'label': build['label'], 'args': args})
    return {
        'label': f"PyTorch ({variants[0]['label']})",
        'kind': 'pytorch',
        'variants': variants,
        'fallback_args': ['install', *PYTORCH_DISTRIBUTIONS],
    }


def build_bundle_steps(
        bundle_name: str,
        hw: Optional[Dict[str, Any]] = None,
        gpu: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Translate a bundle definition into the ordered pip/mim steps to run."""
    bundle = PACKAGE_BUNDLES[bundle_name]
    hardware = hw or get_hardware_profile()
    gpu_info = gpu or get_gpu_info()

    requirement_names: List[str] = []
    if bundle.get('requirements_file'):
        requirement_names = read_requirement_names(PROJECT_ROOT / bundle['requirements_file'])

    uses_torch = (
        bool(bundle.get('requires_pytorch'))
        or bundle.get('build') == 'pytorch'
        or any(_distribution_name(req) in PYTORCH_DISTRIBUTIONS for req in requirement_names)
    )

    steps: List[Dict[str, Any]] = []
    if bundle.get('build') == 'pytorch':
        steps.append(_pytorch_step(hardware, gpu_info))
    elif bundle.get('requires_pytorch') and _needs_pytorch_build(hardware, gpu_info):
        # Installing a torch-dependent plugin before torch exists would let pip pull the
        # CPU-only PyPI wheel, so the hardware-matched build is installed first.
        steps.append(_pytorch_step(hardware, gpu_info))

    # --upgrade also refreshes transitive dependencies, which would overwrite a working CUDA
    # torch build; it is therefore only used by bundles that stay out of the torch ecosystem.
    prefix = ['install'] if uses_torch else ['install', '--upgrade']

    if bundle.get('packages'):
        steps.append({'label': bundle['name'], 'kind': 'pip', 'args': prefix + list(bundle['packages'])})
    elif requirement_names:
        specs = [req for req in requirement_names if _distribution_name(req) not in PYTORCH_DISTRIBUTIONS]
        if specs:
            steps.append({'label': bundle['name'], 'kind': 'pip', 'args': prefix + specs})
    for post in bundle.get('post_steps') or []:
        steps.append({'label': post['label'], 'kind': 'module',
                      'module': post['module'], 'args': list(post['args'])})
    return steps


def _bundle_blockers(bundle: Dict[str, Any], hw: Dict[str, Any], gpu: Dict[str, Any]) -> List[str]:
    """Hardware or operating-system reasons why a bundle must not be installed here."""
    reasons: List[str] = []
    profile = hw.get('profile') or 'cpu'

    if bundle.get('requires_gpu') and not (gpu.get('has_nvidia_gpu') or profile == 'nvidia_cuda'):
        reasons.append('An NVIDIA GPU is required')

    if bundle.get('requires_vendor') == 'amd' and profile not in ('amd_directml', 'amd'):
        reasons.append('An AMD GPU is required')

    platforms = bundle.get('supported_platforms')
    if platforms and sys.platform not in platforms:
        reasons.append(bundle.get('unsupported_reason')
                       or 'This package is not available on this operating system')

    return reasons


def _bundle_warnings(bundle_name: str, hw: Dict[str, Any], gpu: Dict[str, Any]) -> List[str]:
    """Non-blocking cautions about what the installer will actually produce on this machine."""
    warnings: List[str] = []

    if bundle_name == 'pytorch':
        build = resolve_pytorch_builds(hw)[0]
        if build.get('note'):
            warnings.append(build['note'])
    elif bundle_name == 'tensorrt':
        message = engine_fp16_modelopt_message()
        if message:
            warnings.append(message)
    elif bundle_name in ('onnx_runtime_gpu', 'onnx_runtime_directml') and is_package_installed('onnxruntime'):
        # All ONNX Runtime flavours install into the same 'onnxruntime' package directory.
        warnings.append('The CPU onnxruntime package is also installed; remove it if the GPU providers do not load.')

    return warnings


def get_bundle_status(bundle_name: str, hw: Optional[Dict[str, Any]] = None,
                      gpu: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Describe one bundle: installation state plus whether it can be installed here."""
    bundle = PACKAGE_BUNDLES.get(bundle_name)
    if bundle is None:
        return None
    hardware = hw or get_hardware_profile()
    gpu_info = gpu or get_gpu_info()

    components = [
        {'name': name, 'installed': is_package_installed(name), 'version': get_package_version(name)}
        for name in bundle_provides(bundle_name)
    ]
    installed = bool(components) and all(item['installed'] for item in components)

    reasons = _bundle_blockers(bundle, hardware, gpu_info)

    result: Dict[str, Any] = {
        'key': bundle_name,
        'name': bundle['name'],
        'description': bundle['description'],
        'license': bundle.get('license'),
        'requires_gpu': bool(bundle.get('requires_gpu')),
        'requires_vendor': bundle.get('requires_vendor'),
        'requires_pytorch': bool(bundle.get('requires_pytorch')),
        'installed': installed,
        'components': components,
        'available': not reasons,
        'reasons': reasons,
        'warnings': [] if reasons else _bundle_warnings(bundle_name, hardware, gpu_info),
        'steps': [step['label'] for step in build_bundle_steps(bundle_name, hardware, gpu_info)],
    }
    versions = [item['version'] for item in components if item['version']]
    if installed and len(components) == 1 and versions:
        result['version'] = versions[0]
    return result


def get_bundles_status(hw: Optional[Dict[str, Any]] = None,
                       gpu: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Status of every installable bundle, keyed by bundle id."""
    hardware = hw or get_hardware_profile()
    gpu_info = gpu or get_gpu_info()
    return {name: get_bundle_status(name, hardware, gpu_info) for name in PACKAGE_BUNDLES}


def _trt_major_version() -> Optional[int]:
    """Return the installed TensorRT major version, or None if TensorRT is not available."""
    try:
        import tensorrt as trt
        return int(str(trt.__version__).split('.', 1)[0])
    except Exception:
        return None


ENGINE_FP16_MODELOPT_MESSAGE = (
    'TensorRT 11 is installed. FP16 engine export needs nvidia-modelopt, which is not installed. '
    'On the System Info page, click Update on TensorRT Acceleration to reinstall TensorRT 10.x. '
    'That build creates FP16 engines without this package. Uncheck FP16 to export FP32 with the current TensorRT.'
)


def engine_fp16_modelopt_message() -> Optional[str]:
    """Why an FP16 .engine export would fail, or None when this TensorRT build can do it."""
    major = _trt_major_version()
    if major is None or major < 11 or is_package_installed('nvidia-modelopt'):
        return None
    return ENGINE_FP16_MODELOPT_MESSAGE


def get_export_provider_capabilities(
        gpu_info: Optional[Dict[str, Any]] = None,
        yolo_provider: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Describe installed export paths without implying all models are compatible."""
    gpu = gpu_info or get_gpu_info()
    if yolo_provider is None:
        from system.detection.registry import get_provider_status
        yolo_provider = get_provider_status('yolo')

    capabilities = {}
    for export_format, dependencies, hardware_required in (
            ('onnx', ('onnx',), False),
            ('engine', ('tensorrt',), True),
    ):
        reasons = []
        if not yolo_provider.get('available'):
            reasons.append(yolo_provider.get('error') or 'Ultralytics exporter is unavailable')
        missing_export_dependencies = [
            name for name in dependencies if not is_package_installed(name)
        ]
        if missing_export_dependencies:
            reasons.append(
                f"Missing export dependencies: {', '.join(missing_export_dependencies)}"
            )
        if hardware_required and not gpu.get('has_nvidia_gpu'):
            reasons.append('An NVIDIA GPU is required')

        # TensorRT 11 removed the FP16 builder flag. Ultralytics then imports modelopt,
        # which this installer does not ship: the TensorRT 10.x pin builds FP16 directly.
        fp16_note = engine_fp16_modelopt_message() if export_format == 'engine' and not missing_export_dependencies else None

        entry: Dict[str, Any] = {
            'format': export_format,
            'extension': f'.{export_format}',
            'exporter': 'ultralytics',
            'supported': True,
            'available': not reasons,
            'requirements': ['torch', 'ultralytics', *dependencies]
                + (['NVIDIA GPU'] if hardware_required else []),
            'reasons': reasons,
        }
        if fp16_note:
            entry['fp16_note'] = fp16_note
        capabilities[export_format] = entry
    return capabilities


def get_runtime_status() -> Dict[str, Any]:
    """Get full status of inference runtimes and hardware."""
    gpu = get_gpu_info()
    hw = get_hardware_profile()
    from system.detection.registry import get_provider_status, get_provider_statuses

    # ONNX & ONNX Runtime
    onnx_installed = is_package_installed('onnx')
    onnx_version = get_package_version('onnx')
    onnxslim_installed = is_package_installed('onnxslim')

    ort_installed = False
    ort_version = None
    ort_providers: List[str] = []
    try:
        import onnxruntime as ort
        ort_installed = True
        ort_version = getattr(ort, '__version__', None)
        ort_providers = ort.get_available_providers()
    except Exception:
        pass

    # TensorRT
    trt_installed = False
    trt_version = None
    try:
        import tensorrt as trt
        trt_installed = True
        trt_version = getattr(trt, '__version__', None)
    except Exception:
        pass

    # PyTorch
    torch_installed = False
    torch_version = None
    try:
        import torch
        torch_installed = True
        torch_version = getattr(torch, '__version__', None)
    except Exception:
        pass

    # OpenVINO
    openvino_installed = False
    openvino_version = None
    try:
        import openvino
        openvino_installed = True
        openvino_version = getattr(openvino, '__version__', None)
    except Exception:
        pass

    # Ultralytics
    ultralytics_installed = is_package_installed('ultralytics')
    ultralytics_version = get_package_version('ultralytics')

    packages_status = {
        'onnx': {'installed': onnx_installed, 'version': onnx_version},
        'onnxslim': {'installed': onnxslim_installed, 'version': get_package_version('onnxslim')},
        'onnxruntime': {'installed': ort_installed, 'version': ort_version, 'providers': ort_providers},
        'tensorrt': {'installed': trt_installed, 'version': trt_version},
        'torch': {'installed': torch_installed, 'version': torch_version, 'cuda': gpu['cuda_available']},
        'ultralytics': {'installed': ultralytics_installed, 'version': ultralytics_version},
        'openvino': {'installed': openvino_installed, 'version': openvino_version},
    }

    export_capabilities = get_export_provider_capabilities(
        gpu,
        get_provider_status('ultralytics'),
    )
    can_export_onnx = export_capabilities['onnx']['available']
    can_export_engine = export_capabilities['engine']['available']
    can_run_engine = bool(trt_installed and gpu['has_nvidia_gpu'])

    return {
        'gpu': gpu,
        'hardware': describe_hardware(hw),
        'packages': packages_status,
        'providers': get_provider_statuses(),
        'export_capabilities': export_capabilities,
        'onnx': {
            'export_ready': can_export_onnx,
            'inference_ready': ort_installed,
            'version': ort_version or onnx_version,
            'providers': ort_providers,
        },
        'tensorrt': {
            'export_ready': can_export_engine,
            'inference_ready': can_run_engine,
            'version': trt_version,
            'supported_on_hardware': gpu['has_nvidia_gpu'],
        },
        'bundles': get_bundles_status(hw, gpu),
    }


_COLLECTION_INTENTS = frozenset({
    'video_test', 'collect_dataset', 'explore', 'collection', 'none', '',
})

_PROVIDER_PRIMARY_BUNDLE: Dict[str, str] = {
    'ultralytics': 'ultralytics',
    'onnxruntime': 'onnxruntime',
    'onnx': 'onnxruntime',
    'rf_detr': 'rf_detr',
    'd_fine': 'd_fine',
    'rtmdet': 'rtmdet',
}


def _dependency_to_bundle_index() -> Dict[str, List[str]]:
    index: Dict[str, List[str]] = {}
    for bundle_name in PACKAGE_BUNDLES:
        for dist in bundle_provides(bundle_name):
            key = _norm_dist(dist)
            index.setdefault(key, [])
            if bundle_name not in index[key]:
                index[key].append(bundle_name)
    return index


def _pick_onnx_bundle(hw: Dict[str, Any], gpu: Dict[str, Any]) -> str:
    for candidate in ('onnx_runtime_gpu', 'onnx_runtime_directml', 'onnxruntime'):
        status = get_bundle_status(candidate, hw, gpu)
        if status and status.get('available'):
            return candidate
    return 'onnxruntime'


def _bundle_plan_items(keys: List[str], hw: Dict[str, Any], gpu: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Full install-time status of every planned bundle, in plan order."""
    items: List[Dict[str, Any]] = []
    for key in keys:
        status = get_bundle_status(key, hw, gpu)
        if status:
            items.append(status)
    return items


def _add_needed_bundle(key: str, required: List[str], blocked: List[str],
                       hw: Dict[str, Any], gpu: Dict[str, Any]) -> bool:
    """Record a bundle the plan needs.

    Returns True when the bundle can be installed here; a bundle that this hardware or
    operating system cannot run is recorded as blocked so the UI can explain the dead end
    instead of silently dropping it from the list.
    """
    status = get_bundle_status(key, hw, gpu)
    if not status or status.get('installed'):
        return False
    if not status.get('available'):
        if key not in blocked:
            blocked.append(key)
        return False
    if key not in required:
        required.append(key)
    return True


def _core_only_plan(note: str) -> Dict[str, Any]:
    """Empty bundle plan for collection and preview modes."""
    return {
        'required': [],
        'items': [],
        'blocked': [],
        'optional': [],
        'provider': None,
        'missing_deps': [],
        'notes': [note],
        'warnings': [],
    }


def resolve_bundles_for_inference(
        inference_intent: Optional[str] = None,
        model_type: Optional[str] = None,
        weights_path: Optional[str] = None,
        target_mode: Optional[str] = None,
        hw: Optional[Dict[str, Any]] = None,
        gpu: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute minimal runtime bundles still required for the requested inference profile.
    Collection / video-only intents return an empty required set.

    ``required`` lists bundles the installer can run here, ``blocked`` the ones this
    machine cannot run. Both are expanded into ``items``/``blocked`` status records so a
    client does not need a second request to render names, licences and pip steps.
    """
    from pathlib import Path

    intent = (inference_intent or '').strip().lower()
    mode = (target_mode or '').strip().lower()
    weights = (weights_path or '').strip()
    model = (model_type or '').strip().lower()

    if mode == 'collection' or intent in _COLLECTION_INTENTS:
        return _core_only_plan('Core runtime only (no ML bundles needed).')

    from system.detection.registry import get_provider_status, resolve_architecture

    hardware = hw or get_hardware_profile()
    gpu_info = gpu or get_gpu_info()

    # Training needs the torch stack whether or not a weights file was chosen yet.
    if intent == 'train':
        required: List[str] = []
        blocked: List[str] = []
        for key in ('pytorch', 'ultralytics'):
            _add_needed_bundle(key, required, blocked, hardware, gpu_info)
        return {
            'required': required,
            'items': _bundle_plan_items(required, hardware, gpu_info),
            'blocked': _bundle_plan_items(blocked, hardware, gpu_info),
            'optional': [],
            'provider': 'ultralytics',
            'missing_deps': [],
            'notes': ['Training requires PyTorch and Ultralytics when not already installed.'],
            'warnings': [],
        }

    if not weights or model in ('none', 'preview'):
        return _core_only_plan('Core runtime only (no ML bundles needed).')

    resolved = resolve_architecture(model_type, weights_path)
    if model in ('none', 'preview'):
        return _core_only_plan('Preview/collection — no inference bundles.')

    provider = get_provider_status(resolved)
    missing = [name for name, ok in (provider.get('dependencies') or {}).items() if not ok]
    dep_index = _dependency_to_bundle_index()
    required = []
    blocked = []
    notes: List[str] = []
    warnings: List[str] = []

    provider_bundle = _PROVIDER_PRIMARY_BUNDLE.get(resolved)
    if provider_bundle in ('onnxruntime', 'onnx'):
        provider_bundle = _pick_onnx_bundle(hardware, gpu_info)

    for dep in missing:
        bundles_for_dep = list(dep_index.get(_norm_dist(dep), []))
        if _norm_dist(dep) == 'onnxruntime' and provider_bundle:
            bundles_for_dep = [provider_bundle]
        if _norm_dist(dep) == 'torch' and 'pytorch' not in bundles_for_dep:
            bundles_for_dep.insert(0, 'pytorch')
        unavailable: List[str] = []
        for candidate in bundles_for_dep:
            status = get_bundle_status(candidate, hardware, gpu_info)
            if not status or status.get('installed'):
                continue
            if status.get('available'):
                if candidate not in required:
                    required.append(candidate)
                    warnings.extend(status.get('warnings') or [])
                break
            if candidate not in unavailable:
                unavailable.append(candidate)
        else:
            # Nothing could be installed for this dependency: report the dead end instead of
            # dropping it, otherwise the wizard lists no component while inference still fails.
            for candidate in unavailable:
                if candidate not in required and candidate not in blocked:
                    blocked.append(candidate)

    if provider_bundle:
        _add_needed_bundle(provider_bundle, required, blocked, hardware, gpu_info)

    suffix = Path(weights).suffix.lower()
    if suffix in ('.engine', '.trt'):
        _add_needed_bundle('tensorrt', required, blocked, hardware, gpu_info)

    if _needs_pytorch_build(hardware, gpu_info):
        needs_torch_bundle = any(
            PACKAGE_BUNDLES.get(b, {}).get('requires_pytorch') for b in required
        )
        if needs_torch_bundle or resolved in ('ultralytics', 'rf_detr', 'd_fine', 'rtmdet'):
            _add_needed_bundle('pytorch', required, blocked, hardware, gpu_info)

    if 'pytorch' in required:
        # Every torch-dependent plugin installs on top of it, so the client must run it first.
        required.remove('pytorch')
        required.insert(0, 'pytorch')

    if missing:
        notes.append(f"Provider {resolved}: missing {', '.join(missing)}")
    elif not provider.get('inference_available'):
        notes.append(provider.get('error') or f"Provider {resolved} unavailable")

    return {
        'required': required,
        'items': _bundle_plan_items(required, hardware, gpu_info),
        'blocked': _bundle_plan_items(blocked, hardware, gpu_info),
        'optional': [],
        'provider': resolved,
        'missing_deps': missing,
        'notes': notes,
        'warnings': warnings,
    }


class RuntimeManager:
    """Manager for installing and removing AI runtime dependencies in the background."""

    _instance: Optional[RuntimeManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> RuntimeManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self) -> None:
        self.state_lock = threading.Lock()
        self.status = 'idle'  # 'idle' | 'running' | 'success' | 'error' | 'cancelled'
        self.action: Optional[str] = None  # 'install' | 'uninstall'
        self.active_bundle: Optional[str] = None
        self.logs: List[str] = []
        self.error_message: Optional[str] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.cancel_event = threading.Event()
        self.process: Optional[subprocess.Popen] = None
        self.step_index = 0
        self.step_total = 0
        self.current_step: Optional[str] = None
        self.restart_required = False

    def get_install_status(self) -> Dict[str, Any]:
        with self.state_lock:
            return {
                'status': self.status,
                'action': self.action,
                'bundle': self.active_bundle,
                'logs': list(self.logs),
                'error': self.error_message,
                'step_index': self.step_index,
                'step_total': self.step_total,
                'current_step': self.current_step,
                'restart_required': self.restart_required,
                'can_cancel': self.status == 'running',
            }

    def start_install(self, bundle_name: str) -> Dict[str, Any]:
        """Start background installation of the requested bundle."""
        if bundle_name not in PACKAGE_BUNDLES:
            return {
                'ok': False,
                'error': f"Unknown bundle '{bundle_name}'. Available: {list(PACKAGE_BUNDLES.keys())}",
            }

        bundle_def = PACKAGE_BUNDLES[bundle_name]
        hw = get_hardware_profile(refresh=True)
        gpu_info = get_gpu_info()
        blockers = _bundle_blockers(bundle_def, hw, gpu_info)
        if blockers:
            return {
                'ok': False,
                'reason': blockers[0],
                'error': f"Bundle '{bundle_name}' cannot be installed here: {blockers[0]}.",
            }

        try:
            steps = build_bundle_steps(bundle_name, hw, gpu_info)
        except Exception as exc:
            return {'ok': False, 'error': f"Could not prepare the installation steps: {exc}"}
        if not steps:
            return {'ok': False, 'error': f"Bundle '{bundle_name}' has nothing to install."}

        opening = f"Starting installation of {bundle_def['name']}..."
        busy = self._claim_job(bundle_name, 'install', steps, opening)
        if busy is not None:
            return busy

        return {
            'ok': True,
            'bundle': bundle_name,
            'action': 'install',
            'status': 'running',
            'steps': [step['label'] for step in steps],
            'hardware': describe_hardware(hw),
        }

    def start_uninstall(self, bundle_name: str) -> Dict[str, Any]:
        """Start background removal of the packages that belong only to this bundle."""
        plan = plan_uninstall(bundle_name)
        if not plan.get('ok'):
            return plan

        packages = list(plan['packages'])
        bundle_def = PACKAGE_BUNDLES[bundle_name]
        steps = [{
            'label': 'pip uninstall ' + ' '.join(packages),
            'kind': 'pip',
            'module': 'pip',
            'args': ['uninstall', '-y', *packages],
        }]
        opening = f"Starting removal of {bundle_def['name']} ({', '.join(packages)})..."
        busy = self._claim_job(bundle_name, 'uninstall', steps, opening)
        if busy is not None:
            return busy

        return {
            'ok': True,
            'bundle': bundle_name,
            'action': 'uninstall',
            'status': 'running',
            'packages': packages,
            'steps': [step['label'] for step in steps],
        }

    def _claim_job(self, bundle_name: str, action: str, steps: List[Dict[str, Any]],
                   opening_log: str) -> Optional[Dict[str, Any]]:
        """Mark a job running and start its worker. Returns an error payload when one is busy."""
        with self.state_lock:
            if self.status == 'running':
                return {
                    'ok': False,
                    'reason': 'A package job is already running for {bundle}.',
                    'reason_params': {'bundle': self.active_bundle or ''},
                }

            self.status = 'running'
            self.action = action
            self.active_bundle = bundle_name
            self.logs = [opening_log]
            self.error_message = None
            self.cancel_event = threading.Event()
            self.process = None
            self.step_index = 0
            self.step_total = len(steps)
            self.current_step = None
            self.restart_required = False

            self.worker_thread = threading.Thread(
                target=self._run_job_worker,
                args=(bundle_name, steps, action),
                daemon=True,
            )
            self.worker_thread.start()
        return None

    def cancel_install(self) -> Dict[str, Any]:
        """Abort the running install or removal job."""
        with self.state_lock:
            if self.status != 'running':
                return {'ok': False, 'error': 'No installation job is running.'}
            self.cancel_event.set()
            process = self.process
        if process is not None:
            try:
                process.kill()
                self._append_log('Cancellation requested: terminating the installer process...')
            except Exception as exc:
                self._append_log(f"Could not terminate the installer process: {exc}")
        else:
            self._append_log('Cancellation requested: stopping after the current step...')
        return {'ok': True, 'status': 'cancelled'}

    def _run_job_worker(self, bundle_name: str, steps: List[Dict[str, Any]], action: str) -> None:
        """Worker thread executing each install or removal step in order."""
        phase = 'removal' if action == 'uninstall' else 'installation'
        for step in steps:
            if self.cancel_event.is_set():
                self._finish_cancelled()
                return
            with self.state_lock:
                self.current_step = step['label']
                self.step_index += 1
                self.logs.append(f"[{self.step_index}/{self.step_total}] {step['label']}")

            if step.get('kind') == 'pytorch':
                ok = self._run_pytorch_step(step)
            else:
                ok = self._run_step(step.get('module', 'pip'), step['args'], step['label'], phase)

            if self.cancel_event.is_set():
                self._finish_cancelled()
                return
            if not ok:
                with self.state_lock:
                    self.status = 'error'
                    self.current_step = None
                    self.error_message = self.error_message or f"Step '{step['label']}' failed."
                    self.logs.append(f"Error: {self.error_message}")
                return

        with self.state_lock:
            self.status = 'success'
            self.current_step = None
            # pip rewrites site-packages underneath the running process, so the import
            # state is only guaranteed to match the environment after a restart.
            self.restart_required = True
            if action == 'uninstall':
                self.logs.append(f"Successfully removed bundle '{bundle_name}'. "
                                 f"Restart the server to unload it.")
            else:
                self.logs.append(f"Successfully installed bundle '{bundle_name}'. "
                                 f"Restart the server to load it.")

    def _run_pytorch_step(self, step: Dict[str, Any]) -> bool:
        """Try each hardware-matched PyTorch wheel index, then plain PyPI."""
        for index, variant in enumerate(step['variants']):
            label = f"PyTorch {variant['label']}"
            if index:
                self._append_log(f"Retrying with {label}...")
            if self._run_step('pip', variant['args'], label):
                return True
            if self.cancel_event.is_set():
                return False
        self._append_log('Falling back to the default PyPI PyTorch build...')
        return self._run_step('pip', step['fallback_args'], 'PyTorch (PyPI)')

    def _run_step(self, module: str, args: List[str], label: str, phase: str = 'installation') -> bool:
        """Run ``python -m <module> <args>`` and stream its output into the web log."""
        cmd = [sys.executable, '-m', module] + list(args)
        self._append_log(f"Executing: {' '.join(cmd)}")
        env = dict(os.environ)
        env['PYTHONUNBUFFERED'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
                creationflags=creationflags,
            )
            with self.state_lock:
                self.process = process

            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    stripped = line.rstrip()
                    if stripped:
                        self._append_log(stripped)
                    if self.cancel_event.is_set():
                        break

            if self.cancel_event.is_set():
                try:
                    process.kill()
                except Exception:
                    pass
            process.wait()
            ret_code = process.returncode
        except Exception as exc:
            with self.state_lock:
                self.process = None
                self.error_message = str(exc)
                self.logs.append(f"Exception during {phase}: {exc}")
            return False

        with self.state_lock:
            self.process = None
            if ret_code == 0:
                self.logs.append(f"Step '{label}' finished successfully.")
                return True
            if self.cancel_event.is_set():
                return False
            self.error_message = f"'{module} {args[0]}' exited with code {ret_code}"
            self.logs.append(f"Error: {self.error_message}")
            return False

    def _finish_cancelled(self) -> None:
        with self.state_lock:
            self.status = 'cancelled'
            self.current_step = None
            self.process = None
            label = 'Removal' if self.action == 'uninstall' else 'Installation'
            self.error_message = f'{label} cancelled.'
            self.logs.append(f'{label} cancelled.')

    def _append_log(self, text: str) -> None:
        with self.state_lock:
            self.logs.append(text)
            # Limit log buffer to last 500 lines
            if len(self.logs) > 500:
                self.logs = self.logs[-500:]


# Global runtime manager singleton
runtime_manager = RuntimeManager()
