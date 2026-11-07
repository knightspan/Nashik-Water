"""Time series with automatic downsampling, statistics and CSV rows."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, literal, literal_column, select
from sqlalchemy.orm import Session

from app.domain import Colour
from app.models import Reading, ReadingHourly
from app.schemas import ParamStats, SeriesOut, SeriesPoint, StatsOut
from app.wqi import BAND_NAMES, BANDS

PARAMS = ("ph", "tds", "turb", "temp", "wqi")
SEVERITY = {Colour.GREEN.value: 0, Colour.GREY.value: 1, Colour.AMBER.value: 2, Colour.RED.value: 3}
BY_SEVERITY = {v: k for k, v in SEVERITY.items()}
EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


def resolution_for(hours: int) -> str:
    if hours <= 24:
        return "raw"
    if hours <= 24 * 7:
        return "15min"
    return "1h"


def _severity_expr():  # type: ignore[no-untyped-def]
    return func.max(
        case(
            (Reading.colour == Colour.RED.value, 3),
            (Reading.colour == Colour.AMBER.value, 2),
            (Reading.colour == Colour.GREY.value, 1),
            else_=0,
        )
    )


def _bucketed(db: Session, site_id: str, since: datetime, stride: str) -> list[SeriesPoint]:
    bucket = func.date_bin(literal_column(f"INTERVAL '{stride}'"), Reading.ts, literal(EPOCH))
    stmt = (
        select(
            bucket.label("bucket"),
            *[func.avg(getattr(Reading, p)).label(p) for p in PARAMS],
            _severity_expr().label("sev"),
            func.count().label("n"),
        )
        .where(Reading.site_id == site_id, Reading.ts >= since)
        .group_by("bucket")
        .order_by("bucket")
    )
    return [
        SeriesPoint(
            ts=r.bucket,
            **{p: _round(getattr(r, p)) for p in PARAMS},
            colour=BY_SEVERITY[r.sev],
            n=r.n,
        )
        for r in db.execute(stmt)
    ]


def _hourly_archive(
    db: Session, site_id: str, since: datetime, until: datetime
) -> list[SeriesPoint]:
    stmt = (
        select(ReadingHourly)
        .where(
            ReadingHourly.site_id == site_id,
            ReadingHourly.hour >= since,
            ReadingHourly.hour < until,
        )
        .order_by(ReadingHourly.hour)
    )
    points = []
    for h in db.scalars(stmt):
        colour = "RED" if h.n_red else "AMBER" if h.n_amber else "GREY" if h.n_grey else "GREEN"
        points.append(
            SeriesPoint(
                ts=h.hour,
                ph=_round(h.ph_mean),
                tds=_round(h.tds_mean),
                turb=_round(h.turb_mean),
                temp=_round(h.temp_mean),
                wqi=_round(h.wqi_mean),
                colour=colour,
                n=h.n,
            )
        )
    return points


def series(db: Session, site_id: str, hours: int) -> SeriesOut:
    since = datetime.now(UTC) - timedelta(hours=hours)
    res = resolution_for(hours)
    if res == "raw":
        stmt = (
            select(Reading)
            .where(Reading.site_id == site_id, Reading.ts >= since)
            .order_by(Reading.ts)
        )
        points = [
            SeriesPoint(ts=r.ts, **{p: getattr(r, p) for p in PARAMS}, colour=r.colour)
            for r in db.scalars(stmt)
        ]
    elif res == "15min":
        points = _bucketed(db, site_id, since, "15 minutes")
    else:
        points = _bucketed(db, site_id, since, "1 hour")
        # Raw rows older than the retention period are gone; fill in from the archive.
        first = points[0].ts if points else datetime.now(UTC)
        points = _hourly_archive(db, site_id, since, first) + points
    return SeriesOut(site_id=site_id, hours=hours, resolution=res, points=points)  # type: ignore[arg-type]


def _round(v: float | None, nd: int = 3) -> float | None:
    return None if v is None else round(float(v), nd)


def stats(db: Session, site_id: str, days: int) -> StatsOut:
    since = datetime.now(UTC) - timedelta(days=days)
    where = (Reading.site_id == site_id, Reading.ts >= since)

    cols = []
    for p in PARAMS:
        c = getattr(Reading, p)
        cols += [
            func.min(c).label(f"{p}_min"),
            func.max(c).label(f"{p}_max"),
            func.avg(c).label(f"{p}_mean"),
            func.percentile_cont(0.5).within_group(c).label(f"{p}_median"),
        ]
    row = db.execute(select(func.count().label("n"), *cols).where(*where)).one()
    n = int(row.n)
    params = {
        p: ParamStats(
            **{m: _round(getattr(row, f"{p}_{m}")) for m in ("min", "max", "mean", "median")}
        )
        for p in PARAMS
    }

    band_case = case(
        *[(Reading.wqi <= upper, literal(name)) for name, upper in BANDS],
        else_=literal("unfit"),
    )
    band_rows = db.execute(
        select(band_case.label("band"), func.count())
        .where(*where, Reading.wqi.is_not(None))
        .group_by("band")
    ).all()
    band_total = sum(c for _, c in band_rows) or 1
    bands = {b: 0.0 for b in BAND_NAMES}
    for b, c in band_rows:
        bands[b] = round(100.0 * c / band_total, 1)

    colour_rows = db.execute(
        select(Reading.colour, func.count()).where(*where).group_by(Reading.colour)
    ).all()
    colours = {c.value: 0.0 for c in Colour}
    for colour, c in colour_rows:
        colours[colour] = round(100.0 * c / (n or 1), 1)

    return StatsOut(
        site_id=site_id, days=days, count=n, params=params, wqi_bands=bands, colours=colours
    )


CSV_COLUMNS = [
    "ts",
    "site_id",
    "ph",
    "tds",
    "turb",
    "temp",
    "wqi",
    "label",
    "colour",
    "confidence",
    "health",
    "synthetic",
]


def csv_rows(db: Session, site_id: str, days: int) -> Iterator[list[object]]:
    since = datetime.now(UTC) - timedelta(days=days)
    stmt = (
        select(Reading)
        .where(Reading.site_id == site_id, Reading.ts >= since)
        .order_by(Reading.ts)
        .execution_options(yield_per=1000)
    )
    for r in db.scalars(stmt):
        yield [
            r.ts.isoformat(),
            r.site_id,
            r.ph,
            r.tds,
            r.turb,
            r.temp,
            r.wqi,
            r.label,
            r.colour,
            r.confidence,
            r.health,
            r.synthetic,
        ]
