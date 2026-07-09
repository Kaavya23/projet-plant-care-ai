"""
Dashboard Streamlit — point d'entrée visuel du POC (cf. F8).

Trois onglets démontrent les trois options d'IA en appelant l'API FastAPI.
Configurable via API_URL (défaut : http://localhost:8000).

Lancement :  streamlit run dashboard/app.py
"""
from __future__ import annotations

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API = os.getenv("API_URL", "http://localhost:8000")


def _post_json(url: str, **kwargs):
    """Appelle l'API et retourne du JSON, sinon affiche une erreur lisible."""
    try:
        resp = requests.post(url, timeout=30, **kwargs)
        resp.raise_for_status()
    except requests.RequestException as err:
        st.error(f"Erreur API: {err}")
        if getattr(err, "response", None) is not None and err.response.text:
            st.code(err.response.text[:2000])
        return None

    try:
        return resp.json()
    except ValueError:
        st.error("La reponse de l'API n'est pas un JSON valide.")
        if resp.text:
            st.code(resp.text[:2000])
        return None

st.set_page_config(page_title="PlantCare AI", page_icon="🌿", layout="wide")
st.title("🌿 PlantCare AI — Assistant d'entretien des plantes")

try:
    h = requests.get(f"{API}/health", timeout=5).json()
    st.caption(f"API OK · modèle arrosage : {h['watering_model']} · "
               f"vision : {h['vision_model']} · LLM : {h['llm']}")
except Exception:
    st.error(f"API injoignable sur {API}. Lance d'abord l'API (uvicorn).")

especes = {
    "Monstera deliciosa": dict(id=1, lumiere=0.6, seuil_sol_sec=30),
    "Sansevieria trifasciata": dict(id=3, lumiere=0.4, seuil_sol_sec=20),
    "Calathea orbifolia": dict(id=6, lumiere=0.4, seuil_sol_sec=40),
}

tab_c, tab_a, tab_b, tab_d, tab_stats = st.tabs(
    ["💧 Arrosage (C)", "💬 Conseil (A)", "📷 Reconnaissance (B)", "🔬 Santé (D)",
     "📊 Statistiques"])

with tab_c:
    st.subheader("Recommandation d'arrosage — RandomForest maison")

    col = st.columns(2)
    nom = col[0].selectbox("Espèce", list(especes), key="c_esp")
    pot = col[0].slider("Taille du pot (cm)", 8, 30, 18)
    sol = col[1].slider("Humidité du sol (%)", 2, 95, 25)
    temp = col[1].slider("Température (°C)", 8, 38, 24)
    lux = col[0].slider("Luminosité (lux)", 50, 2000, 700)
    hum = col[1].slider("Humidité de l'air (%)", 15, 95, 50)
    jours = col[0].slider("Jours depuis dernier arrosage", 0, 12, 3)
    if st.button("Prédire l'arrosage", type="primary"):
        e = especes[nom]
        r = _post_json(f"{API}/api/v1/arrosage", json=dict(
            taille_pot=pot, espece=dict(id=e["id"], nom_sci=nom,
                lumiere=e["lumiere"], seuil_sol_sec=e["seuil_sol_sec"]),
            mesure=dict(sol=sol, temperature=temp, lux=lux, humidite_air=hum),
            jours_dernier_arrosage=jours))
        if r is None:
            st.stop()
        emoji = {"arroser_maintenant": "🚿", "verifier_prochainement": "👀",
                 "ne_pas_arroser": "✋"}.get(r["verdict"], "")
        st.metric(f"{emoji} Verdict", r["verdict"], f"confiance {r['confiance']:.0%}")
        st.info(r["explication"])

with tab_a:
    st.subheader("Conseil d'entretien — Gemini + secours local")
    nom2 = st.selectbox("Espèce", list(especes), key="a_esp")

    source_metriques = st.radio(
        "Choix de la température et de l'humidité du jour",
        [
            "Saisie manuelle",
            "Météo de votre ville",
        ],
        horizontal=True,
    )

    utilisation_sliders = source_metriques == "Saisie manuelle"
    tj = st.slider(
        "Température du jour (ajustable, °C)",
        8,
        38,
        32,
        disabled=not utilisation_sliders,
    )
    hj = st.slider(
        "Humidité de l'air du jour (ajustable, %)",
        15,
        95,
        40,
        disabled=not utilisation_sliders,
    )

    if utilisation_sliders:
        st.caption("Les sliders seront utilisés pour température/humidité du conseil.")
    else:
        st.caption(
            "La météo API sera prioritaire pour température/humidité. "
            "Les sliders sont ignorés."
        )

    villes = [
        "Paris",
        "Lyon",
        "Marseille",
        "Toulouse",
        "Lille",
        "Bordeaux",
        "Nantes",
        "Strasbourg",
        "Nice",
        "Montpellier",
    ]
    ville = st.selectbox("Ville", villes, index=0)

    meteo_payload = dict(ville=ville, units="metric", lang="fr")

    if st.button("Générer le conseil", type="primary"):
        e = especes[nom2]
        payload = dict(
            espece=dict(id=e["id"], nom_sci=nom2, lumiere=e["lumiere"],
                        seuil_sol_sec=e["seuil_sol_sec"]),
            mesure=dict(sol=20, temperature=tj, lux=700, humidite_air=hj),
        )
        if utilisation_sliders:
            payload["temperature_jour"] = tj
            payload["humidite_air_jour"] = hj
        payload["meteo"] = meteo_payload

        r = _post_json(f"{API}/api/v1/conseil", json=payload)
        if r is None:
            st.stop()
        st.markdown("## Resultat du conseil")
        st.success(r["conseil"])
        st.caption(f"Source LLM: {r['source']}")

        contexte = r.get("contexte_utilise", {})

        st.caption("Contexte utilise")
        ville_ret = ville
        if r.get("meteo") and r["meteo"].get("ville"):
            ville_ret = r["meteo"].get("ville")
        st.caption(
            f"Temperature retenue: {r['temperature_jour']:.1f} deg · "
            f"Humidite retenue: {r['humidite_air_jour']:.1f}% · "
            f"Ville retenue: {ville_ret}"
        )

with tab_b:
    st.subheader("Reconnaissance d'espèce — MobileNetV2 fine-tuné")
    photo = st.file_uploader("Photo de la plante", type=["jpg", "jpeg", "png"])
    if photo and st.button("Identifier", type="primary"):
        r = _post_json(f"{API}/api/v1/reconnaissance",
                       files={"fichier": (photo.name, photo.getvalue(),
                                          photo.type)})
        if r is None:
            st.stop()
        st.image(photo, width=280)
        st.metric("Espèce prédite", r["espece_predite"], f"score {r['score']:.0%}")
        for alt in r.get("alternatives", []):
            st.caption(f"alternative : {alt['espece']} ({alt['score']:.0%})")

with tab_d:
    st.subheader("Analyse de santé — plant.health (Kindwise)")
    st.caption(
        "Nécessite `PLANT_HEALTH_API_KEY` côté API. "
        "La photo est transmise à l'API Kindwise — voir RGPD."
    )
    photo_sante = st.file_uploader(
        "Photo montrant les symptômes",
        type=["jpg", "jpeg", "png", "webp"],
        key="d_photo",
    )
    if photo_sante is not None:
        st.image(photo_sante, caption="Image sélectionnée", width=400)
        if st.button("Analyser la santé", type="primary", key="d_btn"):
            try:
                with st.spinner("Analyse en cours..."):
                    r = requests.post(
                        f"{API}/api/v1/sante",
                        files={"fichier": (
                            photo_sante.name,
                            photo_sante.getvalue(),
                            photo_sante.type,
                        )},
                        timeout=40,
                    )
                    r.raise_for_status()
                    data = r.json()

                est_saine = data.get("est_saine")
                prob = data.get("probabilite_sante")

                st.subheader("État général")
                if est_saine is True:
                    st.success("La plante semble saine.")
                elif est_saine is False:
                    st.warning("La plante présente peut-être un problème.")
                else:
                    st.info(
                        "Résultat indisponible — "
                        "configurez `PLANT_HEALTH_API_KEY` dans l'environnement de l'API."
                    )

                if prob is not None:
                    st.write(f"Score de l'évaluation : {prob:.1%}")

                suggestions = data.get("suggestions", [])
                if suggestions:
                    st.subheader("Causes possibles")
                    for s in suggestions:
                        p = s.get("probabilite", 0)
                        with st.expander(f"{s['nom']} — {p:.1%}"):
                            if s.get("description"):
                                st.write(s["description"])
                            if s.get("traitement"):
                                st.markdown("**Conseils proposés :**")
                                st.write(s["traitement"])

            except requests.HTTPError as err:
                st.error(f"Erreur API HTTP {err.response.status_code}.")
                st.code(err.response.text)
            except requests.RequestException as err:
                st.error(f"Impossible de contacter l'API : {err}")

with tab_stats:
    st.subheader("Statistiques agrégées — couche Curated du datalake")
    st.caption(
        "Ces chiffres proviennent des fichiers `curated/` du datalake, "
        "produits par le pipeline Prefect (raw → staging → curated)."
    )

    if st.button("🔄 Recalculer les statistiques", type="primary", key="stats_refresh"):
        try:
            r = requests.post(f"{API}/api/v1/stats/refresh", timeout=30)
            r.raise_for_status()
            st.success("Statistiques recalculées depuis le datalake.")
        except requests.RequestException as err:
            st.error(f"Échec du recalcul : {err}")

    stats = None
    try:
        resp = requests.get(f"{API}/api/v1/stats", timeout=15)
        resp.raise_for_status()
        stats = resp.json()
    except requests.RequestException as err:
        st.error(f"Impossible de récupérer les statistiques : {err}")

    if stats is not None:
        import pandas as pd

        especes = pd.DataFrame(stats.get("especes", []))
        capteurs = pd.DataFrame(stats.get("capteurs", []))
        meteo = pd.DataFrame(stats.get("meteo", []))

        st.markdown("### 📷 Espèces les plus reconnues")
        if not especes.empty:
            especes = especes.rename(columns={
                "espece_predite": "Espèce",
                "n": "Nombre de reconnaissances",
                "score_moy": "Score moyen",
            })
            c1, c2 = st.columns([2, 1])
            c1.bar_chart(especes.set_index("Espèce")["Nombre de reconnaissances"])
            c2.dataframe(especes, hide_index=True, use_container_width=True)
        else:
            st.info("Aucune reconnaissance enregistrée pour l'instant.")

        st.markdown("### 🌦️ Météo moyenne par ville")
        if not meteo.empty:
            meteo = meteo.rename(columns={
                "ville": "Ville",
                "heure": "Heure",
                "temp_moy": "Température moyenne (°C)",
                "humidite_moy": "Humidité moyenne (%)",
                "vent_moy": "Vent moyen (km/h)",
                "pluie_tot": "Pluie cumulée (mm)",
            })
            st.dataframe(meteo, hide_index=True, use_container_width=True)
        else:
            st.info("Aucune donnée météo agrégée. Lance le flow Prefect.")

