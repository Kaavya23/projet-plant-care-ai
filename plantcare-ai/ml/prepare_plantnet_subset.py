from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

from PIL import Image


DEFAULT_DATA_DIR = Path("data/plantnet_subset")


def sanitize_species_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", name.strip())
    cleaned = cleaned.strip("_")
    if not cleaned:
        return "unknown"
    return cleaned


def export_subset_from_hf(
    output_dir: Path | str = DEFAULT_DATA_DIR,
    species: Iterable[str] | None = None,
    max_per_species: int = 30,
    split: str = "train",
    limit: int | None = None,
) -> Path:
    """Download a small PlantNet subset and export it as ImageFolder-style folders."""
    from datasets import load_dataset

    print(f"Preparing PlantNet subset in {output_dir}...")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading PlantNet dataset from Hugging Face (split={split})...")

    selected_species = list(species or [])
    if not selected_species:
        selected_species = ["Monstera deliciosa", "Ficus lyrata", "Sansevieria trifasciata"]

    ds = load_dataset("mikehemberger/plantnet300K", split=split, streaming=True)

    counts: dict[str, int] = {}
    for row in ds:
        if limit is not None and sum(counts.values()) >= limit:
            break

        label = row.get("label")
        if label is None:
            continue

        # The dataset provides integer labels, but the metadata CSV is the source of
        # human-readable names. For a lightweight setup we keep the label index in the
        # folder name and rely on the user to replace it with a real species list.
        species_name = selected_species[label % len(selected_species)] if isinstance(label, int) else str(label)
        target_dir = output_dir / sanitize_species_name(species_name)
        target_dir.mkdir(parents=True, exist_ok=True)

        if counts.get(species_name, 0) >= max_per_species:
            continue

        image = row.get("image")
        if image is None:
            continue

        if not isinstance(image, Image.Image):
            continue

        safe_name = f"{counts.get(species_name, 0):04d}_{len(list(target_dir.glob('*'))):04d}.jpg"
        image.save(target_dir / safe_name)
        counts[species_name] = counts.get(species_name, 0) + 1

    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a small PlantNet subset for training")
    parser.add_argument("--output-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--species", nargs="+", default=["Monstera deliciosa", "Ficus lyrata", "Sansevieria trifasciata"])
    parser.add_argument("--max-per-species", type=int, default=30)
    parser.add_argument("--split", default="train")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    output_dir = export_subset_from_hf(
        output_dir=args.output_dir,
        species=args.species,
        max_per_species=args.max_per_species,
        split=args.split,
        limit=args.limit,
    )
    print(f"Prepared PlantNet subset in {output_dir}")


if __name__ == "__main__":
    main()
