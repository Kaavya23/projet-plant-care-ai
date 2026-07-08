# Model Card — Modèle de vision (Option B)

## Objet
Reconnaître l'espèce d'une plante à partir d'une photo (5 à 10 espèces).

## Modèle
- **Type** : MobileNetV2 pré-entraîné (ImageNet) puis **fine-tuné**.
- **Choix** : légèreté → fine-tuning possible même sans GPU (cf. M2/R2, M3).
- **Stratégie** : gel des premières couches, entraînement de la tête + dernières
  couches de `features`.

## Données
- Entraînement : sous-ensemble de **PlantNet-300K** (5–10 espèces), jamais le
  jeu complet (32 Go) — cf. M2/R2.
- Inférence : photo utilisateur = donnée **Sensible**, traitée **localement**,
  jamais envoyée à une API de vision externe (cf. M6).
- Arborescence attendue : `data/plantnet_subset/<Espece>/*.jpg`.

## Performance
Critère M1 : démontrer une **amélioration après fine-tuning** vs baseline
(réseau pré-entraîné brut). Le script `train_vision.py` journalise
`acc_baseline` et `acc_finetune` (MLflow).

*(Un micro-jeu synthétique de secours prouve que la boucle tourne ; les chiffres
crédibles s'obtiennent avec le sous-ensemble PlantNet réel.)*

## Distinction à défendre
Ici on **fine-tune** (mise à jour de poids), pas seulement de l'inférence.
C'est le point inférence vs fine-tuning à ne pas confondre.

## Limites
- Restreint aux espèces vues à l'entraînement.
- Sensible à la qualité/éclairage de la photo.
