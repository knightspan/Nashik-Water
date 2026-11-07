"""Fixed vocabularies shared by the database, the API schemas and the tests.

These strings are part of the data contract with the Raspberry Pi. Do not rename them.
"""

from __future__ import annotations

from enum import StrEnum


class Colour(StrEnum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    GREY = "GREY"


class Label(StrEnum):
    NORMAL = "Normal"
    NATURAL_CHANGE = "Natural change"
    CONTAMINATION = "Contamination"
    SENSOR_CHECK = "Sensor check"
    LEARNING_BASELINE = "Learning baseline"


class Health(StrEnum):
    OK = "ok"
    OFFLINE = "offline"
    FLATLINE = "flatline"
    OUT_OF_RANGE = "out_of_range"


class Role(StrEnum):
    ADMIN = "admin"
    VIEWER = "viewer"


# Physical ranges accepted on ingest (inclusive).
PARAM_RANGES: dict[str, tuple[float, float]] = {
    "ph": (0.0, 14.0),
    "tds": (0.0, 2000.0),
    "turb": (0.0, 3000.0),
    "temp": (0.0, 50.0),
}
