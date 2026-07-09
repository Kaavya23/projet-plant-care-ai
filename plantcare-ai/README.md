# 🌿 PlantCare AI — POC

Assistant d'entretien de plantes d'intérieur reposant sur **trois options d'IA**
(A/B/C) posées sur un **datalake** multi-sources. Implémentation de référence du
projet _MSI-5-26-BD_ (Tina, Kaavya, Nathan, Thomas · client Zineb Lamri).

> Ce dépôt tourne **en local sans aucune clé** (données simulées + gabarit local
> de l'Option A). Voir **[`SETUP_MANUEL.md`](SETUP_MANUEL.md)** pour activer
> Gemini, PlantNet, PostgreSQL, MinIO, etc.

## Les trois options

| Option              | Fonction                               | Brique                               | Donnée / RGPD                    |
| ------------------- | -------------------------------------- | ------------------------------------ | -------------------------------- |
| **A — Conseiller**  | conseil d'entretien en langage naturel | Vertex AI Gemini + **secours local** | payload pseudonymisé             |
| **B — Reconnaître** | espèce à partir d'une photo            | **MobileNetV2 fine-tuné**            | photo sensible → 100 % local     |
| **C — Anticiper**   | verdict d'arrosage                     | **RandomForest maison** + SHAP       | habitudes → jamais externalisées |

## Démarrage rapide (local, sans Docker)

```bash
pip install -r requirements.txt
make data        # 1. génère les données simulées
make train-c     # 2. entraîne le modèle d'arrosage (F1 ≈ 0.86 > 0.70)
make train-b     # 3. fine-tune la vision (micro-jeu si PlantNet absent)
make api         # 4. API FastAPI  -> http://localhost:8000/docs
make dash        # 5. Dashboard    -> http://localhost:8501  (autre terminal)
make pipeline    # (optionnel) ingestion Open-Meteo + capteurs -> datalake
make test        # tests (dont le critère F1 > 0.70)
```

## Option D — Analyse de santé (plant.health / Kindwise)

Intégrée dans le dashboard principal (onglet **🔬 Santé (D)**). L'onglet envoie la photo à l'API FastAPI (`POST /api/v1/sante`) qui appelle l'API plant.health côté serveur.

Pour activer, ajouter dans `.env` :

```
PLANT_HEALTH_API_KEY=votre_cle_ici
```

Sans clé, un repli stub renvoie un résultat vide (aucune erreur). La clé est lue par `load_dotenv()` au démarrage de l'API et du dashboard.

## Démarrage complet (Docker, une commande)

```bash
docker compose up --build
# API 8000 · Dashboard 8501 · PostgreSQL 5432 · MinIO 9000/9001 · MLflow 5000
```

## Architecture (Clean Architecture)

```
src/plantcare/
  domain/         # entités pures (aucune dépendance externe)
  usecases/       # orchestration des 3 options (injection de dépendances)
  adapters/       # llm_gateway (A) · vision_model (B) · watering_model (C) · plant_health_gateway (D)
  infrastructure/ # db (SQLAlchemy) · datalake (fsspec) · ORM
  api/            # FastAPI (composition root + routes)
ml/               # génération données, entraînements, model cards, seed DB
pipelines/        # flow Prefect (ingestion idempotente)
dashboard/        # Streamlit
```

La **règle de dépendance** est respectée : `api → usecases → domain`, jamais
l'inverse. Les adaptateurs concrets sont injectés dans l'API (`main.py`).

## Correspondance avec les milestones

- **M1** critères d'acceptation : F1 > 0.70 ✅, pipeline idempotent ✅,
  4 options exploitables ✅, model cards ✅, README + schéma ✅.
- **M2** risques : abstraction LLM + secours local (R3), sous-ensemble PlantNet (R2),
  clé de hachage + upsert = idempotence (R8), baseline-first (R9).
- **M3** specs : Prefect, MinIO/GCS via fsspec, PostgreSQL, MLflow, FastAPI, Streamlit, Docker, CI.
- **M5** modèle de données : ORM SQLAlchemy dans `infrastructure/models_orm.py`.
- **M6** roadmap IA : arbitrage A/B/C selon coût × sensibilité (voir `llm_gateway.py`).

## Ce qui doit être ajouté manuellement

Voir **[`SETUP_MANUEL.md`](SETUP_MANUEL.md)** — clé Gemini, images PlantNet,
PostgreSQL, MinIO/GCS, MLflow. Rien n'est requis pour la démo locale de base.

## Points à défendre en soutenance

- **Inférence (A) vs fine-tuning (B)** : l'Option A _appelle_ un LLM ; l'Option B
  _met à jour des poids_. Ne pas confondre.
- **Baseline-first** : chaque modèle est comparé à un baseline (Dummy pour C,
  pré-entraîné brut pour B).
- **Gouvernance = architecture** : la sensibilité des données (M5) dicte le choix
  d'option (M6) — sensible ⇒ interne/auto-hébergé, neutre ⇒ API externe autorisée.

```

```
