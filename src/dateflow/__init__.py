"""dateflow — A zero-dependency, modern Python replacement for python-dateutil."""

__version__ = "0.1.0"

from dateflow.relativedelta import (
    MO,
    TU,
    WE,
    TH,
    FR,
    SA,
    SU,
    relativedelta,
    weekday,
)
from dateflow.easter import easter

__all__ = [
    "relativedelta",
    "weekday",
    "MO",
    "TU",
    "WE",
    "TH",
    "FR",
    "SA",
    "SU",
    "easter",
]
