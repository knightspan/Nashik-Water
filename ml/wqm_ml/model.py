"""Loading the trained model and turning probabilities into the public verdict."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

CLASSES = ["Normal", "Natural change", "Contamination"]
COLOUR = {"Normal": "GREEN", "Natural change": "AMBER", "Contamination": "RED"}
EVENT_TO_CLASS = {0: "Normal", 1: "Natural change", 2: "Natural change", 4: "Contamination"}


def decide(proba: np.ndarray, classes: list[str], contam_threshold: float) -> tuple[np.ndarray, np.ndarray]:
    """Contamination if its probability ≥ threshold, otherwise the likelier of the other two.

    Returns (labels, confidence in %) where confidence is the chosen class's probability.
    """
    proba = np.atleast_2d(proba)
    ci = classes.index("Contamination")
    others = [i for i in range(len(classes)) if i != ci]
    best_other = np.array(others)[proba[:, others].argmax(axis=1)]
    choice = np.where(proba[:, ci] >= contam_threshold, ci, best_other)
    labels = np.array(classes)[choice]
    conf = proba[np.arange(len(proba)), choice] * 100.0
    return labels, conf


@dataclass
class WaterModel:
    estimator: Any
    features: list[str]
    classes: list[str]
    contam_threshold: float
    baselines: dict[str, dict[str, float]]
    meta: dict[str, Any]

    @classmethod
    def load(cls, model_dir: str | Path) -> WaterModel:
        model_dir = Path(model_dir)
        bundle = joblib.load(model_dir / "random_forest.joblib")
        meta = json.loads((model_dir / "meta.json").read_text(encoding="utf-8"))
        return cls(
            estimator=bundle["model"],
            features=bundle["features"],
            classes=list(bundle["model"].classes_),
            contam_threshold=float(bundle["contam_threshold"]),
            baselines=meta["site_baseline"],
            meta=meta,
        )

    def predict(self, x: pd.DataFrame) -> tuple[str, float]:
        proba = self.estimator.predict_proba(x[self.features])
        labels, conf = decide(proba, self.classes, self.contam_threshold)
        return str(labels[0]), float(conf[0])
