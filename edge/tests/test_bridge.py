"""serial_bridge.py: parsing the Arduino's lines and building the website record."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from serial_bridge import Window, parse_line, verdict  # noqa: E402


def test_parses_ph_sample_sketch_line() -> None:
    assert parse_line("Voltage:2.06    pH value: 7.22\r\n") == {"ph": 7.22}
    assert parse_line("Voltage:2.06") == {}
    assert parse_line("") == {}


def test_parses_node_firmware_json() -> None:
    line = '{"node":"node_01","ph":7.82,"tds":331.4,"turb":15.2,"temp":24.56,"temp_ok":1,"edge_state":0}'
    assert parse_line(line) == {"ph": 7.82, "tds": 331.4, "turb": 15.2, "temp": 24.56}
    assert "temp" not in parse_line('{"ph":7.1,"temp":85.0,"temp_ok":0}')
    assert parse_line("{not json") == {}


def test_verdict_rule_never_red() -> None:
    assert verdict({"ph": 7.22}) == ("GREEN", "Normal", "ok")
    assert verdict({"ph": 6.1}) == ("AMBER", "Natural change", "ok")
    assert verdict({"ph": 9.0})[0] == "AMBER"
    assert verdict({"ph": 13.5}) == ("GREY", "Sensor check", "out_of_range")
    assert verdict({"ph": None}) == ("GREY", "Sensor check", "offline")


def test_window_record_is_median_and_matches_contract() -> None:
    w = Window()
    for v in (7.22, 7.23, 7.22, 9.9, 7.24):  # one spike, removed by the median
        w.add({"ph": v})
    rec = w.record("ramkund", datetime(2026, 11, 7, 6, 0, tzinfo=UTC))
    assert rec is not None
    assert rec["ph"] == 7.23
    assert rec["tds"] is None and rec["wqi"] is None
    assert (rec["source"], rec["colour"], rec["label"], rec["health"]) == ("ramkund", "GREEN", "Normal", "ok")
    assert rec["synthetic"] is False
    assert rec["ts"] == "2026-11-07T06:00:00+00:00"
    assert Window().record("ramkund", datetime.now(UTC)) is None


def test_full_node_record_has_wqi() -> None:
    w = Window()
    w.add({"ph": 7.81, "tds": 331.2, "turb": 17.8, "temp": 24.6})
    rec = w.record("ramkund", datetime.now(UTC))
    assert rec is not None and 240 < rec["wqi"] < 246
