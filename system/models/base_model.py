# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 27.12.2024
# Updated: 31.03.2025
# Website: https://bespredel.name

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declared_attr


class TablePrefixBase:
    __table_prefix__: str = ''

    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__table_prefix__ + cls.__name__.lower()

    @classmethod
    def set_table_prefix(cls, prefix: str) -> None:
        """
        Sets the prefix for all tables.
        
        Args:
            prefix (str): Table prefix
        """
        cls.__table_prefix__ = prefix


# Define base class
Base = declarative_base(cls=TablePrefixBase)
