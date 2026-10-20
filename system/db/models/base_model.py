# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declared_attr


class TablePrefixBase:
    __table_prefix__: str = ''

    @declared_attr
    def __tablename__(cls) -> str:
        """
        Get the table name.
        
        Args:
            None

        Returns:
            str: The table name
        """
        return cls.__table_prefix__ + cls.__name__.lower()

    @classmethod
    def set_table_prefix(cls, prefix: str) -> None:
        """
        Sets the prefix for all tables.
        
        Args:
            prefix (str): Table prefix
            
        Returns:
            None
        """
        cls.__table_prefix__ = prefix


# Define base class
Base = declarative_base(cls=TablePrefixBase)
