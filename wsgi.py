# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""WSGI entry point for a production server: gunicorn -w 1 -b 0.0.0.0:80 wsgi:application."""

from system.app_factory import create_app

application, socketio, app_context = create_app()
