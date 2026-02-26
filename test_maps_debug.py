import logging
from src.maps_handler import MapsHandler, ALL_HOSPITALS
logging.basicConfig(level=logging.DEBUG)

mh = MapsHandler()

# Debug the pool filtering
pool_de = [h for h in ALL_HOSPITALS if h.get("country", "DE") == "DE"]
print(f"DE Pool Size: {len(pool_de)}")

pool_uk = [h for h in ALL_HOSPITALS if h.get("country", "DE") == "UK"]
print(f"UK Pool Size: {len(pool_uk)}")

hospitals = mh.find_nearest_hospitals(48.77, 9.18, country="DE")
print(hospitals)
