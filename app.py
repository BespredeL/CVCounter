# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Entry point: builds the app through system.app_factory and runs the server."""

import os
import sys

import system.utils.ultralytics_home

try:
    import colorama
    colorama.init()
except Exception:
    if os.name == 'nt':
        os.system('')

from system.app_factory import create_app

# --------------------------------------------------------------------------------
# Server run
# --------------------------------------------------------------------------------

def main():
    """
    Main entry point for the application.
    Builds the app through system.app_factory and starts the server with configured settings.
    """
    app, socketio, app_context = create_app()
    config = app_context['config']
    try:
        server_host = config.get('server.host', '0.0.0.0')
        server_port = int(config.get('server.port', 8080))
        local_host = '127.0.0.1' if server_host in ('0.0.0.0', '', '::') else server_host
        port_suffix = f":{server_port}" if server_port != 80 else ""

        print("\n" + "=" * 68)
        print("                 CVCounter Server Running")
        print("=" * 68)
        print(f"  * Web interface: http://{local_host}{port_suffix}")
        if server_host in ('0.0.0.0', ''):
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                lan_ip = s.getsockname()[0]
                s.close()
                if lan_ip and lan_ip != local_host:
                    print(f"  * Network access: http://{lan_ip}{port_suffix}")
            except Exception:
                pass
        print("  * Press Ctrl+C to stop the server")
        print("=" * 68 + "\n", flush=True)

        socketio.run(
            app,
            host=server_host,
            port=server_port,
            debug=config.get('general.debug', False),
            log_output=config.get('server.log_output', True),
            use_reloader=config.get('server.use_reloader', False),
            allow_unsafe_werkzeug=config.get('general.allow_unsafe_werkzeug', True)
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
        logger.log_exception()
        # Telemetry may have never been configured here, so report the crash directly and flush it
        try:
            from system.utils.telemetry import get_telemetry

            telemetry = get_telemetry()
            telemetry.capture_startup_failure(e)
            telemetry.shutdown(timeout=3.0)
        except Exception:
            pass
        raise


if __name__ == '__main__':
    main()
