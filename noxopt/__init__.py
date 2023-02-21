from __future__ import annotations

import sys

from nox.sessions import Session

from noxopt._option import Option
from noxopt.noxopt import NoxOpt


if sys.version_info < (3, 10):  # pragma: no cover
    from typing_extensions import Annotated
else:
    from typing import Annotated

if sys.version_info < (3, 8):  # pragma: no cover
    from importlib_metadata import version as _version
else:
    from importlib.metadata import version as _version

__version__ = _version(__name__)
__all__ = ["NoxOpt", "Option", "Session", "Annotated"]
