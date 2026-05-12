"""skillify scripts — Python implementations of the meta-skill audit + scaffold + eval pipeline."""

import warnings

__version__ = "0.1.0"

from . import aggregator
warnings.filterwarnings(
    "ignore",
    message=r"'scripts\.check_resolvable' found in sys\.modules after import of package 'scripts'",
    category=RuntimeWarning,
)
from . import check_resolvable
from . import receipt
from . import slots

__all__ = ["aggregator", "check_resolvable", "receipt", "slots"]
