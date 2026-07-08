"""
Couche DOMAINE (Clean Architecture) — entités métier pures.

Aucune dépendance à FastAPI, SQLAlchemy, sklearn, etc. Ce sont les objets
que manipulent les cas d'usage. Les couches externes en dépendent, jamais
l'inverse (règle de dépendance de la Clean Architecture).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Verdict(str, Enum):
    NE_PAS_ARROSER = "ne_pas_arroser"
    VERIFIER = "verifier_prochainement"
    ARROSER = "arroser_maintenant"


@dataclass(frozen=True)
class Espece:
    id: int
    nom_sci: str
    lumiere: float
    humidite: float
    temp_min: float
    temp_max: float
    seuil_sol_sec: float = 30.0


@dataclass(frozen=True)
class MesureCapteur:
    sol: float
    temperature: float
    lux: float
    humidite_air: float


@dataclass(frozen=True)
class Plante:
    id: int
    espece_id: int
    emplacement: str
    taille_pot: int


@dataclass(frozen=True)
class RecommandationArrosage:
    """Sortie de l'Option C."""
    verdict: Verdict
    confiance: float
    explication: str


@dataclass(frozen=True)
class ConseilEntretien:
    """Sortie de l'Option A."""
    texte: str
    source: str  # "gemini" ou "gabarit_local"


@dataclass(frozen=True)
class AnalyseImage:
    """Sortie de l'Option B."""
    espece_predite: str
    score: float
    alternatives: list[tuple[str, float]]
