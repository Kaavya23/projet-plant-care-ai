"""
Passerelle météo pour enrichir le prompt LLM avec le contexte local.

Implémentations :
  1. OpenWeatherMapGateway -> appelle l'API OpenWeatherMap Current Weather
  2. LocalWeatherGateway   -> repli sans réseau (retourne None)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import requests

_VALID_UNITS = {"standard", "metric", "imperial"}


@dataclass(frozen=True)
class MeteoSnapshot:
    latitude: float
    longitude: float
    temperature: float
    humidite_air: float
    conditions: str
    vitesse_vent: float | None
    precipitation_1h: float | None
    units: str
    source: str = "openweathermap"

    def _temperature_unit(self) -> str:
        if self.units == "imperial":
            return "degF"
        if self.units == "standard":
            return "K"
        return "degC"

    def resume_prompt(self) -> str:
        morceaux = [
            f"conditions : {self.conditions or 'non precisees'}",
            f"temperature exterieure {self.temperature:.1f} {self._temperature_unit()}",
            f"humidite {self.humidite_air:.0f} %",
        ]
        if self.vitesse_vent is not None:
            morceaux.append(f"vent {self.vitesse_vent:.1f} m/s")
        if self.precipitation_1h is not None:
            morceaux.append(f"precipitations 1h {self.precipitation_1h:.1f} mm")
        return ", ".join(morceaux)


class WeatherGateway(Protocol):
    def recuperer(self, latitude: float, longitude: float, units: str = "metric",
                  lang: str = "fr") -> MeteoSnapshot | None:
        ...

    def recuperer_par_ville(self, ville: str, units: str = "metric",
                            lang: str = "fr",
                            code_pays: str | None = None) -> MeteoSnapshot | None:
        ...


class LocalWeatherGateway:
    """Repli local : n'ajoute pas de contexte météo externe."""

    def recuperer(self, latitude: float, longitude: float, units: str = "metric",
                  lang: str = "fr") -> MeteoSnapshot | None:
        return None

    def recuperer_par_ville(self, ville: str, units: str = "metric",
                            lang: str = "fr",
                            code_pays: str | None = None) -> MeteoSnapshot | None:
        return None


class OpenWeatherMapGateway:
    def __init__(self, api_key: str,
                 base_url: str = "https://api.openweathermap.org/data/2.5/weather",
                 geocode_url: str = "https://api.openweathermap.org/geo/1.0/direct"):
        self.api_key = api_key
        self.base_url = base_url
        self.geocode_url = geocode_url

    def recuperer(self, latitude: float, longitude: float, units: str = "metric",
                  lang: str = "fr") -> MeteoSnapshot | None:
        try:
            units = units if units in _VALID_UNITS else "metric"
            resp = requests.get(
                self.base_url,
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "units": units,
                    "lang": lang,
                    "appid": self.api_key,
                },
                timeout=6,
            )
            resp.raise_for_status()
            data = resp.json()

            main = data.get("main", {})
            weather = data.get("weather", [])
            wind = data.get("wind", {})
            rain = data.get("rain", {})
            snow = data.get("snow", {})

            temp = float(main["temp"])
            humidite = float(main["humidity"])
            conditions = ""
            if weather and isinstance(weather, list):
                conditions = str(weather[0].get("description", "")).strip()

            precipitation = None
            if isinstance(rain, dict) and "1h" in rain:
                precipitation = float(rain["1h"])
            elif isinstance(snow, dict) and "1h" in snow:
                precipitation = float(snow["1h"])

            vitesse_vent = None
            if isinstance(wind, dict) and "speed" in wind:
                vitesse_vent = float(wind["speed"])

            return MeteoSnapshot(
                latitude=latitude,
                longitude=longitude,
                temperature=temp,
                humidite_air=humidite,
                conditions=conditions,
                vitesse_vent=vitesse_vent,
                precipitation_1h=precipitation,
                units=units,
                source="openweathermap",
            )
        except Exception:
            return None

    def recuperer_par_ville(self, ville: str, units: str = "metric",
                            lang: str = "fr",
                            code_pays: str | None = None) -> MeteoSnapshot | None:
        try:
            ville = (ville or "").strip()
            if not ville:
                return None

            query = ville
            if code_pays:
                query = f"{ville},{code_pays}"

            geo_resp = requests.get(
                self.geocode_url,
                params={
                    "q": query,
                    "limit": 1,
                    "appid": self.api_key,
                },
                timeout=6,
            )
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()
            if not isinstance(geo_data, list) or not geo_data:
                return None

            premier = geo_data[0]
            latitude = float(premier["lat"])
            longitude = float(premier["lon"])
            return self.recuperer(latitude=latitude, longitude=longitude,
                                 units=units, lang=lang)
        except Exception:
            return None


def obtenir_weather_gateway(api_key: str | None) -> WeatherGateway:
    if api_key:
        return OpenWeatherMapGateway(api_key=api_key)
    return LocalWeatherGateway()
