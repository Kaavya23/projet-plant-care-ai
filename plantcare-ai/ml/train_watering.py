"""
Option C — Modèle maison de recommandation d'arrosage (RandomForest).

- Entraîne un RandomForest multi-classe (3 verdicts).
- Compare à un baseline DummyClassifier (réflexe baseline-first, cf. M2/R9).
- Évalue accuracy / precision / recall / F1 macro (imposé F1 > 0.70 dans M1).
- Calcule l'importance des variables via SHAP (interprétabilité, cf. M6).
- Journalise le run dans MLflow si disponible, sinon dégrade proprement.
- Sérialise le modèle + la liste des features dans ml/artifacts/.

Usage :  python ml/train_watering.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, classification_report, f1_score,
                             precision_score, recall_score)
from sklearn.model_selection import train_test_split

try:
    import joblib
except Exception:  # pragma: no cover
    from sklearn.externals import joblib  # type: ignore

FEATURES = ["espece_id", "taille_pot", "sol", "temperature", "lux",
            "humidite_air", "seuil_sol_sec", "jours_dernier_arrosage"]
TARGET = "verdict"
ARTIFACTS = Path("ml/artifacts")
DATA = Path("data/dataset_arrosage.csv")


def main() -> float:
    if not DATA.exists():
        raise SystemExit("Lance d'abord :  python ml/generate_synthetic_data.py")

    df = pd.read_csv(DATA)
    X, y = df[FEATURES], df[TARGET]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y)

    # --- baseline (réflexe M2) -------------------------------------------
    baseline = DummyClassifier(strategy="most_frequent").fit(X_tr, y_tr)
    f1_base = f1_score(y_te, baseline.predict(X_te), average="macro")

    # --- modèle -----------------------------------------------------------
    clf = RandomForestClassifier(
        n_estimators=300, max_depth=None, min_samples_leaf=2,
        class_weight="balanced", random_state=42, n_jobs=-1)
    clf.fit(X_tr, y_tr)
    pred = clf.predict(X_te)

    metrics = dict(
        accuracy=accuracy_score(y_te, pred),
        precision_macro=precision_score(y_te, pred, average="macro"),
        recall_macro=recall_score(y_te, pred, average="macro"),
        f1_macro=f1_score(y_te, pred, average="macro"),
        f1_baseline=f1_base,
    )

    print("\n=== Modèle d'arrosage (Option C) ===")
    for k, v in metrics.items():
        print(f"  {k:16s}: {v:.4f}")
    print("\n", classification_report(y_te, pred))
    seuil = 0.70
    ok = metrics["f1_macro"] > seuil
    print(f"Critère d'acceptation F1 > {seuil} : {'OK' if ok else 'ECHEC'} "
          f"(gain sur baseline : +{metrics['f1_macro'] - f1_base:.3f})")

    # --- interprétabilité SHAP -------------------------------------------
    try:
        import shap
        expl = shap.TreeExplainer(clf)
        sv = expl.shap_values(X_te.iloc[:200])
        arr = np.array(sv)
        # importance moyenne |SHAP| par feature, agrégée sur les classes
        imp = np.abs(arr).mean(axis=tuple(range(arr.ndim - 1)))
        importances = sorted(zip(FEATURES, imp.tolist()),
                             key=lambda t: t[1], reverse=True)
        print("\nFacteurs déterminants (|SHAP| moyen) :")
        for f, i in importances:
            print(f"  {f:24s}: {i:.4f}")
    except Exception as e:  # pragma: no cover
        importances = list(zip(FEATURES, clf.feature_importances_.tolist()))
        print("\nSHAP indisponible, repli sur feature_importances_ :", e)

    # --- MLflow (optionnel) ----------------------------------------------
    try:
        import mlflow
        mlflow.set_experiment("plantcare-arrosage")
        with mlflow.start_run(run_name="rf_watering"):
            mlflow.log_params(dict(n_estimators=300, min_samples_leaf=2))
            mlflow.log_metrics(metrics)
    except Exception as e:  # pragma: no cover
        print("\nMLflow non journalisé (démarre le serveur pour l'activer) :", e)

    # --- sérialisation ----------------------------------------------------
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, ARTIFACTS / "watering_rf.joblib")
    (ARTIFACTS / "watering_meta.json").write_text(json.dumps(
        dict(features=FEATURES, classes=list(clf.classes_),
             metrics=metrics,
             importances=[list(t) for t in importances]), indent=2))
    print("\nModèle sauvegardé dans", ARTIFACTS.resolve())
    return metrics["f1_macro"]


if __name__ == "__main__":
    main()
