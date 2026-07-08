"""Teste le critère d'acceptation F1 > 0.70 (M1) du modèle d'arrosage."""
import subprocess, sys, json
from pathlib import Path


def test_f1_au_dessus_du_seuil(tmp_path):
    # les artefacts sont produits par l'étape CI précédente
    meta = Path("ml/artifacts/watering_meta.json")
    if not meta.exists():
        subprocess.run([sys.executable, "ml/generate_synthetic_data.py"], check=True)
        subprocess.run([sys.executable, "ml/train_watering.py"], check=True)
    metrics = json.loads(meta.read_text())["metrics"]
    assert metrics["f1_macro"] > 0.70
    assert metrics["f1_macro"] > metrics["f1_baseline"]  # bat le baseline
