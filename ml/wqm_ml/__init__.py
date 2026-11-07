"""Water-quality ML pipeline shared by training (ml/) and the Raspberry Pi service (edge/).

Everything the Pi computes at run time (5-minute windows, features, WQI, sensor health)
lives here, so a model trained with this package sees exactly the same features live.
"""

__version__ = "1.0.0"
