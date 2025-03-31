# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 19.11.2024
# Updated: 19.11.2024
# Website: https://bespredel.name

from system.config_manager import ConfigManager

config = None

def init_config(config_path: str = "config.json") -> ConfigManager:
    """
    Initializes the global configuration instance.
    
    Args:
        config_path (str): Path to the configuration file
        
    Returns:
        ConfigManager: Configuration instance
    """
    global config
    if config is None:
        config = ConfigManager(config_path)
        config.read_config()
    return config 