"""
Abstraction du datalake via fsspec (cf. M3).

Le MÊME code manipule des chemins locaux, MinIO (S3) ou GCS selon la simple
variable d'environnement DATALAKE_BACKEND. Trois zones : raw / staging / curated.
"""
from __future__ import annotations

import fsspec

from plantcare.config import settings

ZONES = ("raw", "staging", "curated")


def _storage_options() -> dict:
    if settings.datalake_backend == "minio":
        return dict(key=settings.minio_key, secret=settings.minio_secret,
                    client_kwargs={"endpoint_url": settings.minio_endpoint})
    return {}


def chemin(zone: str, relatif: str) -> str:
    assert zone in ZONES, f"zone inconnue : {zone}"
    root = settings.datalake_root.rstrip("/")
    return f"{root}/{zone}/{relatif}"


def ecrire_bytes(data: bytes, zone: str, relatif: str) -> str:
    path = chemin(zone, relatif)
    with fsspec.open(path, "wb", **_storage_options()) as f:
        f.write(data)
    return path


def ecrire_parquet(df, zone: str, relatif: str) -> str:
    path = chemin(zone, relatif)
    of = fsspec.open(path, "wb", **_storage_options())
    with of as f:
        df.to_parquet(f, index=False)
    return path


def lire_parquet(zone: str, relatif: str):
    import pandas as pd
    path = chemin(zone, relatif)
    with fsspec.open(path, "rb", **_storage_options()) as f:
        return pd.read_parquet(f)
