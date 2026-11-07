"""The Pi must compute exactly what training computed."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wqm_ml.features import (
    FEATURES,
    MIN_HISTORY,
    PARAMS,
    add_features,
    aggregate_window,
    latest_features,
    site_baseline,
    to_windows,
)
from wqm_ml.health import health_series, sensor_health
from wqm_ml.model import decide
from wqm_ml.synth import generate
from wqm_ml.wqi import WEIGHTS, wqi


def test_wqi_matches_backend_formula() -> None:
    assert round(WEIGHTS["ph"], 3) == 0.368
    assert round(WEIGHTS["tds"], 3) == 0.006
    assert round(WEIGHTS["turb"], 3) == 0.626
    assert wqi(8.5, 500, 5) == pytest.approx(100)
    assert wqi(6.5, 0, 0) == pytest.approx(100 * WEIGHTS["ph"])


@pytest.fixture(scope="module")
def site() -> pd.DataFrame:
    df = generate(days=2, seed=5, faults=False)
    return df[df.source == "ramkund"].reset_index(drop=True)


def test_window_median_matches_batch_resample(site: pd.DataFrame) -> None:
    w = to_windows(site[["ts", *PARAMS]])
    first = site.iloc[:5][PARAMS].to_numpy()
    np.testing.assert_allclose(aggregate_window(first), w.iloc[0][PARAMS].to_numpy(dtype=float))


def test_window_needs_three_valid_readings() -> None:
    rows = np.array([[7.0, 100, 1, 25], [np.nan] * 4, [np.nan] * 4, [7.2, 110, 2, 25], [np.nan] * 4])
    assert np.isnan(aggregate_window(rows)).all()


def test_streaming_features_equal_batch_features(site: pd.DataFrame) -> None:
    """latest_features() on a growing history == add_features() on the whole series."""
    w = to_windows(site[["ts", *PARAMS]])
    b = site_baseline(w)
    batch = add_features(w, b)
    for i in (MIN_HISTORY + 5, MIN_HISTORY + 100, len(w) - 1):
        live = latest_features(w.iloc[: i + 1][["ts", *PARAMS]], b)
        assert live is not None
        np.testing.assert_allclose(
            live[FEATURES].to_numpy()[0], batch.iloc[i][FEATURES].to_numpy(dtype=float), rtol=1e-9
        )


def test_not_enough_history_returns_none(site: pd.DataFrame) -> None:
    w = to_windows(site[["ts", *PARAMS]])
    assert latest_features(w.iloc[: MIN_HISTORY - 1], site_baseline(w)) is None


def test_health_rules_scalar_equals_vectorised() -> None:
    df = generate(days=1, seed=7, faults=True)
    g = df[df.source == "tapovan"].reset_index(drop=True)
    vec = health_series(g)
    for i in range(40, len(g), 37):
        assert sensor_health(g.iloc[max(0, i - 59) : i + 1]) == vec[i], i


def test_health_cases() -> None:
    ok = pd.DataFrame(
        {"ph": 7.5 + np.random.default_rng(1).normal(0, 0.02, 40), "tds": 300.0, "turb": 10.0, "temp": 24.0}
    )
    ok["tds"] += np.arange(40) * 0.1
    ok["turb"] += np.arange(40) * 0.01
    assert sensor_health(ok) == "ok"
    stuck = ok.copy()
    stuck["tds"] = 312.0
    assert sensor_health(stuck) == "flatline"
    clear = ok.copy()
    clear["turb"] = 0.0  # RO water reads 0 NTU: not a fault
    assert sensor_health(clear) == "ok"
    dry = ok.copy()
    dry.loc[dry.index[-1], "ph"] = 13.5
    assert sensor_health(dry) == "out_of_range"
    gone = ok.copy()
    gone.iloc[-4:] = np.nan
    assert sensor_health(gone) == "offline"
    assert sensor_health([]) == "offline"


def test_decide_threshold() -> None:
    classes = ["Contamination", "Natural change", "Normal"]
    proba = np.array([[0.3, 0.2, 0.5], [0.1, 0.6, 0.3]])
    labels, conf = decide(proba, classes, 0.25)
    assert list(labels) == ["Contamination", "Natural change"]
    assert conf.tolist() == pytest.approx([30.0, 60.0])
