"""
Option B — Fine-tuning d'un MobileNetV2 pour la reconnaissance d'espèce.

Attendu du cahier des charges (M1) : démontrer une AMÉLIORATION de la métrique
APRÈS fine-tuning par rapport au baseline (le réseau pré-entraîné dont on
n'entraîne que la tête, voire un classifieur trivial).

>>> Point de vigilance ENTRETIEN <<<
Ici on FINE-TUNE (on met à jour des poids), on ne fait PAS que de l'inférence.
C'est la distinction inférence / fine-tuning à savoir défendre.

Organisation des images attendue (à fournir manuellement, cf. SETUP_MANUEL) :
    data/plantnet_subset/
        Monstera_deliciosa/ img1.jpg img2.jpg ...
        Ficus_lyrata/       ...
        ...  (5 à 10 espèces, cf. M2/R2 : jamais tout PlantNet-300K)

Si le dossier est absent, le script fabrique un MICRO-JEU SYNTHÉTIQUE (carrés
colorés) uniquement pour prouver que la boucle d'entraînement tourne. À
remplacer par le sous-ensemble PlantNet réel pour des résultats crédibles.

Usage :  python ml/train_vision.py --epochs 3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ARTIFACTS = Path("artifacts")
DATA_DIR = Path("data/plantnet_subset")


def _fabriquer_jeu_synthetique(root: Path, classes=4, par_classe=24):
    """Micro-jeu de démonstration si PlantNet n'est pas fourni."""
    import numpy as np
    from PIL import Image
    root.mkdir(parents=True, exist_ok=True)
    couleurs = [(60, 160, 70), (40, 120, 160), (170, 120, 60), (150, 70, 150)]
    for c in range(classes):
        d = root / f"espece_demo_{c}"
        d.mkdir(exist_ok=True)
        base = np.array(couleurs[c % len(couleurs)])
        for i in range(par_classe):
            noise = np.random.default_rng(c * 100 + i).integers(-30, 30, (64, 64, 3))
            arr = np.clip(base + noise, 0, 255).astype("uint8")
            Image.fromarray(arr).save(d / f"img_{i}.png")
    print(f"[demo] micro-jeu synthétique créé dans {root} "
          f"({classes} classes) — À REMPLACER par PlantNet.")


def main(epochs: int = 3, lr: float = 1e-3):
    import torch
    from torch import nn, optim
    from torch.utils.data import DataLoader, random_split
    from torchvision import datasets, models, transforms

    if not DATA_DIR.exists() or not any(DATA_DIR.iterdir()):
        _fabriquer_jeu_synthetique(DATA_DIR)

    tf = transforms.Compose([
        transforms.Resize((224, 224)), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    ds = datasets.ImageFolder(str(DATA_DIR), transform=tf)
    classes = ds.classes
    n_val = max(1, int(0.25 * len(ds)))
    train_ds, val_ds = random_split(ds, [len(ds) - n_val, n_val],
                                    generator=torch.Generator().manual_seed(42))
    train_dl = DataLoader(train_ds, batch_size=16, shuffle=True)
    val_dl = DataLoader(val_ds, batch_size=16)

    def build():
        net = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
        net.classifier[1] = nn.Linear(net.classifier[1].in_features, len(classes))
        return net

    def evaluate_metrics(net):
        from sklearn.metrics import f1_score, precision_score, recall_score
        net.eval()
        preds = []
        trues = []
        with torch.no_grad():
            for x, y in val_dl:
                p = net(x).argmax(1)
                preds.append(p.cpu().numpy())
                trues.append(y.cpu().numpy())
        import numpy as _np
        if preds:
            preds = _np.concatenate(preds)
            trues = _np.concatenate(trues)
        else:
            preds = _np.array([])
            trues = _np.array([])
        acc = float((preds == trues).mean()) if trues.size else 0.0
        f1 = float(f1_score(trues, preds, average="macro")) if trues.size else 0.0
        prec = float(precision_score(trues, preds, average="macro")) if trues.size else 0.0
        rec = float(recall_score(trues, preds, average="macro")) if trues.size else 0.0
        return dict(accuracy=acc, f1_macro=f1, precision_macro=prec, recall_macro=rec)

    # --- BASELINE : tête non entraînée (pré-entraîné brut) ----------------
    baseline_net = build()
    baseline_metrics = evaluate_metrics(baseline_net)
    acc_baseline = baseline_metrics["accuracy"]
    f1_baseline = baseline_metrics["f1_macro"]

    # --- FINE-TUNING : on entraîne toute la tête + dernières couches ------
    net = build()
    for p in net.features[:-3].parameters():  # gèle le début, affine la fin
        p.requires_grad = False
    opt = optim.Adam([p for p in net.parameters() if p.requires_grad], lr=lr)
    crit = nn.CrossEntropyLoss()
    for ep in range(epochs):
        net.train()
        for x, y in train_dl:
            opt.zero_grad()
            loss = crit(net(x), y)
            loss.backward()
            opt.step()
        finetune_metrics = evaluate_metrics(net)
        acc_ft = finetune_metrics["accuracy"]
        f1_ft = finetune_metrics["f1_macro"]
        print(f"  epoch {ep+1}/{epochs}  val_acc={acc_ft:.3f}")

    print(f"\n=== Vision (Option B) ===\n  baseline (pré-entraîné brut) : {acc_baseline:.3f} (F1={f1_baseline:.3f})"
        f"\n  après fine-tuning            : {acc_ft:.3f} (F1={f1_ft:.3f})"
        f"\n  amélioration                 : {'OUI' if acc_ft > acc_baseline else 'NON'} "
        f"({acc_ft - acc_baseline:+.3f})")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    torch.save(net.state_dict(), ARTIFACTS / "vision_mobilenet.pt")
    (ARTIFACTS / "vision_classes.json").write_text(json.dumps(classes))
    try:
        import mlflow
        mlflow.set_experiment("plantcare-vision")
        with mlflow.start_run(run_name="mobilenet_ft"):
            mlflow.log_metrics({
                "acc_baseline": acc_baseline,
                "acc_finetune": acc_ft,
                "f1_baseline": f1_baseline,
                "f1_finetune": f1_ft,
                "precision_finetune": finetune_metrics.get("precision_macro"),
                "recall_finetune": finetune_metrics.get("recall_macro"),
            })
    except Exception:
        pass
    print("Modèle vision sauvegardé dans", ARTIFACTS.resolve())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=1e-3)
    main(**vars(ap.parse_args()))
