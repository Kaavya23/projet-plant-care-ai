"""
Génère un jeu de données simulé cohérent pour PlantCare AI.

Sortie : plusieurs CSV dans data/ qui alimentent :
  - l'entraînement du modèle d'arrosage (Option C)
  - le peuplement de la base PostgreSQL de service

La logique d'arrosage est volontairement DÉTERMINISTE-BRUITÉE : un verdict
"vérité terrain" est calculé à partir de règles agronomiques simples, puis
un peu de bruit est ajouté. Le RandomForest doit retrouver cette logique.
Cela garantit un F1 élevé tout en restant un vrai problème d'apprentissage.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)

# Verdicts (Option C) : 3 classes imposées par le cahier des charges
VERDICTS = ["ne_pas_arroser", "verifier_prochainement", "arroser_maintenant"]

ESPECES = [
    # nom_sci, lumiere(0-1), humidite_cible(%), temp_min, temp_max, seuil_sol_sec(%)
    ("Monstera deliciosa", 0.6, 60, 18, 27, 30),
    ("Ficus lyrata", 0.7, 55, 16, 24, 28),
    ("Sansevieria trifasciata", 0.4, 40, 15, 29, 20),
    ("Epipremnum aureum", 0.5, 55, 17, 26, 30),
    ("Chlorophytum comosum", 0.6, 50, 15, 25, 28),
    ("Calathea orbifolia", 0.4, 70, 18, 24, 40),
    ("Zamioculcas zamiifolia", 0.3, 40, 16, 28, 18),
    ("Spathiphyllum wallisii", 0.4, 65, 18, 25, 45),
]

VILLES = ["Paris", "Lyon", "Bordeaux", "Lille", "Marseille"]


def verite_terrain(sol_humidite, seuil_sec, temp, humidite_air, jours_dernier_arrosage):
    """Règle agronomique 'oracle' que le modèle devra apprendre."""
    # Indice de stress hydrique : plus le sol est sec / chaud / air sec / long
    # depuis le dernier arrosage, plus il faut arroser.
    stress = (
        (seuil_sec - sol_humidite) * 1.2
        + (temp - 22) * 0.8
        + (50 - humidite_air) * 0.3
        + jours_dernier_arrosage * 2.0
    )
    if stress > 18:
        return "arroser_maintenant"
    if stress > 4:
        return "verifier_prochainement"
    return "ne_pas_arroser"


def generer(n_users=120, mesures_par_plante=40):
    users, plantes, especes_rows, soins, mesures, meteo, dataset = ([] for _ in range(7))

    for i, (nom, lum, hum, tmin, tmax, seuil) in enumerate(ESPECES, start=1):
        especes_rows.append(
            dict(id=i, nom_sci=nom, lumiere=lum, humidite=hum,
                 temp_min=tmin, temp_max=tmax, seuil_sol_sec=seuil)
        )

    plante_id = 0
    for u in range(1, n_users + 1):
        ville = RNG.choice(VILLES)
        users.append(dict(id=u, email=f"user{u}@example.test", ville=ville,
                          date_inscription="2026-06-01"))
        for _ in range(RNG.integers(1, 4)):
            plante_id += 1
            esp = especes_rows[RNG.integers(0, len(ESPECES))]
            plantes.append(dict(id=plante_id, user_id=u, espece_id=esp["id"],
                                emplacement=RNG.choice(["salon", "chambre", "cuisine", "bureau"]),
                                taille_pot=int(RNG.integers(10, 30)),
                                date_ajout="2026-06-10"))
            for _ in range(mesures_par_plante):
                sol = float(np.clip(RNG.normal(esp["seuil_sol_sec"], 15), 2, 95))
                temp = float(np.clip(RNG.normal(22, 5), 8, 38))
                lux = float(np.clip(RNG.normal(esp["lumiere"] * 1000, 250), 50, 2000))
                hum_air = float(np.clip(RNG.normal(esp["humidite"], 12), 15, 95))
                jours = int(RNG.integers(0, 10))
                verdict = verite_terrain(sol, esp["seuil_sol_sec"], temp, hum_air, jours)
                # bruit d'étiquetage : 8 % des cas basculent sur une classe voisine
                if RNG.random() < 0.08:
                    idx = VERDICTS.index(verdict)
                    verdict = VERDICTS[int(np.clip(idx + RNG.choice([-1, 1]), 0, 2))]
                mesures.append(dict(plante_id=plante_id, humidite=hum_air, sol=sol,
                                    temperature=temp, lux=lux, horodatage="2026-07-01"))
                dataset.append(dict(
                    espece_id=esp["id"], taille_pot=plantes[-1]["taille_pot"],
                    sol=sol, temperature=temp, lux=lux, humidite_air=hum_air,
                    seuil_sol_sec=esp["seuil_sol_sec"], jours_dernier_arrosage=jours,
                    verdict=verdict))
            soins.append(dict(plante_id=plante_id, type_action="arrosage",
                              date="2026-06-28", quantite=200, photo_ref=None))

    for v in VILLES:
        meteo.append(dict(ville=v, temp=float(RNG.normal(24, 4)), pluie=float(RNG.random()),
                          vent=float(RNG.normal(12, 4)), horodatage="2026-07-01"))

    return dict(
        utilisateurs=pd.DataFrame(users),
        especes=pd.DataFrame(especes_rows),
        plantes=pd.DataFrame(plantes),
        historique_soins=pd.DataFrame(soins),
        mesures_capteurs=pd.DataFrame(mesures),
        obs_meteo=pd.DataFrame(meteo),
        dataset_arrosage=pd.DataFrame(dataset),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data")
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tables = generer()
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
        print(f"  {name:22s} -> {len(df):6d} lignes")
    # catalogue d'espèces exposé aussi comme "source publique" du datalake
    tables["especes"].to_csv(out / "catalogue_especes.csv", index=False)
    print("Données simulées générées dans", out.resolve())
