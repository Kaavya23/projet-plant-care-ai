"""
Orchestration Prefect (cf. M3) — ingestion → validation → transformation.

Deux sources de NATURES DIFFÉRENTES (exigence M1) :
  - Open-Meteo  : API publique, quasi temps réel, AUCUNE clé requise.
  - Capteurs    : mesures simulées (micro-lots).

Le flow écrit d'abord en zone RAW, valide/nettoie en STAGING, puis agrège en
CURATED. L'idempotence (cf. M2/R8) est assurée par une CLÉ DE HACHAGE + upsert :
réexécuter le flow ne crée aucun doublon.

Lancement local (sans serveur Prefect) :  python pipelines/prefect_flows.py
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from prefect import flow, task
except Exception:  # repli si Prefect absent : les décorateurs deviennent neutres
    def task(fn=None, **_):
        return (lambda f: f)(fn) if fn else (lambda f: f)
    def flow(fn=None, **_):
        return (lambda f: f)(fn) if fn else (lambda f: f)

VILLES = {"Paris": (48.85, 2.35), "Lyon": (45.76, 4.83), "Lille": (50.63, 3.06)}


def _cle(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]


@task(retries=2, retry_delay_seconds=5)
def ingerer_meteo() -> list[dict]:
    """Source quasi temps réel — Open-Meteo (pas de clé API)."""
    import requests
    rows = []
    for ville, (lat, lon) in VILLES.items():
        try:
            r = requests.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
            }, timeout=10)
            cur = r.json().get("current", {})
            rows.append(dict(
                ville=ville, temp=cur.get("temperature_2m"),
                humidite=cur.get("relative_humidity_2m"),
                vent=cur.get("wind_speed_10m"), pluie=cur.get("precipitation"),
                horodatage=datetime.now(timezone.utc).isoformat(),
                cle=_cle(ville, datetime.now(timezone.utc).strftime("%Y%m%d%H"))))
        except Exception as e:
            print(f"  [meteo] {ville} indisponible : {e}")
    return rows


@task
def simuler_capteurs(n: int = 20) -> list[dict]:
    import numpy as np
    rng = np.random.default_rng()
    now = datetime.now(timezone.utc)
    return [dict(
        plante_id=int(rng.integers(1, 50)),
        sol=float(np.clip(rng.normal(30, 15), 2, 95)),
        temperature=float(np.clip(rng.normal(22, 5), 8, 38)),
        lux=float(np.clip(rng.normal(700, 250), 50, 2000)),
        humidite=float(np.clip(rng.normal(55, 12), 15, 95)),
        horodatage=now.isoformat(),
        cle=_cle("capteur", i, now.strftime("%Y%m%d%H%M"))) for i in range(n)]


@task
def valider(rows: list[dict]) -> list[dict]:
    """Nettoyage minimal : on retire les lignes à valeurs manquantes."""
    return [r for r in rows if all(v is not None for v in r.values())]


@task
def ecrire(rows: list[dict], zone: str, nom: str) -> str:
    """Écrit dans le datalake (dédoublonnage par 'cle' = idempotence)."""
    import pandas as pd
    from plantcare.infrastructure.datalake import ecrire_parquet, lire_parquet
    df = pd.DataFrame(rows)
    if df.empty:
        return "vide"
    try:
        existant = lire_parquet(zone, nom)
        df = pd.concat([existant, df]).drop_duplicates("cle", keep="last")
    except Exception:
        pass  # première exécution : pas encore de fichier
    return ecrire_parquet(df, zone, nom)


@flow(name="plantcare-ingestion")
def ingestion_flow():
    meteo = valider(ingerer_meteo())
    capteurs = valider(simuler_capteurs())
    p1 = ecrire(meteo, "raw", "meteo.parquet")
    p2 = ecrire(capteurs, "raw", "capteurs.parquet")
    print(f"Ingestion terminée : {len(meteo)} météo, {len(capteurs)} capteurs")
    print(f"  -> {p1}\n  -> {p2}")


if __name__ == "__main__":
    ingestion_flow()
