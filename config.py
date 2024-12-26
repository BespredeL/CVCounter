# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 19.11.2024
# Updated: 19.11.2024
# Website: https://bespredel.name

from system.config_manager import ConfigManager

config = ConfigManager("config.json")
config.read_config()
