"""
Option A — Conseil d'entretien en langage naturel.

Passerelle ABSTRAITE devant le LLM (cf. M2/R3 : cette abstraction est la
mitigation du risque d'indisponibilité de Gemini). Deux implémentations :

  1. GeminiGateway     -> appelle Vertex AI Gemini (nécessite credentials GCP)
  2. GabaritLocalGateway -> génère un conseil par gabarit, SANS aucun réseau

`obtenir_gateway()` choisit automatiquement : Gemini si les credentials sont
présents ET que le SDK répond, sinon repli silencieux sur le gabarit local.
Ainsi la fonctionnalité ne dépend JAMAIS entièrement d'un tiers (cf. M6).

RGPD : la charge utile (payload) ne contient QUE des données publiques ou
internes pseudonymisées — fiche d'espèce, météo, verdict d'arrosage. Aucune
donnée personnelle brute (email, localisation précise) n'est transmise.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from plantcare.domain.entities import ConseilEntretien


@dataclass(frozen=True)
class PayloadConseil:
    """Charge utile pseudonymisée envoyée au LLM."""
    espece: str
    lumiere: str
    temperature_jour: float
    humidite_air_jour: float
    verdict_arrosage: str
    meteo_resume: str | None = None
    meteo_source: str | None = None

    def as_prompt(self) -> str:
        meteo = ""
        if self.meteo_resume:
            src = f" ({self.meteo_source})" if self.meteo_source else ""
            meteo = f" Meteo locale{src} : {self.meteo_resume}."
        return (
            "Tu es un assistant jardinage. Rédige en français un conseil court "
            "(2-3 phrases), concret et bienveillant, pour l'entretien d'une "
            f"plante de type {self.espece}. Contexte du jour : température "
            f"{self.temperature_jour:.0f} °C, humidité de l'air "
            f"{self.humidite_air_jour:.0f} %, besoin en lumière : {self.lumiere}. "
            f"Le modèle d'arrosage recommande : « {self.verdict_arrosage} ». "
            f"{meteo}"
            "Ne mentionne aucune donnée personnelle."
        )


class LLMGateway(Protocol):
    def conseiller(self, payload: PayloadConseil) -> ConseilEntretien: ...


class GabaritLocalGateway:
    """Repli 100 % local, déterministe, sans réseau."""

    _VERDICTS = {
        "arroser_maintenant": "Le substrat est sec : arrosez dès maintenant, "
                              "puis laissez l'excédent s'écouler.",
        "verifier_prochainement": "Surveillez l'humidité du substrat ces "
                                  "prochains jours avant d'arroser.",
        "ne_pas_arroser": "Le substrat est encore humide : inutile d'arroser "
                          "pour l'instant.",
    }

    def conseiller(self, payload: PayloadConseil) -> ConseilEntretien:
        base = self._VERDICTS.get(payload.verdict_arrosage,
                                  "Vérifiez régulièrement l'état du substrat.")
        chaud = ""
        if payload.temperature_jour >= 30:
            chaud = (f" Avec {payload.temperature_jour:.0f} °C aujourd'hui, "
                     f"votre {payload.espece} risque de sécher plus vite.")
        texte = (f"{base}{chaud} Besoin en lumière : {payload.lumiere}.")
        return ConseilEntretien(texte=texte, source="gabarit_local")


class GeminiApiKeyGateway:
    """Appelle l'API Gemini via une clé AI Studio (google-generativeai).

    Voie la plus simple : une seule clé (chaîne), sans compte de service.
    """

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model_name = model
        self._fallback = GabaritLocalGateway()

    def conseiller(self, payload: PayloadConseil) -> ConseilEntretien:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)
            resp = model.generate_content(payload.as_prompt())
            return ConseilEntretien(texte=resp.text.strip(), source="gemini_api")
        except Exception:
            # quota / réseau / clé invalide -> gabarit local (cf. M2/R3)
            return self._fallback.conseiller(payload)


class GeminiGateway:
    """Appelle Vertex AI Gemini. Nécessite GCP + google-cloud-aiplatform."""

    def __init__(self, project: str, location: str = "europe-west1",
                 model: str = "gemini-1.5-flash"):
        self.project, self.location, self.model_name = project, location, model
        self._fallback = GabaritLocalGateway()

    def conseiller(self, payload: PayloadConseil) -> ConseilEntretien:
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
            vertexai.init(project=self.project, location=self.location)
            model = GenerativeModel(self.model_name)
            resp = model.generate_content(payload.as_prompt())
            return ConseilEntretien(texte=resp.text.strip(), source="gemini")
        except Exception:
            # cache/indispo/quota -> gabarit local (cf. M2/R3)
            return self._fallback.conseiller(payload)


def obtenir_gateway() -> LLMGateway:
    """Fabrique : clé API AI Studio > Vertex AI > gabarit local.

    On choisit la première voie effectivement configurée. Aucune configuration
    -> gabarit local, garantissant une réponse même hors ligne (cf. M6).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return GeminiApiKeyGateway(
            api_key, model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))

    project = os.getenv("GCP_PROJECT")
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if project and creds and os.path.exists(creds):
        return GeminiGateway(project=project,
                             location=os.getenv("GCP_LOCATION", "europe-west1"))

    return GabaritLocalGateway()