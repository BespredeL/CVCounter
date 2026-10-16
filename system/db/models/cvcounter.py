# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 27.12.2024
# Updated: 28.04.2025
# Website: https://bespredel.name

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from system.db.models.base_model import Base


class CVCounter(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    active = Column(Boolean, default=True, index=True)
    location = Column(String(255), nullable=False, index=True)
    total_count = Column(Integer, default=0)
    source_count = Column(Integer, default=0)
    defects_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    parts = Column(Text, nullable=True)
    custom_fields = Column(Text, nullable=True)
    class_counts = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_cvcounter_loc_created', 'location', 'created_at'),
        Index('ix_cvcounter_loc_active', 'location', 'active'),
    )
