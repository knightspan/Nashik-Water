"""The 7 monitoring sites and their simulated behaviour.

Baselines come from the team's field tests (see WQM_code/pi/synth_water.py and the
project report). Replace NOISE with the standard deviations measured in experiment E2
(30 readings in the same water) once the probes are calibrated.
"""

from __future__ import annotations

from typing import Any

# Measurement noise of the low-cost probes (1-minute readings).
NOISE = {"ph": 0.02, "tds": 3.0, "turb": 0.5, "temp": 0.06}

# Accepted physical ranges (same as the web API).
RANGES = {"ph": (0.0, 14.0), "tds": (0.0, 2000.0), "turb": (0.0, 3000.0), "temp": (0.0, 50.0)}

# drift: slow natural wandering (pH units, fraction of TDS, log-turbidity)
# rain:  added turbidity (NTU), fractional TDS change, pH change at full intensity
# bathing: morning ritual bathing (turbidity NTU, TDS mg/L added)
SITES: dict[str, dict[str, Any]] = {
    "ugamsthan": dict(
        ph=7.3,
        tds=110,
        turb=3,
        temp=22.0,
        temp_amp=1.0,
        tau_h=12,
        drift=dict(ph=0.04, tds=0.04, turb=0.20),
        rain_per_day=0.20,
        rain=dict(turb=40, tds=-0.10, ph=-0.08),
        contam_per_day=0.02,
    ),
    "kushavart": dict(
        ph=7.6,
        tds=280,
        turb=10,
        temp=24.0,
        temp_amp=1.5,
        tau_h=10,
        drift=dict(ph=0.05, tds=0.05, turb=0.25),
        rain_per_day=0.20,
        rain=dict(turb=30, tds=-0.10, ph=-0.08),
        bathing=dict(turb=15, tds=40),
        contam_per_day=0.08,
    ),
    "gangapur_dam": dict(
        ph=7.6,
        tds=165,
        turb=5,
        temp=23.5,
        temp_amp=1.0,
        tau_h=12,
        drift=dict(ph=0.05, tds=0.04, turb=0.20),
        rain_per_day=0.20,
        rain=dict(turb=50, tds=-0.15, ph=-0.10),
        contam_per_day=0.03,
    ),
    "someshwar": dict(
        ph=7.7,
        tds=210,
        turb=9,
        temp=24.0,
        temp_amp=1.4,
        tau_h=8,
        drift=dict(ph=0.06, tds=0.05, turb=0.25),
        rain_per_day=0.20,
        rain=dict(turb=90, tds=-0.25, ph=-0.12),
        contam_per_day=0.05,
    ),
    "ramkund": dict(
        ph=7.8,
        tds=330,
        turb=15,
        temp=24.5,
        temp_amp=1.5,
        tau_h=8,
        drift=dict(ph=0.08, tds=0.06, turb=0.25),
        rain_per_day=0.20,
        rain=dict(turb=120, tds=-0.30, ph=-0.15),
        bathing=dict(turb=20, tds=50),
        contam_per_day=0.12,
    ),
    "tapovan": dict(
        ph=7.7,
        tds=420,
        turb=22,
        temp=25.0,
        temp_amp=1.5,
        tau_h=8,
        drift=dict(ph=0.08, tds=0.06, turb=0.25),
        rain_per_day=0.20,
        rain=dict(turb=120, tds=-0.30, ph=-0.15),
        contam_per_day=0.15,
    ),
    "nandini": dict(
        ph=7.3,
        tds=650,
        turb=35,
        temp=26.0,
        temp_amp=1.2,
        tau_h=6,
        drift=dict(ph=0.08, tds=0.07, turb=0.30),
        rain_per_day=0.20,
        rain=dict(turb=150, tds=-0.30, ph=-0.15),
        contam_per_day=0.20,
    ),
}
