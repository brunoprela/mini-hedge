"""Fee accounting models package."""

from app.modules.fee_accounting.models.fee_accrual import FeeAccrualRecord
from app.modules.fee_accounting.models.fee_schedule import FeeScheduleRecord
from app.modules.fee_accounting.models.high_water_mark import HighWaterMarkRecord
from app.shared.models import Base as Base

__all__ = [
    "FeeAccrualRecord",
    "FeeScheduleRecord",
    "HighWaterMarkRecord",
]
