from src.maps_handler import MapsHandler, ALL_HOSPITALS
import sys
import logging

logging.basicConfig(level=logging.INFO)

print(f"Total hospitals: {len(ALL_HOSPITALS)}")
mh = MapsHandler()

try:
    # Find nearest in DE
    de_hospitals = mh.find_nearest_hospitals(48.77, 9.18, country="DE")
    print(f"Nearest in DE: {len(de_hospitals)}")
except Exception as e:
    print(f"Error in DE: {e}")
