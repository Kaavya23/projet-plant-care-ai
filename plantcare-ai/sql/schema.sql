-- Schéma PostgreSQL de service (dérivé du modèle conceptuel M5).
-- Les tables sont créées automatiquement par SQLAlchemy (init_db), ce fichier
-- sert de référence documentaire et de secours pour un déploiement manuel.

CREATE TABLE IF NOT EXISTS utilisateur (
    id               SERIAL PRIMARY KEY,
    email            VARCHAR NOT NULL,          -- SENSIBLE (RGPD)
    ville            VARCHAR,                    -- SENSIBLE (localisation)
    date_inscription DATE
);

CREATE TABLE IF NOT EXISTS espece (
    id            SERIAL PRIMARY KEY,
    nom_sci       VARCHAR NOT NULL,
    lumiere       REAL, humidite REAL,
    temp_min      REAL, temp_max REAL,
    seuil_sol_sec REAL DEFAULT 30.0
);

CREATE TABLE IF NOT EXISTS plante (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES utilisateur(id),
    espece_id   INTEGER REFERENCES espece(id),
    emplacement VARCHAR, taille_pot INTEGER, date_ajout DATE
);

CREATE TABLE IF NOT EXISTS historique_soin (
    id SERIAL PRIMARY KEY,
    plante_id INTEGER REFERENCES plante(id),
    type_action VARCHAR, date DATE, quantite REAL, photo_ref VARCHAR
);

CREATE TABLE IF NOT EXISTS mesure_capteur (
    id SERIAL PRIMARY KEY,
    plante_id INTEGER REFERENCES plante(id),
    humidite REAL, sol REAL, temperature REAL, lux REAL,
    horodatage TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS obs_meteo (
    id SERIAL PRIMARY KEY,
    ville VARCHAR, temp REAL, pluie REAL, vent REAL,
    horodatage TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recommandation (
    id SERIAL PRIMARY KEY,
    plante_id INTEGER REFERENCES plante(id),
    type VARCHAR, verdict VARCHAR, texte VARCHAR, confiance REAL,
    date TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analyse_image (
    id SERIAL PRIMARY KEY,
    plante_id INTEGER REFERENCES plante(id),
    espece_predite VARCHAR, score REAL, date TIMESTAMP DEFAULT now()
);
