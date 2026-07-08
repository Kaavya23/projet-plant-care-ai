"""Peuple PostgreSQL (base de service) à partir des CSV simulés."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
from plantcare.infrastructure.db import get_engine, init_db

DATA = Path("data")

def main():
    init_db()
    eng = get_engine()
    mapping = {
        "utilisateur": "utilisateurs.csv", "espece": "especes.csv",
        "plante": "plantes.csv", "historique_soin": "historique_soins.csv",
        "mesure_capteur": "mesures_capteurs.csv", "obs_meteo": "obs_meteo.csv",
    }
    for table, fichier in mapping.items():
        p = DATA / fichier
        if not p.exists():
            print(f"  (absent) {fichier} — lance generate_synthetic_data.py")
            continue
        df = pd.read_csv(p)
        if table == "espece" and "seuil_sol_sec" not in df.columns:
            df["seuil_sol_sec"] = 30.0
        df.to_sql(table, eng, if_exists="append", index=False)
        print(f"  {table:18s} <- {len(df)} lignes")
    print("Base peuplée.")

if __name__ == "__main__":
    main()
