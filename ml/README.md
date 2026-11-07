# wqm_ml — water-state model

Shared by training (here) and the Raspberry Pi service (`edge/`).

```bash
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-train.txt -e .
python -m wqm_ml.train                              # ~1 min: models/ + reports/REPORT.md
pytest
```

| File | Purpose |
|---|---|
| `wqm_ml/sites.py` | the 7 sites' baselines and event rates (from the field tests) |
| `wqm_ml/synth.py` | labelled 1-minute synthetic telemetry with events and sensor faults |
| `wqm_ml/features.py` | 5-minute windows and the 24 causal features (identical on the Pi) |
| `wqm_ml/health.py` | sensor-health rules: offline / flatline / out_of_range |
| `wqm_ml/model.py` | loading the model and the thresholded decision |
| `wqm_ml/train.py` | train / validate / test, model comparison, Arduino tree export, report |
| `models/` | `random_forest.joblib`, `meta.json`, `WaterStateTree.h`, `SiteBaseline.h` |
| `reports/` | `REPORT.md`, `metrics.json`, figures |

Results: [reports/REPORT.md](reports/REPORT.md).
