# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 22.01.2026
# Website: https://bespredel.name

import os
import signal
import sys
from threading import Lock

from flask import Flask
from flask_httpauth import HTTPBasicAuth
from flask_socketio import SocketIO

from system.managers.config_manager import init_config
from system.managers.database_manager import DatabaseManager
from system.core.object_counter import ObjectCounter
from system.managers.thread_manager import ThreadManager
from system.utils.utils import slug, system_check, trans as translate
from system.db.models.base_model import TablePrefixBase
from routes import counters_bp, reports_bp, settings_bp, main_bp


# --------------------------------------------------------------------------------
# Application Factory
# --------------------------------------------------------------------------------

def create_app(config_path: str = "config.json", test_config: dict = None):
    """
    Application factory function.
    
    Creates and configures the Flask application instance.
    
    Args:
        config_path (str): Path to configuration file. Defaults to "config.json".
        test_config (dict): Optional test configuration to override defaults.
    
    Returns:
        tuple: (Flask app instance, SocketIO instance, application context dict)
    """

    # Init config
    _config = init_config(config_path)

    # System check
    if _config.get("general.system_check", False):
        system_check()

    # Generate and save secret key if not set
    if not _config.get("server.secret_key"):
        secret_key = os.urandom(40).hex()
        _config.set("server.secret_key", secret_key)
        _config.save_config()

    # General settings
    locations = list(_config.get("detections", {}).keys())
    locations_dict = dict([(k, v['label']) for k, v in _config.get("detections", {}).items()])

    # Start Flask
    _app = Flask(__name__)

    # Apply test config if provided
    if test_config:
        _app.config.update(test_config)
    else:
        # Config Flask
        _app.config['SECRET_KEY'] = _config.get("server.secret_key")
        _app.config["TEMPLATES_AUTO_RELOAD"] = True

    # Configure Socket.IO
    allowed_origins = _config.get("server.allowed_origins", ["http://localhost:8080"])
    _socketio = SocketIO(_app, async_mode="threading", cors_allowed_origins=allowed_origins)

    # Auth
    _auth = HTTPBasicAuth()
    users = _config.get("users", {})

    # Set table prefix
    TablePrefixBase.set_table_prefix(_config.get("db.prefix", ""))

    # Start DB
    db_uri = _config.get("db.uri") or "sqlite:///:memory:"
    _db_manager = DatabaseManager(uri=db_uri, prefix=_config.get("db.prefix"))

    # Init objects
    _object_counters: dict[str, ObjectCounter] = {}
    _thread_manager: ThreadManager = ThreadManager()
    _lock: Lock = Lock()

    # Store in application context (accessible via current_app.config['APP_CONTEXT'])
    app_context = {
        'config': _config,
        'locations': locations,
        'locations_dict': locations_dict,
        'db_manager': _db_manager,
        'object_counters': _object_counters,
        'thread_manager': _thread_manager,
        'lock': _lock,
        'auth': _auth,
        'users': users,
        'socketio': _socketio
    }

    # Store app_context in app config for access in blueprints
    _app.config['APP_CONTEXT'] = app_context

    # Register template filters and globals
    register_template_helpers(_app, app_context)

    # Setup authentication
    setup_authentication(app_context)

    # Register blueprints
    register_blueprints(_app)

    # Register signal handlers
    register_signal_handlers(app_context)

    return _app, _socketio, app_context


def register_template_helpers(app: Flask, context: dict):
    """
    Register template filters and globals.

    Args:
        app (Flask): Flask application instance
        context (dict): Application context dictionary

    Returns:
        None
    """

    config = context['config']
    thread_manager = context['thread_manager']
    object_counters = context['object_counters']

    @app.template_filter('slug')
    def _slug(string: str) -> str:
        """
        Convert a string to a URL-friendly slug.

        Args:
            string (str): Input string

        Returns:
            str: URL-friendly slug
        """
        if not string:
            return ""
        return slug(string)

    @app.template_global()
    def trans(string: str, **kwargs: dict) -> str:
        """
        Translate a string using the configured language.

        Args:
            string (str): Input string
            **kwargs (dict): Additional keyword arguments

        Returns:
            str: Translated string
        """
        if kwargs.get('lang') is None:
            kwargs['lang'] = config.get('general.default_language', 'ru')
        return translate(string, **kwargs)

    @app.template_global()
    def counter_status(key: str) -> str:
        """
        Get the current status of a counter.

        Args:
            key (str): Counter key

        Returns:
            str: Counter status
        """
        if key not in thread_manager.threads:
            return 'stopped'
        if key not in object_counters:
            return 'stopped'
        if object_counters[key].is_pause():
            return 'paused'
        return 'running'

    @app.template_global()
    def counter_status_class(key: str) -> str:
        """
        Get the CSS class for a counter's status.

        Args:
            key (str): Counter key

        Returns:
            str: CSS class
        """
        if key not in thread_manager.threads:
            return 'secondary'
        if key not in object_counters:
            return 'secondary'
        if object_counters[key].is_pause():
            return 'warning'
        return 'success'

    @app.context_processor
    def utility_processor() -> dict:
        """
        Add global variables to all template contexts.

        Returns:
            dict: Global variables
        """
        return dict(config=config)


def setup_authentication(context: dict):
    """
    Setup authentication for the application.
    
    Args:
        context (dict): Application context dictionary
    
    Returns:
        None
    """
    from system.auth import setup_auth
    setup_auth()


def register_blueprints(app: Flask):
    """
    Register all application blueprints.

    Args:
        app (Flask): Flask application instance

    Returns:
        None
    """
    app.register_blueprint(main_bp)
    app.register_blueprint(counters_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)


def register_signal_handlers(context: dict):
    """
    Register signal handlers for shutdown.
    """

    thread_manager = context['thread_manager']
    object_counters = context['object_counters']
    lock = context['lock']
    db_manager = context['db_manager']

    def shutdown_handler(signum=None, frame=None):
        """
        Shutdown handler for the application.

        Args:
            signum (int): Signal number.
            frame (frame): Current stack frame.
        """
        from system.utils.logger import Logger
        logger = Logger()

        logger.info("Received shutdown signal. Starting shutdown...")

        # Stop all threads and object counters
        try:
            with lock:
                counters_copy = object_counters.copy()

            if counters_copy:
                logger.info(f"Stopping {len(counters_copy)} object counter(s)...")
                results = thread_manager.stop_all_threads(counters_copy)

                # Cleanup any remaining counters
                for location, counter in counters_copy.items():
                    if location not in results or not results[location]:
                        try:
                            logger.info(f"Force cleanup for location: {location}")
                            counter.cleanup()
                        except Exception as e:
                            logger.error(f"Error during force cleanup for {location}: {e}")

                with lock:
                    object_counters.clear()
        except Exception as e:
            logger.error(f"Error during thread shutdown: {e}")

        # Close database connections
        try:
            if db_manager:
                logger.info("Closing database connections...")
                db_manager.close()
        except Exception as e:
            logger.error(f"Error closing database: {e}")

        logger.info("Graceful shutdown completed.")
        sys.exit(0)

    # Register signal handlers
    try:
        signal.signal(signal.SIGTERM, shutdown_handler)
    except (ValueError, OSError):
        # SIGTERM is not available on Windows
        pass

    try:
        signal.signal(signal.SIGINT, shutdown_handler)
    except (ValueError, OSError):
        # This should not happen, but need try handle it this shit
        pass


# --------------------------------------------------------------------------------
# Create application instance for Flask CLI compatibility
# --------------------------------------------------------------------------------
_app_instance = create_app()
app = _app_instance[0]  # Flask app instance
socketio = _app_instance[1]  # SocketIO instance
app_context = _app_instance[2]  # Application context

# Make app_context available globally for backward compatibility if needed
config = app_context['config']

# --------------------------------------------------------------------------------
# Server run
# --------------------------------------------------------------------------------

if __name__ == '__main__':
    """
    Main entry point for the application.
    Starts the Flask server with configured settings.
    """
    try:
        socketio.run(
            app,
            host=config.get('server.host'),
            port=config.get('server.port', 8080),
            debug=config.get('general.debug', False),
            log_output=config.get('server.log_output', True),
            use_reloader=config.get('server.use_reloader', False),
            allow_unsafe_werkzeug=config.get('general.allow_unsafe_werkzeug', config.get('general.debug', False))
        )
    except KeyboardInterrupt:
        from system.utils.logger import Logger

        logger = Logger()
        logger.info("Received KeyboardInterrupt. Shutting down...")
        sys.exit(0)
    except Exception as e:
        from system.utils.logger import Logger

        logger = Logger()
        logger.error(f"Fatal error in main: {e}")
        raise
