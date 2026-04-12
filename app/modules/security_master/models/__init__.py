"""Security master models package."""

from app.modules.security_master.models.equity_extension import EquityExtensionRecord
from app.modules.security_master.models.fixed_income_extension import FixedIncomeExtensionRecord
from app.modules.security_master.models.future_extension import FutureExtensionRecord
from app.modules.security_master.models.fx_extension import FXExtensionRecord
from app.modules.security_master.models.identifier import IdentifierType, InstrumentIdentifierRecord
from app.modules.security_master.models.instrument import InstrumentRecord
from app.modules.security_master.models.option_extension import OptionExtensionRecord
from app.modules.security_master.models.swap_extension import SwapExtensionRecord
from app.shared.models import Base as Base

__all__ = [
    "EquityExtensionRecord",
    "FXExtensionRecord",
    "FixedIncomeExtensionRecord",
    "FutureExtensionRecord",
    "IdentifierType",
    "InstrumentIdentifierRecord",
    "InstrumentRecord",
    "OptionExtensionRecord",
    "SwapExtensionRecord",
]
