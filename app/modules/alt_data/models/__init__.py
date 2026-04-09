"""Alt data models package."""

from app.modules.alt_data.models.alt_data_feed import AltDataFeedRecord
from app.modules.alt_data.models.alt_data_point import AltDataPointRecord
from app.shared.models import Base as Base

__all__ = [
    "AltDataFeedRecord",
    "AltDataPointRecord",
]
