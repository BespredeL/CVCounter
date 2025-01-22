# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 27.12.2024
# Updated: 27.12.2024
# Website: https://bespredel.name

from config import config
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declared_attr


class TablePrefixBase:
    __table_prefix__: str = config.get('db.prefix', '')

    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__table_prefix__ + cls.__name__.lower()


# Defining the base class
Base = declarative_base(cls=TablePrefixBase)
