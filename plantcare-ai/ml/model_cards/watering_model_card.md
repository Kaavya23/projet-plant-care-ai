# Model Card — Modèle d'arrosage (Option C)

## Objet
Prédire le verdict d'arrosage d'une plante d'intérieur parmi trois classes :
`arroser_maintenant`, `verifier_prochainement`, `ne_pas_arroser`.

## Modèle
- **Type** : RandomForest (300 arbres, `class_weight="balanced"`).
- **Choix** : interprétabilité (SHAP) et rapidité d'entraînement — cf. M3/M6.
- **Baseline de comparaison** : `DummyClassifier(most_frequent)` (réflexe M2/R9).

## Données
- Source : historique de soins + mesures capteurs + météo (simulés pour le POC).
- Features : `espece_id, taille_pot, sol, temperature, lux, humidite_air, seuil_sol_sec, jours_dernier_arrosage`.
- Cible construite par une règle agronomique bruitée (8 % de bruit d'étiquetage).
- Classe **Interne / Sensible** (habitudes) : traitement 100 % local, jamais
  externalisé (cf. M6).

## Performance (jeu de test, 25 %)
| Métrique | Valeur |
|---|---|
| F1 macro | ≈ 0.86 |
| F1 baseline | ≈ 0.20 |
| Accuracy | ≈ 0.87 |
| **Critère M1 (F1 > 0.70)** | **Satisfait** |

*(valeurs sur données simulées ; réentraîner sur données réelles met à jour ces chiffres.)*

## Interprétabilité
Importance des variables via SHAP (`TreeExplainer`), restituée dans
`watering_meta.json` et dans l'explication renvoyée par l'API.

## Limites
- Entraîné sur données simulées : à revalider sur données réelles.
- Ne remplace pas le jugement d'un jardinier ; verdict indicatif.

## Distinction à défendre
On **entraîne** ce modèle (apprentissage supervisé), on ne fait pas que de
l'inférence — contrairement à l'Option A (LLM appelé en inférence).
