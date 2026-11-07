import pytest

from app.wqi import WEIGHTS, compute_wqi, q_ph, wqi_band


def test_weights_match_spec() -> None:
    assert round(WEIGHTS["ph"], 3) == 0.368
    assert round(WEIGHTS["tds"], 3) == 0.006
    assert round(WEIGHTS["turb"], 3) == 0.626
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "ph,expected",
    [(7.0, 0.0), (8.5, 100.0), (7.75, 50.0), (6.5, 100.0), (6.75, 50.0), (5.0, 400.0)],
)
def test_ph_quality_rating(ph: float, expected: float) -> None:
    assert q_ph(ph) == pytest.approx(expected)


def test_wqi_at_limits_is_100() -> None:
    # Every parameter exactly at its BIS limit -> each Q = 100 -> WQI = 100.
    assert compute_wqi(8.5, 500, 5) == pytest.approx(100.0)
    assert compute_wqi(7.0, 0, 0) == pytest.approx(0.0)


def test_wqi_example_reading() -> None:
    # Ramkund-like water: turbidity dominates the index.
    w = compute_wqi(7.81, 331.2, 17.8)
    assert 240 < w < 246


@pytest.mark.parametrize(
    "w,band",
    [
        (None, None),
        (0, "excellent"),
        (25, "excellent"),
        (25.1, "good"),
        (50, "good"),
        (75, "poor"),
        (100, "very_poor"),
        (100.01, "unfit"),
        (900, "unfit"),
    ],
)
def test_bands(w: float | None, band: str | None) -> None:
    assert wqi_band(w) == band
