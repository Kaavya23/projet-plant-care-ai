# SETUP_MANUEL — ce que vous devez ajouter à la main

Le dépôt tourne **en local sans aucune clé** grâce aux données simulées et au
gabarit local de secours de l'Option A. Ce guide liste ce qu'il faut ajouter
**manuellement** pour activer chaque brique « pour de vrai ».

> Légende : 🟢 optionnel (le POC marche sans) · 🔴 requis pour la version « réelle »

---

## 0. Prérequis de base

```bash
python -m venv .venv && source .venv/bin/activate   # (Windows : .venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env        # puis éditez .env selon les sections ci-dessous
```

`torch`/`torchvision` sont volumineux (~2 Go). Si vous ne travaillez pas
l'Option B tout de suite, vous pouvez les commenter dans `requirements.txt`.

---

## 1. 🟢 Option A — Vertex AI Gemini (clé / credentials GCP)

Sans configuration, l'API répond via le **gabarit local** (`source: gabarit_local`).
Pour activer Gemini :

1. Créez un projet sur <https://console.cloud.google.com>.
2. Activez l'API **Vertex AI** (`Vertex AI API`).
3. Créez un **compte de service** → rôle _Vertex AI User_ → **générez une clé JSON**.
4. Déposez la clé dans `./secrets/gcp-key.json` (dossier déjà dans `.gitignore` — **ne jamais committer**).
5. Renseignez dans `.env` :
   ```
   GCP_PROJECT=votre-projet-gcp
   GCP_LOCATION=europe-west1
   GOOGLE_APPLICATION_CREDENTIALS=./secrets/gcp-key.json
   ```
6. Décommentez dans `requirements.txt` : `google-cloud-aiplatform` puis `pip install -r requirements.txt`.

Au prochain démarrage, `/health` affichera `"llm": "GeminiGateway"`.
En cas de quota/indispo, le repli local se fait tout seul (cf. M2/R3).

> 💡 Astuce démo : gardez un **cache** ou laissez le gabarit local activé le jour
> de la soutenance pour ne pas dépendre du réseau (R3).

---

## 1 bis. 🟢 Option A — Contexte météo OpenWeatherMap

Permet d'enrichir les conseils LLM avec la météo locale (température,
humidité, vent, pluie) à partir d'une latitude/longitude.

1. Créez une clé sur <https://openweathermap.org/api>.
2. Ajoutez dans `.env` :
   ```
   OPENWEATHER_API_KEY=votre_cle_ici
   OPENWEATHER_DEFAULT_LAT=48.8566
   OPENWEATHER_DEFAULT_LON=2.3522
   OPENWEATHER_DEFAULT_UNITS=metric
   OPENWEATHER_DEFAULT_LANG=fr
   ```
3. Dans le dashboard (onglet **Conseil**), activez l'option météo et renseignez
   votre position si besoin.

Les champs `temperature_jour` / `humidite_air_jour` restent modifiables :
s'ils sont fournis, ils ont priorité sur les valeurs OpenWeatherMap.

---

## 2. 🔴 Option B — sous-ensemble d'images PlantNet-300K

Le script `ml/train_vision.py` cherche `data/plantnet_subset/`. S'il est absent,
il fabrique un micro-jeu synthétique (juste pour prouver que ça tourne).
Pour des résultats crédibles :

1. Récupérez **5 à 10 espèces** depuis PlantNet-300K
   (miroir Hugging Face conseillé, en streaming — **ne téléchargez jamais les 32 Go**, cf. M2/R2).
2. Préparez un sous-ensemble dans le bon format avec :
   ```bash
   python ml/prepare_plantnet_subset.py --species Monstera deliciosa Ficus lyrata Sansevieria trifasciata --max-per-species 30
   ```
   Cela crée une arborescence compatible avec votre entraînement :
   ```
   data/plantnet_subset/
     Monstera_deliciosa/  img1.jpg img2.jpg ...
     Ficus_lyrata/        ...
     Sansevieria_trifasciata/ ...
   ```
3. Lancez : `python ml/train_vision.py --epochs 3`
4. Vérifiez que `acc_finetune > acc_baseline` (critère M1).

_(Le nom du dossier = le libellé d'espèce renvoyé par l'API.)_

---

## 3. 🟢 Open-Meteo (aucune clé)

L'API Open-Meteo est **gratuite et sans clé**. Rien à faire : le flow Prefect
l'interroge directement. Vérifiez juste votre accès réseau sortant.

---

## 4. 🟢 Datalake MinIO (au lieu du local)

Par défaut, le datalake écrit dans `./datalake` (backend `local`). Pour MinIO :

1. Démarrez MinIO (inclus dans `docker-compose.yml`) → console <http://localhost:9001>
   (identifiants `minioadmin` / `minioadmin`).
2. Créez un bucket (ex. `plantcare`).
3. Dans `.env` :
   ```
   DATALAKE_BACKEND=minio
   DATALAKE_ROOT=s3://plantcare
   ```

Pour GCS : `DATALAKE_BACKEND=gcs`, `DATALAKE_ROOT=gs://votre-bucket`, et
réutilisez les credentials GCP de la section 1.

---

## 5. 🔴 PostgreSQL (base de service)

- **Avec Docker** : `docker compose up postgres` suffit (déjà configuré).
- **Sans Docker** : installez PostgreSQL, créez la base et l'utilisateur,
  puis ajustez `DATABASE_URL` dans `.env`.
- Créez les tables + peuplez : `python ml/seed_db.py`
  (utilise `sql/schema.sql` comme référence).

---

## 6. 🟢 MLflow

- **Avec Docker** : `docker compose up mlflow` → UI <http://localhost:5000>.
- **Sans** : `pip install mlflow && mlflow server --port 5000`.
- Sans serveur, l'entraînement fonctionne quand même (journalisation ignorée).

---

## 7. 🟢 GCP — déploiement cloud (objectif « Could »)

Le déploiement GCP est un objectif secondaire (M1). L'infra est prévue en
Terraform (à ajouter dans `infra/` si vous allez jusque-là) et activable via
les **crédits gratuits**. Le POC reste entièrement démontrable en local (R4).

---

## Récapitulatif « à fournir »

| Élément                        | Où                                | Requis ?                  |
| ------------------------------ | --------------------------------- | ------------------------- |
| Clé JSON compte de service GCP | `./secrets/gcp-key.json` + `.env` | 🟢 (sinon gabarit local)  |
| Sous-ensemble PlantNet         | `data/plantnet_subset/<Espece>/`  | 🔴 pour Option B crédible |
| PostgreSQL                     | Docker ou local + `DATABASE_URL`  | 🔴 pour la persistance    |
| MinIO / GCS                    | Docker ou cloud + `.env`          | 🟢 (local par défaut)     |
| MLflow                         | Docker ou local                   | 🟢                        |
| Open-Meteo                     | rien (sans clé)                   | —                         |
