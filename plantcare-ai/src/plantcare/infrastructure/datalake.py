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


def ecrire_csv(df, zone: str, relatif: str) -> str:
    path = chemin(zone, relatif)
    of = fsspec.open(path, "w", encoding="utf-8", **_storage_options())
    with of as f:
        df.to_csv(f, index=False)
    return path


def lire_csv(zone: str, relatif: str):
    import pandas as pd
    path = chemin(zone, relatif)
    with fsspec.open(path, "r", encoding="utf-8", **_storage_options()) as f:
        return pd.read_csv(f)


def lire_csv_glob(zone: str, motif: str = "**/*.csv"):
    """Lit et concatène tous les CSV correspondant au motif dans une zone."""
    import pandas as pd
    pattern = chemin(zone, motif)
    dfs = []
    for of in fsspec.open_files(pattern, "r", encoding="utf-8", **_storage_options()):
        with of as f:
            dfs.append(pd.read_csv(f))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
