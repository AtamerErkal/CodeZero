import sys
import logging
from src.maps_handler import MapsHandler

logging.basicConfig(level=logging.INFO)

mh = MapsHandler()

def _find_hospitals(mh, lat: float, lon: float, country: str = "DE") -> list[dict]:
    import inspect
    sig = inspect.signature(mh.find_nearest_hospitals)
    print(f"Signature: {sig}")
    if "country" in sig.parameters:
        print("Using country parameter")
        return mh.find_nearest_hospitals(lat, lon, count=3, country=country)
    print("Not using country parameter")
    return mh.find_nearest_hospitals(lat, lon, count=3)

try:
    print("Testing DE...")
    hospitals = _find_hospitals(mh, 48.77, 9.18, country="DE")
    print(len(hospitals))
except Exception as e:
    print(e)
