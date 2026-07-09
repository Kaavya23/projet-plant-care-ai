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

# Espèces simulées pour les capteurs (nom, seuil_sol_sec %) — alignées sur
# les 3 plantes proposées dans le dashboard (onglet Arrosage / Conseil).
ESPECES_CAPTEURS = [
    ("Monstera deliciosa", 30),
    ("Sansevieria trifasciata", 20),
    ("Calathea orbifolia", 40),
]


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
    rows = []
    for i in range(n):
        espece, seuil = ESPECES_CAPTEURS[int(rng.integers(0, len(ESPECES_CAPTEURS)))]
        rows.append(dict(
            plante_id=int(rng.integers(1, 50)),
            espece=espece,
            seuil_sol_sec=float(seuil),
            sol=float(np.clip(rng.normal(seuil, 15), 2, 95)),
            temperature=float(np.clip(rng.normal(22, 5), 8, 38)),
            lux=float(np.clip(rng.normal(700, 250), 50, 2000)),
            humidite=float(np.clip(rng.normal(55, 12), 15, 95)),
            horodatage=now.isoformat(),
            cle=_cle("capteur", i, now.strftime("%Y%m%d%H%M"))))
    return rows


@task
def valider(rows: list[dict]) -> list[dict]:
    """Nettoyage minimal : on retire les lignes à valeurs manquantes."""
    return [r for r in rows if all(v is not None for v in r.values())]


@task
def ecrire(rows: list[dict], zone: str, nom: str) -> str:
    """Écrit dans le datalake (dédoublonnage par 'cle' = idempotence)."""
    import pandas as pd
    from plantcare.infrastructure.datalake import ecrire_csv, lire_csv
    df = pd.DataFrame(rows)
    if df.empty:
        return "vide"
    try:
        existant = lire_csv(zone, nom)
        df = pd.concat([existant, df]).drop_duplicates("cle", keep="last")
    except Exception:
        pass  # première exécution : pas encore de fichier
    return ecrire_csv(df, zone, nom)


# --- Couche STAGING (silver) : nettoyage, typage, flags métier -------------
SEUIL_SOL_SEC = 30.0  # seuil générique (%) en dessous duquel le sol est jugé sec


@task
def transformer_staging() -> dict:
    """RAW -> STAGING : validation, typage, déduplication, enrichissement."""
    import pandas as pd
    from plantcare.infrastructure.datalake import ecrire_csv, lire_csv
    resultats: dict[str, str] = {}

    # Météo : types corrects, horodatage datetime, colonnes temporelles
    try:
        meteo = lire_csv("raw", "meteo.csv")
        for c in ("temp", "humidite", "vent", "pluie"):
            meteo[c] = pd.to_numeric(meteo[c], errors="coerce")
        meteo["horodatage"] = pd.to_datetime(meteo["horodatage"], utc=True, errors="coerce")
        meteo = (meteo.dropna(subset=["temp", "humidite"])
                      .drop_duplicates("cle", keep="last"))
        meteo["date"] = meteo["horodatage"].dt.strftime("%Y-%m-%d")
        meteo["heure"] = meteo["horodatage"].dt.strftime("%Y-%m-%dT%H:00:00Z")
        resultats["meteo"] = ecrire_csv(meteo, "staging", "meteo_clean.csv")
    except Exception as e:
        print(f"  [staging] météo ignorée : {e}")

    # Capteurs : types corrects, flag métier sol_sec, colonne date
    try:
        cap = lire_csv("raw", "capteurs.csv")
        for c in ("sol", "temperature", "lux", "humidite", "seuil_sol_sec"):
            cap[c] = pd.to_numeric(cap[c], errors="coerce")
        cap = (cap.dropna(subset=["sol", "temperature"])
                  .drop_duplicates("cle", keep="last"))
        cap["horodatage"] = pd.to_datetime(cap["horodatage"], utc=True, errors="coerce")
        seuil = cap["seuil_sol_sec"].fillna(SEUIL_SOL_SEC)
        cap["sol_sec"] = cap["sol"] < seuil
        cap["date"] = cap["horodatage"].dt.strftime("%Y-%m-%d")
        resultats["capteurs"] = ecrire_csv(cap, "staging", "capteurs_clean.csv")
    except Exception as e:
        print(f"  [staging] capteurs ignorés : {e}")

    return resultats


# --- Couche CURATED (gold) : agrégats métier prêts à l'analyse -------------
@task
def agreger_curated() -> dict:
    """STAGING -> CURATED : agrégats et KPI prêts pour dashboard/ML."""
    import pandas as pd
    from plantcare.infrastructure.datalake import (ecrire_csv, lire_csv,
                                                   lire_csv_glob)
    resultats: dict[str, str] = {}

    # Météo agrégée par ville et par heure
    try:
        meteo = lire_csv("staging", "meteo_clean.csv")
        agg = (meteo.groupby(["ville", "heure"], as_index=False)
                    .agg(temp_moy=("temp", "mean"), humidite_moy=("humidite", "mean"),
                         vent_moy=("vent", "mean"), pluie_tot=("pluie", "sum")))
        agg = agg.round(2)
        resultats["meteo"] = ecrire_csv(agg, "curated", "meteo_horaire.csv")
    except Exception as e:
        print(f"  [curated] météo ignorée : {e}")

    # Statistiques capteurs par espèce
    try:
        cap = lire_csv("staging", "capteurs_clean.csv")
        stats = (cap.groupby("espece", as_index=False)
                    .agg(sol_moy=("sol", "mean"), temp_moy=("temperature", "mean"),
                         humidite_moy=("humidite", "mean"),
                         pct_sol_sec=("sol_sec", "mean"), n_mesures=("sol", "size")))
        stats["pct_sol_sec"] = (stats["pct_sol_sec"] * 100).round(1)
        stats = stats.round(2)
        resultats["capteurs"] = ecrire_csv(stats, "curated", "capteurs_stats.csv")
    except Exception as e:
        print(f"  [curated] capteurs ignorés : {e}")

    # KPI des reconnaissances (Option B) : top espèces + score moyen
    try:
        preds = lire_csv_glob("raw", "predictions/**/*.csv")
        if not preds.empty:
            kpi = (preds.groupby("espece_predite", as_index=False)
                        .agg(n=("espece_predite", "size"), score_moy=("score", "mean"))
                        .sort_values("n", ascending=False))
            kpi["score_moy"] = kpi["score_moy"].round(3)
            resultats["predictions"] = ecrire_csv(
                kpi, "curated", "predictions_stats.csv")
    except Exception as e:
        print(f"  [curated] prédictions ignorées : {e}")

    return resultats


@flow(name="plantcare-ingestion")
def ingestion_flow():
    meteo = valider(ingerer_meteo())
    capteurs = valider(simuler_capteurs())
    p1 = ecrire(meteo, "raw", "meteo.csv")
    p2 = ecrire(capteurs, "raw", "capteurs.csv")
    print(f"Ingestion terminée : {len(meteo)} météo, {len(capteurs)} capteurs")
    print(f"  -> {p1}\n  -> {p2}")

    stg = transformer_staging()
    print(f"Staging (silver)  : {stg}")
    cur = agreger_curated()
    print(f"Curated (gold)    : {cur}")


if __name__ == "__main__":
    ingestion_flow()
