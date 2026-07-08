"""Configuration centralisée, pilotée par variables d'environnement (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass


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
    # MLflow
    mlflow_uri: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


settings = Settings()
