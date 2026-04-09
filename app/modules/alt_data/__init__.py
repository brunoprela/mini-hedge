"""Alternative data bounded context — sentiment, web traffic, and non-traditional data."""

from app.modules.alt_data.interface import (
    AltDataFeed,
    AltDataPoint,
    AltDataSource,
    AltDataSummary,
)
from app.modules.alt_data.service import AltDataService

__all__ = [
    "AltDataFeed",
    "AltDataPoint",
    "AltDataService",
    "AltDataSource",
    "AltDataSummary",
]
