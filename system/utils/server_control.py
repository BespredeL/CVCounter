# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 12.10.2026
# Website: https://bespredel.name

"""
Server process management and restart utilities.
Supports clean cross-platform restarts without port collisions or process leaks.
Controlled by config option 'server.allow_web_control'.
"""

import os
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

from system.utils.app_context import get_app_context
from system.utils.logger import Logger
from system.utils.paths import get_project_root


def is_web_control_allowed(context: Optional[Dict[str, Any]] = None) -> bool:
    """
    Check if web control / server management is enabled in the configuration.

    Args:
        context (dict, optional): Application context dictionary.

    Returns:
        bool: True if allow_web_control is enabled, False otherwise.
    """
    if context is None:
        context = get_app_context()
    config = context.get('config') if context else None
    if config:
        return bool(config.get('server.allow_web_control', True))
    return True


def cleanup_app_resources(context: Optional[Dict[str, Any]] = None) -> None:
    """
    Perform a clean, graceful shutdown of background threads, cameras,
    database connections, and telemetry before process restart.

    Args:
        context (dict, optional): Application context dictionary.
    """
    logger = Logger()
    if context is None:
        context = get_app_context()
    if not context:
        return

    logger.info("Cleaning up application resources for server restart...")

    thread_manager = context.get('thread_manager')
    object_counters = context.get('object_counters')
    lock = context.get('lock')
    db_manager = context.get('db_manager')

    if thread_manager and object_counters and lock:
        try:
            with lock:
                counters_copy = object_counters.copy()
            if counters_copy:
                logger.info(f"Stopping {len(counters_copy)} object counter(s)...")
                results = thread_manager.stop_all_threads(counters_copy)
                for location, counter in counters_copy.items():
                    if location not in results or not results[location]:
                        try:
                            counter.cleanup()
                        except Exception as e:
                            logger.error(f"Error during counter cleanup for {location}: {e}")
                with lock:
                    object_counters.clear()
        except Exception as e:
            logger.error(f"Error during thread shutdown: {e}")

    if db_manager:
        try:
            logger.info("Closing database connections...")
            db_manager.close()
        except Exception as e:
            logger.error(f"Error closing database: {e}")

    try:
        from system.utils.telemetry import get_telemetry
        telemetry = get_telemetry()
        telemetry.track('server_restarting')
        telemetry.shutdown(timeout=1.5)
    except Exception as e:
        logger.error(f"Error during telemetry shutdown: {e}")

    logger.info("Resource cleanup completed.")


def execute_process_restart() -> None:
    """
    Re-launch the application process and terminate the current one.
    On Linux/macOS, uses os.execv to replace the process image in-place.
    On Windows, launches a detached lightweight trampoline script that waits
    for the current process to fully exit and release its TCP port before spawning
    the single replacement instance.
    """
    logger = Logger()
    root_dir = str(get_project_root())
    executable = sys.executable

    # Ensure target script argument is resolved to project's app.py
    app_script = os.path.join(root_dir, 'app.py')
    args = list(sys.argv)
    if args and os.path.exists(args[0]) and os.path.abspath(args[0]).startswith(root_dir) and not args[0].endswith('__main__.py'):
        target_script = os.path.abspath(args[0])
        args[0] = target_script
    else:
        args = [app_script]

    logger.info(f"Executing server restart (Platform: {sys.platform}, Executable: {executable}, Script: {args[0]})")

    # Clean environment variables that can break a newly spawned process.
    # Specifically, strip Werkzeug reloader variables (WERKZEUG_RUN_MAIN, WERKZEUG_SERVER_FD),
    # which cause [WinError 10038] when Werkzeug tries to adopt an invalid/closed socket FD.
    clean_env = os.environ.copy()
    for key in list(clean_env.keys()):
        if key.startswith('WERKZEUG_'):
            clean_env.pop(key, None)

    if sys.platform == 'win32':
        # Detached trampoline script for Windows:
        # 1. Sleeps 1.2s to guarantee the parent process is completely terminated
        #    and the Windows kernel releases the bound TCP port (avoiding WinError 10048).
        # 2. Spawns the single new server process with cleaned environment.
        # 3. Trampoline exits immediately.
        trampoline_cmd = [
            executable,
            "-c",
            "import os, time, subprocess, sys; "
            "[os.environ.pop(k, None) for k in list(os.environ) if k.startswith('WERKZEUG_')]; "
            "time.sleep(1.2); "
            "subprocess.Popen([sys.argv[2]] + sys.argv[3:], cwd=sys.argv[1])",
            root_dir,
            executable,
        ] + args

        subprocess.Popen(
            trampoline_cmd,
            cwd=root_dir,
            env=clean_env,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        # Terminate current process immediately
        os._exit(0)
    else:
        # POSIX (Linux, macOS): Replaces current process in-place with the exact same PID
        os.execve(executable, [executable] + args, clean_env)


def schedule_server_restart(
    context: Optional[Dict[str, Any]] = None,
    delay: float = 0.8,
    execute: bool = True
) -> Tuple[bool, str]:
    """
    Schedule a graceful server restart with an initial delay to allow
    the HTTP response to be flushed to the client.

    Args:
        context (dict, optional): Application context.
        delay (float): Seconds to delay before initiating shutdown.
        execute (bool): Whether to actually execute process replacement (False for dry-run/testing).

    Returns:
        tuple: (success: bool, message: str)
    """
    if context is None:
        context = get_app_context()

    if not is_web_control_allowed(context):
        return False, "Server control via web interface is disabled in configuration"

    def _worker():
        time.sleep(max(0.1, delay))
        try:
            cleanup_app_resources(context)
        except Exception as e:
            Logger().error(f"Error during pre-restart cleanup: {e}")

        if execute:
            execute_process_restart()

    thread = threading.Thread(target=_worker, daemon=True, name="ServerRestartWorker")
    thread.start()

    return True, "Server restart scheduled successfully"


def execute_process_shutdown() -> None:
    """
    Terminate the server application process cleanly.
    """
    logger = Logger()
    logger.info("Executing server shutdown...")
    os._exit(0)


def schedule_server_shutdown(
    context: Optional[Dict[str, Any]] = None,
    delay: float = 0.8,
    execute: bool = True
) -> Tuple[bool, str]:
    """
    Schedule a graceful server shutdown with an initial delay to allow
    the HTTP response to be flushed to the client.

    Args:
        context (dict, optional): Application context.
        delay (float): Seconds to delay before initiating shutdown.
        execute (bool): Whether to actually terminate the process (False for dry-run/testing).

    Returns:
        tuple: (success: bool, message: str)
    """
    if context is None:
        context = get_app_context()

    if not is_web_control_allowed(context):
        return False, "Server control via web interface is disabled in configuration"

    def _worker():
        time.sleep(max(0.1, delay))
        try:
            cleanup_app_resources(context)
        except Exception as e:
            Logger().error(f"Error during pre-shutdown cleanup: {e}")

        if execute:
            execute_process_shutdown()

    thread = threading.Thread(target=_worker, daemon=True, name="ServerShutdownWorker")
    thread.start()

    return True, "Server shutdown scheduled successfully"

