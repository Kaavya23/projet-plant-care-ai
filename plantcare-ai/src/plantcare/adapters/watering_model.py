"""
Option C — adaptateur d'inférence du modèle d'arrosage.

Charge le RandomForest sérialisé par ml/train_watering.py et expose une
prédiction typée (verdict + confiance + explication basée sur les features
les plus déterminantes). Si l'artefact est absent, un repli par règle simple
permet à l'API de démarrer quand même (utile en CI / démo à froid).
"""
from __future__ import annotations

import json
from pathlib import Path

from plantcare.domain.entities import (MesureCapteur, Plante, Espece,
                                       RecommandationArrosage, Verdict)

ARTIFACTS = Path("ml/artifacts")


class WateringModel:
    def __init__(self, artifacts_dir: Path = ARTIFACTS):
        self.model = None
        self.meta = {}
        model_path = artifacts_dir / "watering_rf.joblib"
        meta_path = artifacts_dir / "watering_meta.json"
        if model_path.exists() and meta_path.exists():
            import joblib
            self.model = joblib.load(model_path)
            self.meta = json.loads(meta_path.read_text())

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def predire(self, plante: Plante, espece: Espece,
                mesure: MesureCapteur, jours_dernier_arrosage: int = 3
                ) -> RecommandationArrosage:
        if not self.is_loaded:
            return self._repli_regle(espece, mesure)

        import pandas as pd
        features = self.meta["features"]
        vecteur = {
            "espece_id": espece.id, "taille_pot": plante.taille_pot,
            "sol": mesure.sol, "temperature": mesure.temperature,
            "lux": mesure.lux, "humidite_air": mesure.humidite_air,
            "seuil_sol_sec": espece.seuil_sol_sec,
            "jours_dernier_arrosage": jours_dernier_arrosage,
        }
        X = pd.DataFrame([[vecteur[f] for f in features]], columns=features)
        proba = self.model.predict_proba(X)[0]
        idx = int(proba.argmax())
        verdict = str(self.model.classes_[idx])
        top = [t[0] for t in self.meta.get("importances", [])[:3]]
        return RecommandationArrosage(
            verdict=Verdict(verdict), confiance=float(proba[idx]),
            explication="Facteurs déterminants : " + ", ".join(top))

    @staticmethod
    def _repli_regle(espece: Espece, mesure: MesureCapteur) -> RecommandationArrosage:
        if mesure.sol < espece.seuil_sol_sec - 5:
            v = Verdict.ARROSER
        elif mesure.sol < espece.seuil_sol_sec + 10:
            v = Verdict.VERIFIER
        else:
            v = Verdict.NE_PAS_ARROSER
        return RecommandationArrosage(
            verdict=v, confiance=0.5,
            explication="Repli par règle (modèle non chargé).")
