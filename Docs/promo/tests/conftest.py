"""Put `Docs/promo/` on the import path so the promo modules import by name.

The promo builder is a set of flat scripts (run as `python Docs/promo/build_promo.py`),
not an installed package, so the tests mirror that import style.
"""

import sys
from pathlib import Path

PROMO_DIR = Path(__file__).resolve().parents[1]
if str(PROMO_DIR) not in sys.path:
    sys.path.insert(0, str(PROMO_DIR))
