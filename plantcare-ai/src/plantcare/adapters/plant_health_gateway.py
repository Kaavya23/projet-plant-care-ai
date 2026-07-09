"""
Option D — Analyse de santé de la plante via l'API plant.health (Kindwise).

Même pattern que llm_gateway.py : abstraction Protocol + deux implémentations :
  1. PlantHealthAPIGateway  -> appelle https://plant.id/api/v3/identification
  2. PlantHealthStubGateway -> repli local quand la clé est absente

La clé reste côté serveur (variable d'environnement PLANT_HEALTH_API_KEY).
L'image est prétraitée localement (redimensionnement, suppression EXIF, base64).

RGPD : la photo transite vers une API tierce uniquement si l'utilisateur
soumet une image ET que la clé API est configurée. Ce point est documenté
dans le README et doit être mentionné dans la politique de confidentialité.
"""
from __future__ import annotations

import base64
import os
from io import BytesIO
from typing import Protocol

import requests
from PIL import Image, ImageOps

from plantcare.domain.entities import AnalyseSante, SuggestionMaladie

_API_URL = "https://plant.id/api/v3/identification"
_PARAMS = {"details": "local_name,description,treatment", "language": "fr"}


def _encode_image(image_bytes: bytes) -> str:
    """Resize, strip EXIF and return a base64 JPEG string."""
    img = Image.open(BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1600, 1600))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _parse_response(data: dict) -> AnalyseSante:
    health = data.get("result", {}).get("is_healthy", {})
    disease = data.get("result", {}).get("disease", {})

    suggestions: list[SuggestionMaladie] = []
    for s in disease.get("suggestions", [])[:3]:
        details = s.get("details") or {}
        traitement_raw = details.get("treatment")

        if isinstance(traitement_raw, dict):
            lignes: list[str] = []
            for cat, instrs in traitement_raw.items():
                titre = cat.replace("_", " ").title()
                if isinstance(instrs, list):
                    lignes.append(f"{titre} : " + " / ".join(instrs))
                elif instrs:
                    lignes.append(f"{titre} : {instrs}")
            traitement_str: str | None = "\n".join(lignes) or None
        elif isinstance(traitement_raw, list):
            traitement_str = " / ".join(traitement_raw) or None
        elif isinstance(traitement_raw, str):
            traitement_str = traitement_raw or None
        else:
            traitement_str = None

        nom = (
            details.get("local_name")
            or s.get("name")
            or "Problème non identifié"
        )

        suggestions.append(SuggestionMaladie(
            nom=nom,
            probabilite=s.get("probability", 0.0),
            description=details.get("description") or "",
            traitement=traitement_str,
        ))

    return AnalyseSante(
        est_saine=health.get("binary"),
        probabilite_sante=health.get("probability"),
        suggestions=suggestions,
    )


class PlantHealthGateway(Protocol):
    def analyser(self, image_bytes: bytes) -> AnalyseSante: ...


class PlantHealthStubGateway:
    """Repli quand PLANT_HEALTH_API_KEY est absente."""

    def analyser(self, image_bytes: bytes) -> AnalyseSante:
        return AnalyseSante(
            est_saine=None,
            probabilite_sante=None,
            suggestions=[],
        )


class PlantHealthAPIGateway:
    """Appelle l'API plant.health (Kindwise Plant.id v3)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def analyser(self, image_bytes: bytes) -> AnalyseSante:
        image_b64 = _encode_image(image_bytes)
        response = requests.post(
            _API_URL,
            params=_PARAMS,
            headers={
                "Api-Key": self._api_key,
                "Content-Type": "application/json",
            },
            json={
                "images": [image_b64],
                "health": "only",
                "similar_images": True,
            },
            timeout=30,
        )
        response.raise_for_status()
        return _parse_response(response.json())


def obtenir_plant_health_gateway() -> PlantHealthGateway:
    """Fabrique : API si PLANT_HEALTH_API_KEY est présente, sinon stub."""
    api_key = os.getenv("PLANT_HEALTH_API_KEY")
    if api_key:
        return PlantHealthAPIGateway(api_key=api_key)
    return PlantHealthStubGateway()
