"""Teste les routes de l'API (le fallback local rend le test hermétique)."""
from fastapi.testclient import TestClient
from plantcare.api.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_arrosage_cas_sec_chaud():
    r = client.post("/api/v1/arrosage", json={
        "espece": {"id": 1, "nom_sci": "Monstera deliciosa", "seuil_sol_sec": 30},
        "mesure": {"sol": 8, "temperature": 34, "lux": 800, "humidite_air": 35},
        "jours_dernier_arrosage": 7})
    assert r.status_code == 200
    assert r.json()["verdict"] == "arroser_maintenant"


def test_conseil_a_une_source():
    r = client.post("/api/v1/conseil", json={
        "espece": {"id": 1, "nom_sci": "Monstera deliciosa"},
        "mesure": {"sol": 20, "temperature": 32, "lux": 700, "humidite_air": 40},
        "temperature_jour": 32, "humidite_air_jour": 40})
    assert r.json()["source"] in ("gemini", "gabarit_local")
