"""
Maps Handler Module
===================
Provides geolocation and routing services via Azure Maps. Calculates
ETA from patient location to the nearest hospital considering real-time
traffic conditions.

AI-102 Concepts:
  - Azure Maps Route API for ETA calculation
  - Azure Maps Search for finding nearby hospitals
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


class MapsHandler:
    """Handles geolocation and route calculation via Azure Maps.

    Calculates the estimated time of arrival (ETA) from the patient's
    location to the configured hospital, with real-time traffic
    consideration.

    Attributes:
        subscription_key: Azure Maps subscription key.
        hospital_lat: Hospital latitude from config.
        hospital_lon: Hospital longitude from config.
        hospital_name: Hospital name from config.
    """

    def __init__(self) -> None:
        """Initialize the Maps Handler with Azure credentials."""
        self.subscription_key: str = os.getenv("MAPS_SUBSCRIPTION_KEY", "")
        self.hospital_lat: float = float(os.getenv("HOSPITAL_LOCATION_LAT", "48.7758"))
        self.hospital_lon: float = float(os.getenv("HOSPITAL_LOCATION_LON", "9.1829"))
        self.hospital_name: str = os.getenv("HOSPITAL_NAME", "City General Hospital")
        self._initialized = bool(
            self.subscription_key and self.subscription_key != "your-key"
        )

        if not self._initialized:
            logger.warning(
                "Azure Maps credentials not configured. "
                "Using estimated ETA based on straight-line distance."
            )
        else:
            logger.info("Azure Maps initialized.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_eta(
        self, patient_lat: float, patient_lon: float
    ) -> dict:
        """Calculate ETA from patient location to hospital.

        AI-102: Azure Maps Route API provides turn-by-turn directions
        with real-time traffic data. The /route/directions endpoint
        returns travel time, distance, and route geometry.

        Args:
            patient_lat: Patient's latitude.
            patient_lon: Patient's longitude.

        Returns:
            Dict with eta_minutes, distance_km, hospital_name,
            route_summary, and hospital coordinates.
        """
        if self._initialized:
            return self._azure_maps_eta(patient_lat, patient_lon)
        return self._fallback_eta(patient_lat, patient_lon)

    def find_nearest_hospitals(
        self, patient_lat: float, patient_lon: float, radius_km: int = 20
    ) -> list[dict]:
        """Find nearby hospitals using Azure Maps Search.

        AI-102: Azure Maps Search POI (Point of Interest) API finds
        hospitals, clinics, and medical facilities near a given location.

        Args:
            patient_lat: Patient's latitude.
            patient_lon: Patient's longitude.
            radius_km: Search radius in kilometers.

        Returns:
            List of hospital dicts with name, lat, lon, distance_km.
        """
        if not self._initialized:
            # Return the configured hospital as fallback
            dist = self._haversine_distance(
                patient_lat, patient_lon, self.hospital_lat, self.hospital_lon
            )
            return [
                {
                    "name": self.hospital_name,
                    "lat": self.hospital_lat,
                    "lon": self.hospital_lon,
                    "distance_km": round(dist, 1),
                }
            ]

        try:
            url = "https://atlas.microsoft.com/search/poi/json"
            params = {
                "subscription-key": self.subscription_key,
                "api-version": "1.0",
                "query": "hospital emergency room",
                "lat": patient_lat,
                "lon": patient_lon,
                "radius": radius_km * 1000,  # meters
                "limit": 5,
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            hospitals = []
            for result in data.get("results", []):
                pos = result.get("position", {})
                hospitals.append(
                    {
                        "name": result.get("poi", {}).get("name", "Unknown Hospital"),
                        "lat": pos.get("lat", 0),
                        "lon": pos.get("lon", 0),
                        "distance_km": round(
                            result.get("dist", 0) / 1000, 1
                        ),
                        "address": result.get("address", {}).get(
                            "freeformAddress", ""
                        ),
                    }
                )

            logger.info("Found %d hospitals near (%.4f, %.4f).", len(hospitals), patient_lat, patient_lon)
            return hospitals

        except Exception as exc:
            logger.error("Hospital search error: %s", exc)
            # Fallback: return configured hospital
            dist = self._haversine_distance(
                patient_lat, patient_lon, self.hospital_lat, self.hospital_lon
            )
            return [
                {
                    "name": self.hospital_name,
                    "lat": self.hospital_lat,
                    "lon": self.hospital_lon,
                    "distance_km": round(dist, 1),
                }
            ]

    # ------------------------------------------------------------------
    # Azure Maps route calculation
    # ------------------------------------------------------------------

    def _azure_maps_eta(
        self, patient_lat: float, patient_lon: float
    ) -> dict:
        """Calculate ETA using Azure Maps Route Directions API.

        AI-102: The Route Directions API supports:
        - Real-time traffic (traffic=True in departure_time=now)
        - Multiple route alternatives
        - Travel time with/without traffic delays
        """
        try:
            url = "https://atlas.microsoft.com/route/directions/json"
            params = {
                "subscription-key": self.subscription_key,
                "api-version": "1.0",
                "query": (
                    f"{patient_lat},{patient_lon}:"
                    f"{self.hospital_lat},{self.hospital_lon}"
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
                return self._fallback_eta(patient_lat, patient_lon)

            route = routes[0]
            summary = route.get("summary", {})
            eta_seconds = summary.get("travelTimeInSeconds", 0)
            distance_meters = summary.get("lengthInMeters", 0)
            traffic_delay = summary.get("trafficDelayInSeconds", 0)

            result = {
                "eta_minutes": max(1, round(eta_seconds / 60)),
                "distance_km": round(distance_meters / 1000, 1),
                "traffic_delay_minutes": round(traffic_delay / 60),
                "hospital_name": self.hospital_name,
                "hospital_lat": self.hospital_lat,
                "hospital_lon": self.hospital_lon,
                "route_summary": (
                    f"{round(distance_meters / 1000, 1)} km, "
                    f"~{max(1, round(eta_seconds / 60))} min"
                ),
                "source": "azure_maps",
            }

            logger.info(
                "Azure Maps ETA: %d min (%.1f km, +%d min traffic)",
                result["eta_minutes"],
                result["distance_km"],
                result["traffic_delay_minutes"],
            )
            return result

        except Exception as exc:
            logger.error("Azure Maps route error: %s", exc)
            return self._fallback_eta(patient_lat, patient_lon)

    # ------------------------------------------------------------------
    # Fallback ETA (no Azure Maps credentials)
    # ------------------------------------------------------------------

    def _fallback_eta(
        self, patient_lat: float, patient_lon: float
    ) -> dict:
        """Estimate ETA using straight-line distance (Haversine).

        Assumes an average urban driving speed of 30 km/h with a
        1.3x detour factor for road routing.

        Args:
            patient_lat: Patient latitude.
            patient_lon: Patient longitude.

        Returns:
            Estimated ETA dict.
        """
        distance_km = self._haversine_distance(
            patient_lat, patient_lon, self.hospital_lat, self.hospital_lon
        )
        # Detour factor of 1.3 and average speed of 30 km/h
        road_distance = distance_km * 1.3
        eta_minutes = max(1, round((road_distance / 30) * 60))

        result = {
            "eta_minutes": eta_minutes,
            "distance_km": round(distance_km, 1),
            "traffic_delay_minutes": 0,
            "hospital_name": self.hospital_name,
            "hospital_lat": self.hospital_lat,
            "hospital_lon": self.hospital_lon,
            "route_summary": f"~{round(distance_km, 1)} km, ~{eta_minutes} min (estimated)",
            "source": "estimated",
        }

        logger.info(
            "Fallback ETA: %d min (%.1f km straight-line)",
            eta_minutes,
            distance_km,
        )
        return result

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate great-circle distance between two GPS points.

        Args:
            lat1, lon1: First point coordinates.
            lat2, lon2: Second point coordinates.

        Returns:
            Distance in kilometers.
        """
        R = 6371  # Earth's radius in km
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