"""
Couche de restitution - API FastAPI (Clean Architecture).

Le "composition root" : on instancie ici les adaptateurs concrets et on les
injecte dans les cas d'usage. Les routes ne font qu'appeler les cas d'usage
et serialiser leur resultat. Aucune logique metier dans cette couche.
"""
from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from plantcare.adapters.llm_gateway import obtenir_gateway
from plantcare.adapters.plant_health_gateway import obtenir_plant_health_gateway
from plantcare.adapters.vision_model import VisionModel
from plantcare.adapters.watering_model import WateringModel
from plantcare.adapters.weather_gateway import MeteoSnapshot, obtenir_weather_gateway
from plantcare.config import settings
from plantcare.domain.entities import Espece, MesureCapteur, Plante
from plantcare.usecases.services import (
    AnalyserSantePlante,
    ConseillerEntretien,
    RecommanderArrosage,
    ReconnaitreEspece,
)

load_dotenv()  # charge .env pour un lancement local (hors Docker)

app = FastAPI(title="PlantCare AI", version="1.0.0",
              description="POC — trois options d'IA (A/B/C) sur socle datalake.")

# --- composition root : adaptateurs concrets -> cas d'usage ----------------
_watering = WateringModel()
_vision = VisionModel()
_gateway = obtenir_gateway()
_weather = obtenir_weather_gateway(settings.openweather_api_key)
_plant_health = obtenir_plant_health_gateway()

uc_arrosage = RecommanderArrosage(_watering)
uc_conseil = ConseillerEntretien(_gateway, uc_arrosage)
uc_espece = ReconnaitreEspece(_vision)
uc_sante = AnalyserSantePlante(_plant_health)


# --- schemas d'E/S (Pydantic) ---------------------------------------------
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


class MeteoIn(BaseModel):
    ville: str | None = None
    code_pays: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    units: Literal["standard", "metric", "imperial"] | None = None
    lang: str | None = None


class ConseilRequest(ArrosageRequest):
    # Optionnel: si absent, l'API prend la meteo OWM puis fallback capteurs.
    temperature_jour: float | None = None
    humidite_air_jour: float | None = None
    meteo: MeteoIn | None = None


def _to_domain(req: ArrosageRequest):
    plante = Plante(
        id=req.plante_id,
        espece_id=req.espece.id,
        emplacement=req.emplacement,
        taille_pot=req.taille_pot,
    )
    espece = Espece(
        id=req.espece.id,
        nom_sci=req.espece.nom_sci,
        lumiere=req.espece.lumiere,
        humidite=req.espece.humidite,
        temp_min=req.espece.temp_min,
        temp_max=req.espece.temp_max,
        seuil_sol_sec=req.espece.seuil_sol_sec,
    )
    mesure = MesureCapteur(
        sol=req.mesure.sol,
        temperature=req.mesure.temperature,
        lux=req.mesure.lux,
        humidite_air=req.mesure.humidite_air,
    )
    return plante, espece, mesure


def _charger_meteo(req: ConseilRequest) -> MeteoSnapshot | None:
    meteo_req = req.meteo or MeteoIn()
    ville = (meteo_req.ville or settings.openweather_default_city or "").strip()
    code_pays = meteo_req.code_pays or settings.openweather_default_country

    units = meteo_req.units or settings.openweather_default_units
    lang = meteo_req.lang or settings.openweather_default_lang

    if ville:
        return _weather.recuperer_par_ville(
            ville=ville,
            units=units,
            lang=lang,
            code_pays=code_pays,
        )

    latitude = (
        meteo_req.latitude
        if meteo_req.latitude is not None
        else settings.openweather_default_lat
    )
    longitude = (
        meteo_req.longitude
        if meteo_req.longitude is not None
        else settings.openweather_default_lon
    )
    if latitude is None or longitude is None:
        return None

    return _weather.recuperer(latitude=latitude, longitude=longitude, units=units, lang=lang)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "watering_model": type(_watering).__name__,
        "vision_model": type(_vision).__name__,
        "llm": type(_gateway).__name__,
        "weather": type(_weather).__name__,
        "plant_health": type(_plant_health).__name__,
    }


@app.post("/api/v1/arrosage", tags=["Option C"])
def recommander_arrosage(req: ArrosageRequest):
    """Option C - verdict d'arrosage (RandomForest maison)."""
    plante, espece, mesure = _to_domain(req)
    reco = uc_arrosage.executer(plante, espece, mesure, req.jours_dernier_arrosage)
    return {
        "verdict": reco.verdict.value,
        "confiance": round(reco.confiance, 3),
        "explication": reco.explication,
    }


@app.post("/api/v1/conseil", tags=["Option A"])
def conseiller_entretien(req: ConseilRequest):
    """Option A - conseil en langage naturel (Gemini + secours local)."""
    plante, espece, mesure = _to_domain(req)
    meteo_req = req.meteo or MeteoIn()
    ville_effective = (meteo_req.ville or settings.openweather_default_city or "").strip()
    code_pays_effectif = meteo_req.code_pays or settings.openweather_default_country
    units_effectif = meteo_req.units or settings.openweather_default_units
    lang_effectif = meteo_req.lang or settings.openweather_default_lang

    latitude_effective = (
        meteo_req.latitude
        if meteo_req.latitude is not None
        else settings.openweather_default_lat
    )
    longitude_effective = (
        meteo_req.longitude
        if meteo_req.longitude is not None
        else settings.openweather_default_lon
    )

    mode_meteo = "aucun"
    if ville_effective:
        mode_meteo = "ville"
    elif latitude_effective is not None and longitude_effective is not None:
        mode_meteo = "coordonnees"

    meteo = _charger_meteo(req)

    # Overrides manuels prioritaires; sinon meteo OWM; sinon capteurs locaux.
    temp_jour = req.temperature_jour
    source_temperature = "manuel"
    if temp_jour is None:
        source_temperature = "openweathermap" if meteo is not None else "capteurs"
        temp_jour = meteo.temperature if meteo is not None else req.mesure.temperature

    humidite_jour = req.humidite_air_jour
    source_humidite = "manuel"
    if humidite_jour is None:
        source_humidite = "openweathermap" if meteo is not None else "capteurs"
        humidite_jour = meteo.humidite_air if meteo is not None else req.mesure.humidite_air

    conseil = uc_conseil.executer(
        plante,
        espece,
        mesure,
        float(temp_jour),
        float(humidite_jour),
        meteo_resume=meteo.resume_prompt() if meteo else None,
        meteo_source=meteo.source if meteo else None,
    )

    return {
        "conseil": conseil.texte,
        "source": conseil.source,
        "temperature_jour": round(float(temp_jour), 2),
        "humidite_air_jour": round(float(humidite_jour), 2),
        "meteo_requete": {
            "mode": mode_meteo,
            "ville": ville_effective or None,
            "code_pays": code_pays_effectif,
            "latitude": latitude_effective,
            "longitude": longitude_effective,
            "units": units_effectif,
            "lang": lang_effectif,
        },
        "contexte_utilise": {
            "source_llm": conseil.source,
            "temperature_source": source_temperature,
            "humidite_source": source_humidite,
            "meteo_demande": mode_meteo != "aucun",
            "meteo_utilisee": meteo is not None,
            "meteo_mode": mode_meteo,
        },
        "meteo": (
            {
                "source": meteo.source,
                "latitude": meteo.latitude,
                "longitude": meteo.longitude,
                "ville": ville_effective or None,
                "code_pays": code_pays_effectif,
                "lang": lang_effectif,
                "units": meteo.units,
                "conditions": meteo.conditions,
                "vitesse_vent": meteo.vitesse_vent,
                "precipitation_1h": meteo.precipitation_1h,
            }
            if meteo
            else None
        ),
    }


@app.post("/api/v1/reconnaissance", tags=["Option B"])
async def reconnaitre_espece(fichier: UploadFile = File(...)):
    """Option B - reconnaissance d'espece par photo (MobileNetV2 local)."""
    if not fichier.content_type or not fichier.content_type.startswith("image/"):
        raise HTTPException(400, "Un fichier image est attendu.")
    data = await fichier.read()
    res = uc_espece.executer(data)
    return {
        "espece_predite": res.espece_predite,
        "score": round(res.score, 3),
        "alternatives": [
            {"espece": e, "score": round(s, 3)} for e, s in res.alternatives
        ],
    }


@app.post("/api/v1/sante", tags=["Option D"])
async def analyser_sante(fichier: UploadFile = File(...)):
    """Option D - analyse de sante via plant.health (Kindwise API)."""
    if not fichier.content_type or not fichier.content_type.startswith("image/"):
        raise HTTPException(400, "Un fichier image est attendu.")
    data = await fichier.read()
    res = uc_sante.executer(data)
    return {
        "est_saine": res.est_saine,
        "probabilite_sante": (
            round(res.probabilite_sante, 3)
            if res.probabilite_sante is not None
            else None
        ),
        "suggestions": [
            {
                "nom": s.nom,
                "probabilite": round(s.probabilite, 3),
                "description": s.description,
                "traitement": s.traitement,
            }
            for s in res.suggestions
        ],
    }
