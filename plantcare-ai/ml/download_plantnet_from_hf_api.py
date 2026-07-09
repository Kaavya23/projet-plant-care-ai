#!/usr/bin/env python3
"""Download PlantNet rows from Hugging Face datasets-server and save images.

Designed to run in Docker with HF_TOKEN / HUGGINGFACE_HUB_TOKEN provided via env.
"""
from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import re
import sys
import time
from pathlib import Path
from typing import Iterable

import requests


def sanitize_species_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", name.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "unknown"


def find_image_field(data: dict):
    """Return tuple (kind, value) where kind in {'bytes','url','path','raw'} or (None,None).
    Handles typical datasets-server row encodings and a few variants.
    """
    # direct image object like {"__type__": "image", "bytes": "...", "path": "..."}
    for k, v in data.items():
        if isinstance(v, dict) and v.get("__type__") == "image":
            if v.get("bytes"):
                return "bytes", v["bytes"]
            if v.get("path"):
                return "url", v["path"]
            if v.get("url"):
                return "url", v["url"]
    # fallback: keys that often contain url strings
    for k, v in data.items():
        if isinstance(v, str) and v.startswith("http") and any(v.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
            return "url", v
    # sometimes the image is nested under 'image' or 'img'
    for key in ("image", "img", "image_url"):
        v = data.get(key)
        if isinstance(v, dict) and v.get("__type__") == "image":
            return find_image_field({key: v})
        if isinstance(v, str) and v.startswith("http"):
            return "url", v
    return None, None


def download_bytes_from_image_field(val: str, headers: dict) -> bytes | None:
    # val can be base64 or a URL
    if val.startswith("data:"):
        # data URI
        comma = val.find(",")
        b64 = val[comma + 1 :]
        return base64.b64decode(b64)
    if re.match(r"^[A-Za-z0-9+/=\n]+$", val) and len(val) > 200:
        # likely base64
        try:
            return base64.b64decode(val)
        except Exception:
            pass
    # else treat as URL
    # add a few retries for image fetches too
    max_attempts = 4
    backoff = 0.5
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(val, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            if attempt < max_attempts:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None


def download_rows(
    output_dir: Path,
    species: Iterable[str] | None = None,
    max_per_species: int = 30,
    split: str = "train",
    start_offset: int = 0,
    page_length: int = 100,
    max_rows: int | None = None,
):
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    selected_species = list(species or [])
    if not selected_species:
        selected_species = ["Monstera deliciosa", "Ficus lyrata", "Sansevieria trifasciata"]

    counts: dict[str, int] = {}
    total_saved = 0
    offset = start_offset

    while True:
        if max_rows is not None and total_saved >= max_rows:
            break

        api = (
            "https://datasets-server.huggingface.co/rows?dataset=mikehemberger%2Fplantnet300K"
            f"&config=default&split={split}&offset={offset}&length={page_length}"
        )
        print(f"Requesting rows offset={offset} length={page_length}")
        # robust request with retries/backoff to handle transient 502/5xx from HF
        max_attempts = 5
        backoff = 1.0
        r = None
        # add browser-like headers to reduce chance of gateway/proxy issues
        headers_api = headers.copy()
        headers_api.setdefault("Accept", "application/json")
        headers_api.setdefault("User-Agent", "Mozilla/5.0 (compatible; PlantNetDownloader/1.0)")
        for attempt in range(1, max_attempts + 1):
            try:
                r = requests.get(api, headers=headers_api, timeout=60)
                r.raise_for_status()
                break
            except requests.exceptions.HTTPError as he:
                code = getattr(he.response, "status_code", None)
                # retry on 5xx
                if code and 500 <= code < 600 and attempt < max_attempts:
                    print(f"Server error {code}, retrying in {backoff}s... (attempt {attempt})", file=sys.stderr)
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                # log response body for debugging
                resp_body = None
                try:
                    resp_body = he.response.text
                except Exception:
                    resp_body = "<no body>"
                print("Request failed:", he, file=sys.stderr)
                print("Response body:", resp_body, file=sys.stderr)
                r = None
                break
            except Exception as exc:
                if attempt < max_attempts:
                    print(f"Request error, retrying in {backoff}s... (attempt {attempt})", file=sys.stderr)
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                print("Request failed:", exc, file=sys.stderr)
                r = None
                break

        payload = r.json()
        rows = payload.get("rows") or []
        if not rows:
            print("No more rows returned; stopping.")
            break

        for item in rows:
            if max_rows is not None and total_saved >= max_rows:
                break

            # normalize to data dict
            row = item.get("row") or item
            data = row.get("data") or row.get("row") or row

            # try to guess a species label from metadata
            species_name = None
            for k in ("scientificName", "species", "label", "taxon_name"):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    species_name = v
                    break
            if species_name is None:
                # sometimes label is integer index
                label = data.get("label")
                if isinstance(label, int):
                    species_name = selected_species[label % len(selected_species)]
                else:
                    species_name = str(label or "unknown")

            species_dir = output_dir / sanitize_species_name(species_name)
            species_dir.mkdir(parents=True, exist_ok=True)

            if counts.get(species_name, 0) >= max_per_species:
                continue

            kind, val = find_image_field(data)
            if kind is None:
                # no image found in this row
                continue

            img_bytes = None
            if kind == "bytes":
                try:
                    img_bytes = base64.b64decode(val)
                except Exception:
                    img_bytes = None
            elif kind == "url":
                img_bytes = download_bytes_from_image_field(val, headers)

            if not img_bytes:
                continue

            idx = counts.get(species_name, 0)
            fname = species_dir / f"{idx:04d}.jpg"
            try:
                with open(fname, "wb") as fh:
                    fh.write(img_bytes)
                counts[species_name] = counts.get(species_name, 0) + 1
                total_saved += 1
                if total_saved % 10 == 0:
                    print(f"Saved {total_saved} images so far")
            except Exception as exc:
                print("Failed to save image:", exc, file=sys.stderr)

        offset += page_length
        # small sleep to be polite / avoid rate limits
        time.sleep(0.5)

    print(f"Done — saved {total_saved} images in {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download PlantNet images from HF datasets-server into ImageFolder")
    parser.add_argument("--output-dir", default="data/plantnet_subset")
    parser.add_argument("--species", nargs="+", default=None)
    parser.add_argument("--max-per-species", type=int, default=30)
    parser.add_argument("--split", default="train")
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--page-length", type=int, default=100)
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    download_rows(
        output_dir=out,
        species=args.species,
        max_per_species=args.max_per_species,
        split=args.split,
        start_offset=args.start_offset,
        page_length=args.page_length,
        max_rows=args.max_rows,
    )


if __name__ == "__main__":
    main()
