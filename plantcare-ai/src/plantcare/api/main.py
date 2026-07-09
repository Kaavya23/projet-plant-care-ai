"""
Couche de restitution — API FastAPI (Clean Architecture).

Le "composition root" : on instancie ici les adaptateurs concrets et on les
injecte dans les cas d'usage. Les routes ne font qu'appeler les cas d'usage
et sérialiser leur résultat. Aucune logique métier dans cette couche.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from plantcare.adapters.llm_gateway import obtenir_gateway
from plantcare.adapters.vision_model import VisionModel
from plantcare.adapters.watering_model import WateringModel
from plantcare.domain.entities import Espece, MesureCapteur, Plante
from plantcare.infrastructure import datalake
from plantcare.usecases.services import (ConseillerEntretien,
                                         ReconnaitreEspece, RecommanderArrosage)

app = FastAPI(title="PlantCare AI", version="1.0.0",
              description="POC — trois options d'IA (A/B/C) sur socle datalake.")

# --- composition root : adaptateurs concrets -> cas d'usage ----------------
_watering = WateringModel()
_vision = VisionModel()
_gateway = obtenir_gateway()

uc_arrosage = RecommanderArrosage(_watering)
uc_conseil = ConseillerEntretien(_gateway, uc_arrosage)
uc_espece = ReconnaitreEspece(_vision)


# --- schémas d'E/S (Pydantic) ---------------------------------------------
class EspeceIn(BaseModel):
    id: int
    nom_sci: str
    lumiere: float = 0.5
    seuil_sol_sec: float = 30.0
    temp_min: float = 15
    temp_max: float = 28
    humidite: float = 55


class MesureIn(BaseModel):
    sol: float
    temperature: float
    lux: float
    humidite_air: float


class ArrosageRequest(BaseModel):
    plante_id: int = 1
    taille_pot: int = 18
    emplacement: str = "salon"
    espece: EspeceIn
    mesure: MesureIn
    jours_dernier_arrosage: int = 3


class ConseilRequest(ArrosageRequest):
    temperature_jour: float
    humidite_air_jour: float


def _to_domain(req: ArrosageRequest):
    plante = Plante(id=req.plante_id, espece_id=req.espece.id,
                    emplacement=req.emplacement, taille_pot=req.taille_pot)
    espece = Espece(id=req.espece.id, nom_sci=req.espece.nom_sci,
                    lumiere=req.espece.lumiere, humidite=req.espece.humidite,
                    temp_min=req.espece.temp_min, temp_max=req.espece.temp_max,
                    seuil_sol_sec=req.espece.seuil_sol_sec)
    mesure = MesureCapteur(sol=req.mesure.sol, temperature=req.mesure.temperature,
                           lux=req.mesure.lux, humidite_air=req.mesure.humidite_air)
    return plante, espece, mesure


@app.get("/health")
def health():
    return {"status": "ok", "watering_model": _watering.is_loaded,
            "vision_model": _vision.is_loaded,
            "llm": type(_gateway).__name__}


@app.post("/api/v1/arrosage", tags=["Option C"])
def recommander_arrosage(req: ArrosageRequest):
    """Option C — verdict d'arrosage (RandomForest maison)."""
    plante, espece, mesure = _to_domain(req)
    reco = uc_arrosage.executer(plante, espece, mesure, req.jours_dernier_arrosage)
    result = {"verdict": reco.verdict.value, "confiance": round(reco.confiance, 3),
              "explication": reco.explication}
    ts = datetime.now(timezone.utc).isoformat()
    datalake.ecrire_parquet(
        pd.DataFrame([{"ts": ts, "plante_id": req.plante_id,
                       "espece": req.espece.nom_sci, **result}]),
        "raw", f"arrosage/{ts[:10]}/{uuid.uuid4().hex}.parquet")
    return result


@app.post("/api/v1/conseil", tags=["Option A"])
def conseiller_entretien(req: ConseilRequest):
    """Option A — conseil en langage naturel (Gemini + secours local)."""
    plante, espece, mesure = _to_domain(req)
    conseil = uc_conseil.executer(plante, espece, mesure,
                                  req.temperature_jour, req.humidite_air_jour)
    result = {"conseil": conseil.texte, "source": conseil.source}
    ts = datetime.now(timezone.utc).isoformat()
    datalake.ecrire_parquet(
        pd.DataFrame([{"ts": ts, "plante_id": req.plante_id,
                       "espece": req.espece.nom_sci, **result}]),
        "raw", f"conseils/{ts[:10]}/{uuid.uuid4().hex}.parquet")
    return result


@app.post("/api/v1/reconnaissance", tags=["Option B"])
async def reconnaitre_espece(fichier: UploadFile = File(...)):
    """Option B — reconnaissance d'espèce par photo (MobileNetV2 local)."""
    if not fichier.content_type or not fichier.content_type.startswith("image/"):
        raise HTTPException(400, "Un fichier image est attendu.")
    data = await fichier.read()
    res = uc_espece.executer(data)
    ts = datetime.now(timezone.utc).isoformat()
    uid = uuid.uuid4().hex
    ext = (fichier.filename or "image.jpg").rsplit(".", 1)[-1]
    datalake.ecrire_bytes(data, "raw", f"images/{ts[:10]}/{uid}.{ext}")
    result = {"espece_predite": res.espece_predite, "score": round(res.score, 3),
              "alternatives": [{"espece": e, "score": round(s, 3)}
                               for e, s in res.alternatives]}
    datalake.ecrire_parquet(
        pd.DataFrame([{"ts": ts, "image_id": uid,
                       "espece_predite": res.espece_predite,
                       "score": res.score}]),
        "raw", f"predictions/{ts[:10]}/{uid}.parquet")
    return result
