"""
Option B — adaptateur d'inférence du modèle de vision.

Charge le MobileNetV2 fine-tuné par ml/train_vision.py et prédit l'espèce à
partir d'une image. Si torch ou l'artefact ne sont pas disponibles (ex. CI
légère), un repli renvoie une prédiction factice signalée comme telle, afin
que l'API reste démarrable.

RGPD : l'inférence est 100 % locale ; la photo de l'utilisateur ne quitte
jamais le système (cf. M6, aucune API de vision externe).
"""
from __future__ import annotations

import json
from pathlib import Path

from plantcare.domain.entities import AnalyseImage

ARTIFACTS = Path("artifacts")


class VisionModel:
    def __init__(self, artifacts_dir: Path = ARTIFACTS):
        self.model = None
        self.classes: list[str] = []
        self._tf = None
        weights = artifacts_dir / "vision_mobilenet.pt"
        classes_path = artifacts_dir / "vision_classes.json"
        if weights.exists() and classes_path.exists():
            self._charger(weights, classes_path)

    def _charger(self, weights: Path, classes_path: Path) -> None:
        try:
            import torch
            from torchvision import models, transforms
            self.classes = json.loads(classes_path.read_text())
            net = models.mobilenet_v2(weights=None)
            net.classifier[1] = torch.nn.Linear(
                net.classifier[1].in_features, len(self.classes))
            net.load_state_dict(torch.load(weights, map_location="cpu"))
            net.eval()
            self.model = net
            self._tf = transforms.Compose([
                transforms.Resize((224, 224)), transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406],
                                     [0.229, 0.224, 0.225])])
        except Exception:
            self.model = None

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def predire(self, image_bytes: bytes, top_k: int = 3) -> AnalyseImage:
        if not self.is_loaded:
            return AnalyseImage(espece_predite="(modèle vision non chargé)",
                                score=0.0, alternatives=[])
        import io
        import torch
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        x = self._tf(img).unsqueeze(0)
        with torch.no_grad():
            probs = torch.softmax(self.model(x), dim=1)[0]
        vals, idx = torch.topk(probs, min(top_k, len(self.classes)))
        pairs = [(self.classes[i], float(v)) for v, i in zip(vals, idx)]
        return AnalyseImage(espece_predite=pairs[0][0], score=pairs[0][1],
                            alternatives=pairs[1:])
