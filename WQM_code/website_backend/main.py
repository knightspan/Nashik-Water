"""main.py - back end of the public water-quality website (FastAPI + PostgreSQL).
Run locally:  uvicorn main:app --reload
Deploy:       Render / Railway web service; DATABASE_URL and INGEST_API_KEY set as environment variables.
Front end:    React + Vite app (Leaflet map, Chart.js) hosted on Vercel, calling these endpoints.
"""
import os
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime, ForeignKey, select
from sqlalchemy.orm import declarative_base, sessionmaker, Session

engine = create_engine(os.environ.get("DATABASE_URL", "sqlite:///./wqm.db"))
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
API_KEY = os.environ.get("INGEST_API_KEY", "change-me")


class Site(Base):
    __tablename__ = "sites"
    id = Column(String, primary_key=True)             # e.g. "ramkund"
    name = Column(String); kind = Column(String)
    lat = Column(Float); lon = Column(Float)
    simulated = Column(Boolean, default=False)


class Reading(Base):
    __tablename__ = "readings"
    id = Column(Integer, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id"), index=True)
    ts = Column(DateTime(timezone=True), index=True)
    ph = Column(Float); tds = Column(Float); turb = Column(Float); temp = Column(Float); wqi = Column(Float)
    label = Column(String); colour = Column(String); confidence = Column(Float)
    health = Column(String); synthetic = Column(Boolean)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    site_id = Column(String, ForeignKey("sites.id")); ts = Column(DateTime(timezone=True))
    label = Column(String); confidence = Column(Float); wqi = Column(Float)


Base.metadata.create_all(engine)
app = FastAPI(title="Smart Water Quality Monitoring API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


def db():
    s = SessionLocal()
    try: yield s
    finally: s.close()


class StatusIn(BaseModel):
    source: str; colour: str; label: str; confidence: float; wqi: float
    ph: float; tds: float; turb: float; temp: float; health: str; synthetic: bool = False


@app.post("/api/ingest")
def ingest(r: StatusIn, x_api_key: str = Header(""), s: Session = Depends(db)):
    if x_api_key != API_KEY: raise HTTPException(401, "invalid API key")
    now = datetime.now(timezone.utc)
    s.add(Reading(site_id=r.source, ts=now, **r.model_dump(exclude={"source"})))
    if r.colour == "RED": s.add(Alert(site_id=r.source, ts=now, label=r.label, confidence=r.confidence, wqi=r.wqi))
    s.commit(); return {"ok": True}


@app.get("/api/sources")
def sources(s: Session = Depends(db)):
    out = []
    for site in s.scalars(select(Site)):
        last = s.scalars(select(Reading).where(Reading.site_id == site.id).order_by(Reading.ts.desc()).limit(1)).first()
        out.append({"id": site.id, "name": site.name, "kind": site.kind, "lat": site.lat, "lon": site.lon,
                    "simulated": site.simulated, "latest": None if not last else
                    {k: getattr(last, k) for k in ("ts", "ph", "tds", "turb", "temp", "wqi", "label", "colour", "confidence", "health")}})
    return out


@app.get("/api/sources/{site_id}/readings")
def readings(site_id: str, hours: int = 24, s: Session = Depends(db)):
    since = datetime.now(timezone.utc) - timedelta(hours=min(hours, 24 * 30))
    q = select(Reading).where(Reading.site_id == site_id, Reading.ts >= since).order_by(Reading.ts)
    return [{k: getattr(r, k) for k in ("ts", "ph", "tds", "turb", "temp", "wqi", "colour")} for r in s.scalars(q)]


@app.get("/api/alerts")
def alerts(limit: int = 50, s: Session = Depends(db)):
    q = select(Alert).order_by(Alert.ts.desc()).limit(limit)
    return [{"site": a.site_id, "ts": a.ts, "label": a.label, "confidence": a.confidence, "wqi": a.wqi} for a in s.scalars(q)]
