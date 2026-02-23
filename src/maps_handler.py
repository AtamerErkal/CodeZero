"""
Maps Handler Module
===================
Provides geolocation and routing services via Azure Maps. Dynamically
discovers the nearest hospitals with ER capability and calculates ETA
from patient location using real-time traffic data.

AI-102 Concepts:
  - Azure Maps Route API for ETA calculation
  - Azure Maps Search POI for discovering nearby hospitals
  - Geolocation services integration
  - Real-time traffic-aware routing
"""

from __future__ import annotations

import logging
import math
import os
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback hospital database (demo / offline mode)
# When Azure Maps is not available, the system selects the nearest 3
# from this global list using Haversine distance.  Covers several
# cities so demos work regardless of the chosen patient location.
# ---------------------------------------------------------------------------
_DEFAULT_FALLBACK_HOSPITALS: list[dict] = [
    # Germany – Stuttgart area
    {
        "name": "Klinikum Stuttgart – Katharinenhospital (ER)",
        "lat": 48.7823,
        "lon": 9.1749,
        "address": "Kriegsbergstraße 60, 70174 Stuttgart, Germany",
    },
    {
        "name": "Robert-Bosch-Krankenhaus (ER)",
        "lat": 48.7944,
        "lon": 9.2198,
        "address": "Auerbachstraße 110, 70376 Stuttgart, Germany",
    },
    {
        "name": "Marienhospital Stuttgart (ER)",
        "lat": 48.7647,
        "lon": 9.1632,
        "address": "Böheimstraße 37, 70199 Stuttgart, Germany",
    },
    # Germany – Tübingen
    {
        "name": "Universitätsklinikum Tübingen (ER)",
        "lat": 48.5355,
        "lon": 9.0396,
        "address": "Hoppe-Seyler-Straße 3, 72076 Tübingen, Germany",
    },
    # Germany – Munich
    {
        "name": "Klinikum rechts der Isar (ER)",
        "lat": 48.1372,
        "lon": 11.5995,
        "address": "Ismaninger Str. 22, 81675 München, Germany",
    },
    # Turkey – Istanbul
    {
        "name": "Istanbul University Hospital (ER)",
        "lat": 41.0082,
        "lon": 28.9784,
        "address": "Fatih, Istanbul, Turkey",
    },
    {
        "name": "Cerrahpaşa Medical Faculty (ER)",
        "lat": 41.0040,
        "lon": 28.9510,
        "address": "Cerrahpaşa, Fatih, Istanbul, Turkey",
    },
    {
        "name": "Şişli Hamidiye Etfal Hospital (ER)",
        "lat": 41.0600,
        "lon": 28.9870,
        "address": "Şişli, Istanbul, Turkey",
    },
    # USA – New York
    {
        "name": "Bellevue Hospital Center (ER)",
        "lat": 40.7392,
        "lon": -73.9754,
        "address": "462 1st Ave, New York, NY 10016, USA",
    },
    {
        "name": "NYU Langone Health (ER)",
        "lat": 40.7421,
        "lon": -73.9739,
        "address": "550 1st Ave, New York, NY 10016, USA",
    },
    {
        "name": "Mount Sinai Hospital (ER)",
        "lat": 40.7900,
        "lon": -73.9526,
        "address": "1 Gustave L. Levy Pl, New York, NY 10029, USA",
    },
    # France – Paris
    {
        "name": "Hôpital Necker – Enfants Malades (ER)",
        "lat": 48.8462,
        "lon": 2.3155,
        "address": "149 Rue de Sèvres, 75015 Paris, France",
    },
    # Spain – Barcelona
    {
        "name": "Hospital Clínic de Barcelona (ER)",
        "lat": 41.3882,
        "lon": 2.1522,
        "address": "C/ de Villarroel, 170, Barcelona, Spain",
    },
    # UK – London
    {
        "name": "St Thomas' Hospital (ER)",
        "lat": 51.4985,
        "lon": -0.1177,
        "address": "Westminster Bridge Rd, London SE1 7EH, UK",
    },
    # Saudi Arabia – Riyadh
    {
        "name": "King Faisal Specialist Hospital (ER)",
        "lat": 24.6682,
        "lon": 46.6773,
        "address": "Al Mathar Ash Shamali, Riyadh, Saudi Arabia",
    },
]


class MapsHandler:
    """Handles dynamic hospital discovery and route / ETA calculation.

    Instead of routing to a single fixed hospital, this handler
    discovers the nearest hospitals with ER capability based on the
    patient's real-time GPS location and calculates an ETA for each.
    The patient then chooses which hospital to go to.

    With Azure Maps credentials:
      - Azure Maps Search POI discovers real nearby hospitals
      - Azure Maps Route Directions gives traffic-aware ETA

    Without Azure Maps credentials (demo mode):
      - Built-in fallback hospital list (multi-city)
      - Haversine distance + average speed for ETA estimation

    Attributes:
        subscription_key: Azure Maps subscription key.
    """

    def __init__(self) -> None:
        """Initialize the Maps Handler with Azure credentials."""
        self.subscription_key: str = os.getenv("MAPS_SUBSCRIPTION_KEY", "")
        self._initialized = bool(
            self.subscription_key and self.subscription_key != "your-key"
        )

        if not self._initialized:
            logger.warning(
                "Azure Maps credentials not configured. "
                "Using fallback hospital list and estimated ETA."
            )
        else:
            logger.info("Azure Maps initialized.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_nearest_hospitals(
        self,
        patient_lat: float,
        patient_lon: float,
        count: int = 3,
        radius_km: int = 50,
    ) -> list[dict]:
        """Find the nearest hospitals with ER capability and calculate ETA.

        AI-102: Azure Maps Search POI API discovers hospitals near a
        given location.  Results are enriched with ETA from the Route
        Directions API, then sorted fastest-first.

        Args:
            patient_lat: Patient's latitude.
            patient_lon: Patient's longitude.
            count: Number of hospitals to return (default 3).
            radius_km: Search radius in kilometres.

        Returns:
            List of hospital dicts sorted by ETA (fastest first), each
            containing: name, lat, lon, address, distance_km, eta_minutes,
            traffic_delay_minutes, route_summary, source.
        """
        if self._initialized:
            hospitals = self._azure_search_hospitals(
                patient_lat, patient_lon, count, radius_km
            )
        else:
            hospitals = self._fallback_search_hospitals(
                patient_lat, patient_lon, count
            )

        # Enrich each hospital with ETA
        for h in hospitals:
            eta = self.calculate_eta_to_hospital(
                patient_lat, patient_lon, h["lat"], h["lon"]
            )
            h["eta_minutes"] = eta["eta_minutes"]
            h["distance_km"] = eta["distance_km"]
            h["traffic_delay_minutes"] = eta.get("traffic_delay_minutes", 0)
            h["route_summary"] = eta["route_summary"]
            h["source"] = eta["source"]

        # Sort by ETA (fastest first)
        hospitals.sort(key=lambda x: x["eta_minutes"])

        logger.info(
            "Returning %d nearest hospitals for (%.4f, %.4f).",
            len(hospitals),
            patient_lat,
            patient_lon,
        )
        return hospitals

    def calculate_eta_to_hospital(
        self,
        patient_lat: float,
        patient_lon: float,
        hospital_lat: float,
        hospital_lon: float,
    ) -> dict:
        """Calculate ETA from patient location to a specific hospital.

        AI-102: Azure Maps Route Directions API provides turn-by-turn
        directions with real-time traffic data.

        Args:
            patient_lat: Patient's latitude.
            patient_lon: Patient's longitude.
            hospital_lat: Target hospital latitude.
            hospital_lon: Target hospital longitude.

        Returns:
            Dict with eta_minutes, distance_km, traffic_delay_minutes,
            route_summary, source.
        """
        if self._initialized:
            return self._azure_maps_eta(
                patient_lat, patient_lon, hospital_lat, hospital_lon
            )
        return self._fallback_eta(
            patient_lat, patient_lon, hospital_lat, hospital_lon
        )

    # ------------------------------------------------------------------
    # Azure Maps hospital search
    # ------------------------------------------------------------------

    def _azure_search_hospitals(
        self,
        patient_lat: float,
        patient_lon: float,
        count: int,
        radius_km: int,
    ) -> list[dict]:
        """Search for nearby hospitals using Azure Maps Search POI API.

        AI-102: The Search POI endpoint finds points of interest by
        category and keyword, with geographic bias.  CategorySet 7321
        corresponds to hospitals.

        Args:
            patient_lat: Patient latitude.
            patient_lon: Patient longitude.
            count: Max results.
            radius_km: Search radius.

        Returns:
            List of hospital dicts (ETA added later by the caller).
        """
        try:
            url = "https://atlas.microsoft.com/search/poi/json"
            params = {
                "subscription-key": self.subscription_key,
                "api-version": "1.0",
                "query": "hospital emergency",
                "lat": patient_lat,
                "lon": patient_lon,
                "radius": radius_km * 1000,  # metres
                "limit": count * 2,  # fetch extra in case some lack ER
                "categorySet": "7321",  # Hospital / polyclinic
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            hospitals: list[dict] = []
            for result in data.get("results", []):
                pos = result.get("position", {})
                hospitals.append(
                    {
                        "name": result.get("poi", {}).get("name", "Hospital"),
                        "lat": pos.get("lat", 0),
                        "lon": pos.get("lon", 0),
                        "address": result.get("address", {}).get(
                            "freeformAddress", ""
                        ),
                        "distance_km": round(result.get("dist", 0) / 1000, 1),
                    }
                )

            logger.info(
                "Azure Maps found %d hospitals near (%.4f, %.4f).",
                len(hospitals),
                patient_lat,
                patient_lon,
            )
            return hospitals[:count]

        except Exception as exc:
            logger.error("Azure hospital search error: %s", exc)
            return self._fallback_search_hospitals(
                patient_lat, patient_lon, count
            )

    # ------------------------------------------------------------------
    # Fallback hospital search (demo / offline mode)
    # ------------------------------------------------------------------

    def _fallback_search_hospitals(
        self,
        patient_lat: float,
        patient_lon: float,
        count: int = 3,
    ) -> list[dict]:
        """Find nearest hospitals from the built-in fallback list.

        Uses Haversine distance to rank the static hospital database by
        proximity to the patient's location.

        Args:
            patient_lat: Patient latitude.
            patient_lon: Patient longitude.
            count: Number of hospitals to return.

        Returns:
            Nearest hospitals from the fallback list.
        """
        scored: list[dict] = []
        for h in _DEFAULT_FALLBACK_HOSPITALS:
            dist = self._haversine_distance(
                patient_lat, patient_lon, h["lat"], h["lon"]
            )
            scored.append(
                {
                    "name": h["name"],
                    "lat": h["lat"],
                    "lon": h["lon"],
                    "address": h.get("address", ""),
                    "distance_km": round(dist, 1),
                }
            )

        scored.sort(key=lambda x: x["distance_km"])
        nearest = scored[:count]
        logger.info(
            "Fallback search: %d nearest hospitals (closest: %s, %.1f km).",
            len(nearest),
            nearest[0]["name"] if nearest else "N/A",
            nearest[0]["distance_km"] if nearest else 0,
        )
        return nearest

    # ------------------------------------------------------------------
    # Azure Maps route ETA
    # ------------------------------------------------------------------

    def _azure_maps_eta(
        self,
        patient_lat: float,
        patient_lon: float,
        hospital_lat: float,
        hospital_lon: float,
    ) -> dict:
        """Calculate ETA using Azure Maps Route Directions API.

        AI-102: The Route Directions API supports:
        - Real-time traffic (departAt=now)
        - Multiple route alternatives
        - Travel time with / without traffic delays
        """
        try:
            url = "https://atlas.microsoft.com/route/directions/json"
            params = {
                "subscription-key": self.subscription_key,
                "api-version": "1.0",
                "query": (
                    f"{patient_lat},{patient_lon}:"
                    f"{hospital_lat},{hospital_lon}"
                ),
                "traffic": "true",
                "departAt": "now",
                "travelMode": "car",
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            routes = data.get("routes", [])
            if not routes:
                logger.warning("No routes returned from Azure Maps.")
                return self._fallback_eta(
                    patient_lat, patient_lon, hospital_lat, hospital_lon
                )

            summary = routes[0].get("summary", {})
            eta_seconds = summary.get("travelTimeInSeconds", 0)
            distance_meters = summary.get("lengthInMeters", 0)
            traffic_delay = summary.get("trafficDelayInSeconds", 0)

            return {
                "eta_minutes": max(1, round(eta_seconds / 60)),
                "distance_km": round(distance_meters / 1000, 1),
                "traffic_delay_minutes": round(traffic_delay / 60),
                "route_summary": (
                    f"{round(distance_meters / 1000, 1)} km, "
                    f"~{max(1, round(eta_seconds / 60))} min"
                ),
                "source": "azure_maps",
            }

        except Exception as exc:
            logger.error("Azure Maps route error: %s", exc)
            return self._fallback_eta(
                patient_lat, patient_lon, hospital_lat, hospital_lon
            )

    # ------------------------------------------------------------------
    # Fallback ETA
    # ------------------------------------------------------------------

    def _fallback_eta(
        self,
        patient_lat: float,
        patient_lon: float,
        hospital_lat: float,
        hospital_lon: float,
    ) -> dict:
        """Estimate ETA using straight-line distance (Haversine).

        Assumes average urban driving speed of 30 km/h with a 1.3×
        detour factor for road routing.
        """
        distance_km = self._haversine_distance(
            patient_lat, patient_lon, hospital_lat, hospital_lon
        )
        road_distance = distance_km * 1.3
        eta_minutes = max(1, round((road_distance / 30) * 60))

        return {
            "eta_minutes": eta_minutes,
            "distance_km": round(distance_km, 1),
            "traffic_delay_minutes": 0,
            "route_summary": f"~{round(distance_km, 1)} km, ~{eta_minutes} min (estimated)",
            "source": "estimated",
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate great-circle distance between two GPS points.

        Returns:
            Distance in kilometres.
        """
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        return R * c