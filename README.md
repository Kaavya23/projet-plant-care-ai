# 🌿 PlantCare AI — POC

Un assistant d'entretien de plantes d'intérieur démontrant plusieurs briques d'IA
dans une architecture modulaire (Clean Architecture). Ce dépôt est la
référence pour le projet *MSI-5-26-BD* (Tina, Kaavya, Nathan, Thomas).

Objectif : fournir un prototype reproductible localement pour comparer trois
approches IA et un module santé externe :

- Option A — Conseiller (LLM) : génération de conseils linguistiques (Gemini / gabarit local)
- Option B — Reconnaître : classification d'espèces par photo (MobileNetV2 fine-tuné)
- Option C — Anticiper : prédiction d'arrosage (RandomForest + SHAP)
- Option D — Santé : diagnostic externe via plant.health (Kindwise) avec repli stub

Le projet peut tourner en local sans clés externes (comportements de repli
pré-configurés). Voir `SETUP_MANUEL.md` pour activer des clés réelles (Gemini,
PlantNet, PlantHealth, etc.).

## Table des options (résumé)

| Option              | Fonction                               | Brique                                                | Donnée / RGPD                    |
|--------------------:|:---------------------------------------|:------------------------------------------------------|:---------------------------------|
| **A — Conseiller**  | conseil d'entretien en langage naturel | Vertex AI / Gemini (optionnel) + gabarit local        | payload pseudonymisé             |
| **B — Reconnaître** | espèce à partir d'une photo            | MobileNetV2 fine-tuné                                 | photo sensible → 100 % local     |
| **C — Anticiper**   | verdict d'arrosage                     | RandomForest maison + SHAP                             | habitudes → jamais externalisées |
| **D — Santé**       | diagnostic de santé (tierce partie)    | plant.health / Kindwise (API externe) + repli stub    | photo sensible → consent requis  |

## Démarrage rapide

Local (sans Docker) — recommandé pour développement rapide :

```bash
cd plantcare-ai
pip install -r requirements.txt
make data        # génère les données simulées
make prepare-plantnet  # (optionnel) crée un sous-ensemble PlantNet local
make train-c     # entraîne le modèle d'arrosage (option C)
make train-b     # fine-tune la vision (option B)
make api         # lance l'API FastAPI  -> http://localhost:8000/docs
make dash        # lance le dashboard Streamlit -> http://localhost:8501
make test        # lance les tests unitaires
```

Avec Docker (stack complète) :

```bash
cd plantcare-ai
docker compose up --build
# API 8000 · Dashboard 8501 · PostgreSQL 5432 · MinIO 9000/9001 · MLflow 5000
```

Remarques pratiques :
- Pour récupérer un sous-ensemble PlantNet depuis Hugging Face, utilisez
  `ml/download_plantnet_from_hf_api.py` (script Docker-friendly fourni).
- L'authentification HF utilise `HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN`.

## Commandes utiles

- Préparer PlantNet (local, limité) :
  `python ml/prepare_plantnet_subset.py --species Monstera deliciosa Ficus lyrata --max-per-species 30`
- Nouvelle méthode (datasets-server) :
  `python ml/download_plantnet_from_hf_api.py --max-per-species 50 --max-rows 500`
- Entraîner vision : `python ml/train_vision.py --epochs 3`
- Entraîner watering : `python ml/train_watering.py`

## Architecture (aperçu)

Clean Architecture — séparation nette des responsabilités :

```
ROOT/
├─ artifacts/         # Artifacts (modèles, etc.)
├─ notebooks/         # Analyse end to end de toutes les fonctionnalités de PlantCareAI
├─ sql/               # Scripts de schéma de base de données PostgreSQL
├─ src/plantcare/
│  ├─ domain/         # entités pures (aucune dépendance externe)
│  ├─ usecases/       # orchestration + logique métier
│  ├─ adapters/       # implémentations concrètes : llm_gateway, vision_model, watering_model, plant_health_gateway
│  ├─ infrastructure/ # db (SQLAlchemy), datalake (fsspec), ORM
+│  └─ api/            # FastAPI composition root + routes
├─ ml/                # scripts d'entraînement, préparation de données, model cards
├─ pipelines/         # Prefect flows (ingestion, ETL)
└─ dashboard/         # Streamlit app (UI)
```

Diagramme logique (simplifié):

```mermaid
graph LR
  User -->|Upload / Request| API[FastAPI]
  API --> Usecases
  Usecases --> Domain
  Usecases --> Adapters
  Adapters -->|A| LLM[Gemini/Gabarit]
  Adapters -->|B| Vision[MobileNetV2]
  Adapters -->|C| Watering[RandomForest]
  Adapters -->|D| PlantHealth[plant.health]
  API --> DB[(PostgreSQL)]
  API --> Datalake[FSSpec/MinIO]
```

## Données sources

- Données simulées : génération locale via `ml/generate_synthetic_data.py` (utilisée
  pour la partie C et le datalake de démonstration).
- Sous-ensemble PlantNet-300K : recommandé via streaming Hugging Face
  (ne pas télécharger l'ensemble complet de 32 GB). Le format attendu par
  `ml/train_vision.py` : `data/plantnet_subset/<Espece>/*.jpg`.
- Météo : Open-Meteo / OpenWeather (optionnel) — API sans clé pour Open-Meteo.

## Variables d'environnement importantes

- `HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN` — token Hugging Face pour datasets privés.
- `PLANT_HEALTH_API_KEY` — clé plant.health pour l'option D (facultative).
- `GEMINI_API_KEY` / `GOOGLE_APPLICATION_CREDENTIALS` — clés pour Option A (si utilisée).
- `DATABASE_URL`, `MINIO_*`, `MLFLOW_TRACKING_URI` — configs d'infrastructure.

Exemple `.env` (déjà présent dans le dépôt avec placeholder) :

```
DATABASE_URL=postgresql+psycopg2://plantcare:plantcare@localhost:5432/plantcare
DATALAKE_BACKEND=local
HF_TOKEN=hf_xxx
PLANT_HEALTH_API_KEY=
GEMINI_API_KEY=
MLFLOW_TRACKING_URI=http://localhost:5000
```

## Tests & qualité

- `make test` exécute les tests unitaires (pytest). Les tests incluent des
  vérifications du sous-ensemble PlantNet, des transformations et du service API.

## Observabilité & suivi

- MLflow : utilisé pour tracer les runs ML (voir `ml/train_vision.py` et `ml/train_watering.py`).
- Logs : l'API utilise la configuration standard `uvicorn`/`logging`.

## À surveiller / risques

- PlantNet : éviter le téléchargement massif (streaming conseillé).
- LLMs : coûts et disponibilité (prévoir repli local, cf. `llm_gateway.py`).
- Données sensibles : photos, métadonnées EXIF — prétraiter ou anonymiser.

## Contribution & déploiement

- Structure de contribution : ouvrir une branche `feature/...`, tests, PR.
- Déploiement : conteneurisation via `Dockerfile` + `docker-compose.yml`.

## Ressources & références

- `SETUP_MANUEL.md` — procédures d'activation des clés externes et détails d'installation.
- `ml/model_cards/` — model cards pour les artefacts entraînés.
