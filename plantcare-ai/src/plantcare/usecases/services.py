"""
Couche CAS D'USAGE (application) — orchestre le domaine et les adaptateurs.

Chaque cas d'usage correspond à une fonctionnalité du M4 :
  - RecommanderArrosage      (Option C)
  - ConseillerEntretien      (Option A) — dépend du verdict de l'Option C
  - ReconnaitreEspece        (Option B)

Ces classes ne connaissent ni FastAPI ni la base : elles reçoivent leurs
dépendances par injection (adaptateurs), ce qui les rend testables isolément.
"""
from __future__ import annotations

from plantcare.adapters.llm_gateway import LLMGateway, PayloadConseil
from plantcare.adapters.plant_health_gateway import PlantHealthGateway
from plantcare.adapters.vision_model import VisionModel
from plantcare.adapters.watering_model import WateringModel
from plantcare.domain.entities import (AnalyseImage, AnalyseSante,
                                       ConseilEntretien, Espece,
                                       MesureCapteur, Plante,
                                       RecommandationArrosage)

_LUMIERE_LABEL = {0.3: "faible", 0.4: "modérée", 0.5: "modérée",
                  0.6: "vive", 0.7: "vive"}


def _label_lumiere(v: float) -> str:
    return "vive" if v >= 0.6 else "modérée" if v >= 0.4 else "faible"


class RecommanderArrosage:
    def __init__(self, model: WateringModel):
        self.model = model

    def executer(self, plante: Plante, espece: Espece, mesure: MesureCapteur,
                 jours: int = 3) -> RecommandationArrosage:
        return self.model.predire(plante, espece, mesure, jours)


class ConseillerEntretien:
    def __init__(self, gateway: LLMGateway, arrosage: RecommanderArrosage):
        self.gateway = gateway
        self.arrosage = arrosage

    def executer(self, plante: Plante, espece: Espece, mesure: MesureCapteur,
                 temp_jour: float, humidite_jour: float,
                 meteo_resume: str | None = None,
                 meteo_source: str | None = None) -> ConseilEntretien:
        reco = self.arrosage.executer(plante, espece, mesure)
        # payload PSEUDONYMISÉ : aucune donnée personnelle brute (cf. M6)
        payload = PayloadConseil(
            espece=espece.nom_sci,
            lumiere=_label_lumiere(espece.lumiere),
            temperature_jour=temp_jour,
            humidite_air_jour=humidite_jour,
            verdict_arrosage=reco.verdict.value,
            meteo_resume=meteo_resume,
            meteo_source=meteo_source)
        return self.gateway.conseiller(payload)


class ReconnaitreEspece:
    def __init__(self, model: VisionModel):
        self.model = model

    def executer(self, image_bytes: bytes) -> AnalyseImage:
        return self.model.predire(image_bytes)


class AnalyserSantePlante:
    """Option D — délègue l'analyse de santé au gateway plant.health."""

    def __init__(self, gateway: PlantHealthGateway):
        self.gateway = gateway

    def executer(self, image_bytes: bytes) -> AnalyseSante:
        return self.gateway.analyser(image_bytes)
