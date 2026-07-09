"""Configuration centralisée, pilotée par variables d'environnement (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()  # no-op si .env absent ; doit précéder les os.getenv() de Settings


@dataclass(frozen=True)
class Settings:
    # Base de service
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://plantcare:plantcare@localhost:5432/plantcare")
    # Datalake (abstraction fsspec : local | s3/minio | gcs)
    datalake_root: str = os.getenv("DATALAKE_ROOT", "./datalake")
    datalake_backend: str = os.getenv("DATALAKE_BACKEND", "local")  # local|minio|gcs
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    minio_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    # LLM (Option A)
    gcp_project: str | None = os.getenv("GCP_PROJECT")
    gcp_location: str = os.getenv("GCP_LOCATION", "europe-west1")
    # Meteo (OpenWeatherMap, Option A)
    openweather_api_key: str | None = os.getenv("OPENWEATHER_API_KEY")
    openweather_default_lat: float | None = (
        float(os.getenv("OPENWEATHER_DEFAULT_LAT"))
        if os.getenv("OPENWEATHER_DEFAULT_LAT")
        else None
    )
    openweather_default_lon: float | None = (
        float(os.getenv("OPENWEATHER_DEFAULT_LON"))
        if os.getenv("OPENWEATHER_DEFAULT_LON")
        else None
    )
    openweather_default_city: str | None = os.getenv("OPENWEATHER_DEFAULT_CITY")
    openweather_default_country: str | None = os.getenv("OPENWEATHER_DEFAULT_COUNTRY")
    openweather_default_units: str = os.getenv("OPENWEATHER_DEFAULT_UNITS", "metric")
    openweather_default_lang: str = os.getenv("OPENWEATHER_DEFAULT_LANG", "fr")
    # plant.health (Option D)
    plant_health_api_key: str | None = os.getenv("PLANT_HEALTH_API_KEY")
    # MLflow
    mlflow_uri: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


settings = Settings()
