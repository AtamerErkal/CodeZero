"""
Maps Handler Module — CodeZero
================================
Germany hospital database (113 hospitals, all 16 Bundesländer) + traffic-aware ETA.
Ranking: effective_eta = azure_maps_eta + occupancy_penalty
"""

from __future__ import annotations
import logging, math, os
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GERMANY_HOSPITALS: list[dict] = [
    # Baden-Württemberg
    {"name":"Klinikum Stuttgart – Katharinenhospital","lat":48.7823,"lon":9.1749,"address":"Kriegsbergstraße 60, 70174 Stuttgart"},
    {"name":"Robert-Bosch-Krankenhaus Stuttgart","lat":48.7944,"lon":9.2198,"address":"Auerbachstraße 110, 70376 Stuttgart"},
    {"name":"Marienhospital Stuttgart","lat":48.7647,"lon":9.1632,"address":"Böheimstraße 37, 70199 Stuttgart"},
    {"name":"Universitätsklinikum Tübingen","lat":48.5355,"lon":9.0396,"address":"Hoppe-Seyler-Straße 3, 72076 Tübingen"},
    {"name":"Universitätsklinikum Freiburg","lat":47.9975,"lon":7.8418,"address":"Hugstetter Straße 55, 79106 Freiburg"},
    {"name":"Städtisches Klinikum Karlsruhe","lat":49.0069,"lon":8.3714,"address":"Moltkestraße 90, 76133 Karlsruhe"},
    {"name":"Universitätsklinikum Heidelberg","lat":49.4161,"lon":8.6718,"address":"Im Neuenheimer Feld 400, 69120 Heidelberg"},
    {"name":"Klinikum Mannheim","lat":49.4834,"lon":8.4719,"address":"Theodor-Kutzer-Ufer 1-3, 68167 Mannheim"},
    {"name":"Ostalb-Klinikum Aalen","lat":48.8378,"lon":10.0938,"address":"Im Kälblesrain 1, 73430 Aalen"},
    {"name":"SLK-Kliniken Heilbronn","lat":49.1427,"lon":9.2109,"address":"Am Gesundbrunnen 20, 74078 Heilbronn"},
    {"name":"Schwarzwald-Baar Klinikum VS","lat":48.0594,"lon":8.4689,"address":"Keckweg 1, 78052 Villingen-Schwenningen"},
    {"name":"Klinikum Konstanz","lat":47.6696,"lon":9.1719,"address":"Mainaustraße 35, 78464 Konstanz"},
    {"name":"Kreiskliniken Reutlingen","lat":48.4892,"lon":9.2105,"address":"Steinenbergstraße 31, 72764 Reutlingen"},
    {"name":"Klinikum Esslingen","lat":48.7414,"lon":9.3097,"address":"Hirschlandstraße 97, 73730 Esslingen"},
    {"name":"Klinikum Ludwigsburg","lat":48.8979,"lon":9.1921,"address":"Posilipostraße 4, 71640 Ludwigsburg"},
    {"name":"Klinikum Friedrichshafen","lat":47.6618,"lon":9.4925,"address":"Röntgenstraße 2, 88048 Friedrichshafen"},
    {"name":"Ortenau-Klinikum Offenburg","lat":48.4734,"lon":7.9469,"address":"Ebertplatz 12, 77654 Offenburg"},
    {"name":"Klinikum Pforzheim","lat":48.8892,"lon":8.6913,"address":"Kanzlerstraße 2-6, 75175 Pforzheim"},
    # Bayern
    {"name":"Klinikum rechts der Isar München","lat":48.1372,"lon":11.5995,"address":"Ismaninger Str. 22, 81675 München"},
    {"name":"LMU Klinikum München – Großhadern","lat":48.1104,"lon":11.4698,"address":"Marchioninistraße 15, 81377 München"},
    {"name":"Städtisches Klinikum München – Schwabing","lat":48.1760,"lon":11.5816,"address":"Kölner Platz 1, 80804 München"},
    {"name":"Helios München West","lat":48.1549,"lon":11.4619,"address":"Steinerweg 5, 81241 München"},
    {"name":"Klinikum Augsburg","lat":48.3714,"lon":10.8815,"address":"Stenglinstraße 2, 86156 Augsburg"},
    {"name":"Universitätsklinikum Würzburg","lat":49.7970,"lon":9.9270,"address":"Josef-Schneider-Straße 2, 97080 Würzburg"},
    {"name":"Universitätsklinikum Erlangen","lat":49.5966,"lon":11.0042,"address":"Maximiliansplatz 2, 91054 Erlangen"},
    {"name":"Klinikum Nürnberg Nord","lat":49.4821,"lon":11.0639,"address":"Prof.-Ernst-Nathan-Straße 1, 90419 Nürnberg"},
    {"name":"Klinikum Nürnberg Süd","lat":49.4217,"lon":11.0700,"address":"Breslauerstraße 201, 90471 Nürnberg"},
    {"name":"Klinikum Regensburg","lat":49.0197,"lon":12.0882,"address":"Franz-Josef-Strauß-Allee 11, 93053 Regensburg"},
    {"name":"Klinikum Landshut","lat":48.5484,"lon":12.1564,"address":"Robert-Koch-Straße 1, 84034 Landshut"},
    {"name":"RoMed Klinikum Rosenheim","lat":47.8584,"lon":12.1304,"address":"Pettenkoferstraße 10, 83022 Rosenheim"},
    {"name":"Klinikum Ingolstadt","lat":48.7626,"lon":11.4234,"address":"Krumenauerstraße 25, 85049 Ingolstadt"},
    {"name":"Klinikum Passau","lat":48.5731,"lon":13.4597,"address":"Innstraße 76, 94032 Passau"},
    {"name":"Klinikum Bayreuth","lat":49.9536,"lon":11.5786,"address":"Preuschwitzer Straße 101, 95445 Bayreuth"},
    {"name":"Klinikum Coburg","lat":50.2565,"lon":10.9638,"address":"Ketschendorfer Straße 33, 96450 Coburg"},
    {"name":"Klinikum Bamberg","lat":49.8966,"lon":10.8934,"address":"Buger Straße 80, 96049 Bamberg"},
    {"name":"Klinikum Memmingen","lat":47.9863,"lon":10.1808,"address":"Bismarckstraße 23, 87700 Memmingen"},
    {"name":"Klinikum Kaufbeuren","lat":47.8811,"lon":10.6228,"address":"Kempter Straße 99, 87600 Kaufbeuren"},
    # Berlin
    {"name":"Charité – Universitätsmedizin Berlin (Mitte)","lat":52.5247,"lon":13.3783,"address":"Charitéplatz 1, 10117 Berlin"},
    {"name":"Charité – Campus Virchow-Klinikum","lat":52.5419,"lon":13.3427,"address":"Augustenburger Platz 1, 13353 Berlin"},
    {"name":"Charité – Campus Benjamin Franklin","lat":52.4466,"lon":13.3005,"address":"Hindenburgdamm 30, 12203 Berlin"},
    {"name":"Vivantes Klinikum Neukölln","lat":52.4673,"lon":13.4399,"address":"Rudower Chaussee 48, 12351 Berlin"},
    {"name":"Vivantes Klinikum im Friedrichshain","lat":52.5148,"lon":13.4448,"address":"Landsberger Allee 49, 10249 Berlin"},
    {"name":"DRK Kliniken Berlin Westend","lat":52.5100,"lon":13.2838,"address":"Spandauer Damm 130, 14050 Berlin"},
    {"name":"Helios Klinikum Berlin-Buch","lat":52.6239,"lon":13.4998,"address":"Schwanebecker Chaussee 50, 13125 Berlin"},
    {"name":"Sankt Gertrauden-Krankenhaus Berlin","lat":52.4881,"lon":13.3238,"address":"Paretzer Straße 12, 10713 Berlin"},
    # Brandenburg
    {"name":"Städtisches Klinikum Brandenburg","lat":52.4126,"lon":12.5572,"address":"Hochstraße 29, 14770 Brandenburg an der Havel"},
    {"name":"Klinikum Ernst von Bergmann Potsdam","lat":52.3963,"lon":13.0569,"address":"Charlottenstraße 72, 14467 Potsdam"},
    {"name":"Klinikum Frankfurt (Oder)","lat":52.3392,"lon":14.5475,"address":"Müllroser Chaussee 7, 15236 Frankfurt (Oder)"},
    # Bremen
    {"name":"Klinikum Bremen-Mitte","lat":53.0829,"lon":8.8090,"address":"Sankt-Jürgen-Straße 1, 28205 Bremen"},
    {"name":"Klinikum Bremen-Ost","lat":53.0652,"lon":8.9239,"address":"Züricher Straße 40, 28325 Bremen"},
    {"name":"Rotes Kreuz Krankenhaus Bremen","lat":53.0945,"lon":8.7895,"address":"Rotkreuzstraße 2, 28199 Bremen"},
    # Hamburg
    {"name":"Universitätsklinikum Hamburg-Eppendorf (UKE)","lat":53.5892,"lon":9.9739,"address":"Martinistraße 52, 20246 Hamburg"},
    {"name":"Asklepios Klinikum Hamburg-Altona","lat":53.5510,"lon":9.9265,"address":"Paul-Ehrlich-Straße 1, 22763 Hamburg"},
    {"name":"Asklepios Klinikum Hamburg-Barmbek","lat":53.6014,"lon":10.0387,"address":"Rübenkamp 220, 22291 Hamburg"},
    {"name":"Asklepios Klinikum Hamburg-Harburg","lat":53.4646,"lon":9.9892,"address":"Eißendorfer Pferdeweg 52, 21075 Hamburg"},
    {"name":"Marienkrankenhaus Hamburg","lat":53.5716,"lon":10.0138,"address":"Alfredstraße 9, 22087 Hamburg"},
    # Hessen
    {"name":"Universitätsklinikum Frankfurt","lat":50.0934,"lon":8.6460,"address":"Theodor-Stern-Kai 7, 60590 Frankfurt"},
    {"name":"Krankenhaus Nordwest Frankfurt","lat":50.1386,"lon":8.6373,"address":"Steinbacher Hohl 2-26, 60488 Frankfurt"},
    {"name":"Universitätsklinikum Marburg","lat":50.8131,"lon":8.7764,"address":"Baldingerstraße, 35043 Marburg"},
    {"name":"Klinikum Kassel","lat":51.3093,"lon":9.5021,"address":"Mönchebergstraße 41-43, 34125 Kassel"},
    {"name":"HSK Wiesbaden – Dr. Horst Schmidt Kliniken","lat":50.0781,"lon":8.2409,"address":"Ludwig-Erhard-Straße 100, 65199 Wiesbaden"},
    {"name":"Klinikum Darmstadt","lat":49.8757,"lon":8.6449,"address":"Grafenstraße 9, 64283 Darmstadt"},
    {"name":"Klinikum Offenbach","lat":50.1019,"lon":8.7616,"address":"Starkenburgring 66, 63069 Offenbach"},
    # Mecklenburg-Vorpommern
    {"name":"Universitätsmedizin Greifswald","lat":54.0924,"lon":13.3833,"address":"Ferdinand-Sauerbruch-Straße, 17475 Greifswald"},
    {"name":"Universitätsmedizin Rostock","lat":54.0901,"lon":12.1318,"address":"Ernst-Heydemann-Straße 6, 18057 Rostock"},
    {"name":"Helios Kliniken Schwerin","lat":53.6186,"lon":11.4237,"address":"Wismarsche Straße 393-397, 19049 Schwerin"},
    # Niedersachsen
    {"name":"Medizinische Hochschule Hannover (MHH)","lat":52.3814,"lon":9.8056,"address":"Carl-Neuberg-Straße 1, 30625 Hannover"},
    {"name":"Klinikum Region Hannover – Hannover Mitte","lat":52.3659,"lon":9.7388,"address":"Haltenhoffstraße 41, 30167 Hannover"},
    {"name":"Klinikum Braunschweig","lat":52.2604,"lon":10.5113,"address":"Salzdahlumer Straße 90, 38126 Braunschweig"},
    {"name":"Klinikum Oldenburg","lat":53.1507,"lon":8.2045,"address":"Rahel-Straus-Straße 10, 26133 Oldenburg"},
    {"name":"Klinikum Osnabrück","lat":52.2799,"lon":8.0472,"address":"Am Finkenhügel 1, 49076 Osnabrück"},
    {"name":"Städtisches Klinikum Wolfsburg","lat":52.4278,"lon":10.7812,"address":"Sauerbruchstraße 7, 38440 Wolfsburg"},
    {"name":"Klinikum Hildesheim","lat":52.1561,"lon":9.9469,"address":"Senator-Braun-Allee 33, 31135 Hildesheim"},
    {"name":"Universitätsmedizin Göttingen","lat":51.5422,"lon":9.9368,"address":"Robert-Koch-Straße 40, 37075 Göttingen"},
    # Nordrhein-Westfalen
    {"name":"Universitätsklinikum Köln","lat":50.9236,"lon":6.9205,"address":"Kerpener Str. 62, 50937 Köln"},
    {"name":"Krankenhaus Merheim Köln","lat":50.9543,"lon":7.0492,"address":"Ostmerheimer Straße 200, 51109 Köln"},
    {"name":"Universitätsklinikum Düsseldorf","lat":51.1911,"lon":6.7885,"address":"Moorenstraße 5, 40225 Düsseldorf"},
    {"name":"Universitätsklinikum Essen","lat":51.4340,"lon":7.0031,"address":"Hufelandstraße 55, 45147 Essen"},
    {"name":"Universitätsklinikum Bochum","lat":51.4680,"lon":7.2028,"address":"Gudrunstraße 56, 44791 Bochum"},
    {"name":"Universitätsklinikum Münster","lat":51.9630,"lon":7.5953,"address":"Albert-Schweitzer-Campus 1, 48149 Münster"},
    {"name":"Universitätsklinikum Bonn","lat":50.7001,"lon":7.1121,"address":"Venusberg-Campus 1, 53127 Bonn"},
    {"name":"Klinikum Dortmund","lat":51.5056,"lon":7.4596,"address":"Beurhausstraße 40, 44137 Dortmund"},
    {"name":"Evangelisches Klinikum Bethel Bielefeld","lat":52.0126,"lon":8.5145,"address":"Burgsteig 13, 33617 Bielefeld"},
    {"name":"Klinikum Aachen","lat":50.7700,"lon":6.0440,"address":"Pauwelsstraße 30, 52074 Aachen"},
    {"name":"Helios Universitätsklinikum Wuppertal","lat":51.2462,"lon":7.1552,"address":"Heusnerstraße 40, 42283 Wuppertal"},
    {"name":"Klinikum Leverkusen","lat":51.0289,"lon":6.9989,"address":"Am Gesundheitspark 11, 51375 Leverkusen"},
    {"name":"Klinikum Duisburg","lat":51.4360,"lon":6.7623,"address":"Zu den Rehwiesen 9-11, 47055 Duisburg"},
    {"name":"Marienhospital Gelsenkirchen","lat":51.5195,"lon":7.0940,"address":"Virchowstraße 122, 45886 Gelsenkirchen"},
    {"name":"Klinikum Gütersloh","lat":51.9059,"lon":8.3864,"address":"Reckenberger Straße 19, 33332 Gütersloh"},
    {"name":"Klinikum Minden","lat":52.2877,"lon":8.9128,"address":"Hans-Nolte-Straße 1, 32429 Minden"},
    {"name":"Klinikum Solingen","lat":51.1712,"lon":7.0780,"address":"Gotenstraße 1, 42653 Solingen"},
    {"name":"Klinikum Krefeld","lat":51.3388,"lon":6.5855,"address":"Lutherplatz 40, 47805 Krefeld"},
    {"name":"St. Marien-Hospital Hamm","lat":51.6746,"lon":7.8261,"address":"Nassauer Straße 13-19, 59065 Hamm"},
    # Rheinland-Pfalz
    {"name":"Universitätsmedizin Mainz","lat":49.9990,"lon":8.2728,"address":"Langenbeckstraße 1, 55131 Mainz"},
    {"name":"Klinikum Kaiserslautern","lat":49.4451,"lon":7.7556,"address":"Hellmut-Hartert-Straße 1, 67655 Kaiserslautern"},
    {"name":"Bundeswehrzentralkrankenhaus Koblenz","lat":50.3533,"lon":7.5912,"address":"Rübenacher Straße 170, 56072 Koblenz"},
    {"name":"Klinikum Ludwigshafen","lat":49.4778,"lon":8.4456,"address":"Bremserstraße 79, 67063 Ludwigshafen"},
    {"name":"Klinikum Trier – Mutterhaus","lat":49.7541,"lon":6.6421,"address":"Feldstraße 16, 54290 Trier"},
    # Saarland
    {"name":"Universitätsklinikum des Saarlandes Homburg","lat":49.3208,"lon":7.3398,"address":"Kirrberger Straße 100, 66421 Homburg"},
    {"name":"Klinikum Saarbrücken","lat":49.2374,"lon":7.0063,"address":"Winterberg 1, 66119 Saarbrücken"},
    # Sachsen
    {"name":"Universitätsklinikum Leipzig","lat":51.3288,"lon":12.3697,"address":"Liebigstraße 20, 04103 Leipzig"},
    {"name":"Universitätsklinikum Dresden","lat":51.0616,"lon":13.7759,"address":"Fetscherstraße 74, 01307 Dresden"},
    {"name":"Klinikum Chemnitz","lat":50.8357,"lon":12.9300,"address":"Flemmingstraße 2, 09116 Chemnitz"},
    {"name":"Klinikum Zwickau","lat":50.7198,"lon":12.4972,"address":"Karl-Keil-Straße 35, 08060 Zwickau"},
    {"name":"Klinikum Görlitz","lat":51.1551,"lon":14.9875,"address":"Girbigsdorfer Straße 1-3, 02828 Görlitz"},
    # Sachsen-Anhalt
    {"name":"Universitätsklinikum Halle (Saale)","lat":51.4925,"lon":11.9605,"address":"Ernst-Grube-Straße 40, 06120 Halle"},
    {"name":"Universitätsklinikum Magdeburg","lat":52.1285,"lon":11.6271,"address":"Leipziger Straße 44, 39120 Magdeburg"},
    {"name":"Klinikum Dessau","lat":51.8330,"lon":12.2448,"address":"Auenweg 38, 06847 Dessau"},
    # Schleswig-Holstein
    {"name":"Universitätsklinikum Schleswig-Holstein Kiel","lat":54.3216,"lon":10.1348,"address":"Arnold-Heller-Straße 3, 24105 Kiel"},
    {"name":"Universitätsklinikum Schleswig-Holstein Lübeck","lat":53.8385,"lon":10.7154,"address":"Ratzeburger Allee 160, 23562 Lübeck"},
    {"name":"Helios Klinikum Schleswig","lat":54.5168,"lon":9.5601,"address":"St.-Jürgen-Straße 1, 24837 Schleswig"},
    {"name":"Imland Klinik Rendsburg","lat":54.3026,"lon":9.6622,"address":"Lilienstraße 20-28, 24768 Rendsburg"},
    {"name":"Sana Klinikum Lübeck","lat":53.8648,"lon":10.6990,"address":"Kronsforder Allee 71-73, 23560 Lübeck"},
    # Thüringen
    {"name":"Universitätsklinikum Jena","lat":50.9272,"lon":11.5930,"address":"Am Klinikum 1, 07747 Jena"},
    {"name":"Helios Klinikum Erfurt","lat":50.9845,"lon":11.0199,"address":"Nordhäuser Straße 74, 99089 Erfurt"},
    {"name":"SRH Zentralklinikum Suhl","lat":50.6104,"lon":10.6937,"address":"Albert-Schweitzer-Straße 2, 98527 Suhl"},
    {"name":"Klinikum Gera","lat":50.8829,"lon":12.0766,"address":"Straße des Friedens 122, 07548 Gera"},
]

_OCCUPANCY_REGISTRY: dict[str, str] = {}

_OCCUPANCY_PENALTY: dict[str, int] = {"low": 0, "medium": 10, "high": 25, "full": 60}
_OCCUPANCY_LABELS:  dict[str, str] = {"low": "🟢 Low", "medium": "🟡 Medium", "high": "🟠 High", "full": "🔴 Full"}


def set_hospital_occupancy(hospital_name: str, level: str) -> None:
    _OCCUPANCY_REGISTRY[hospital_name] = level
    logger.info("Occupancy updated: %s → %s", hospital_name, level)


def get_hospital_occupancy(hospital_name: str) -> str:
    return _OCCUPANCY_REGISTRY.get(hospital_name, "medium")


class MapsHandler:
    def __init__(self) -> None:
        self.subscription_key: str = os.getenv("MAPS_SUBSCRIPTION_KEY", "")
        self._initialized = bool(self.subscription_key and self.subscription_key != "your-key")
        if not self._initialized:
            logger.warning("Azure Maps not configured — using Germany hospital DB + estimated ETA.")
        else:
            logger.info("Azure Maps initialized.")

    def find_nearest_hospitals(self, patient_lat: float, patient_lon: float, count: int = 3, radius_km: int = 100) -> list[dict]:
        candidates = self._germany_search(patient_lat, patient_lon, radius_km)
        enriched: list[dict] = []
        for h in candidates:
            eta = self.calculate_eta_to_hospital(patient_lat, patient_lon, h["lat"], h["lon"])
            occupancy = get_hospital_occupancy(h["name"])
            penalty   = _OCCUPANCY_PENALTY.get(occupancy, 10)
            enriched.append({
                **h,
                "eta_minutes":           eta["eta_minutes"],
                "distance_km":           eta["distance_km"],
                "traffic_delay_minutes": eta.get("traffic_delay_minutes", 0),
                "route_summary":         eta["route_summary"],
                "source":                eta["source"],
                "occupancy":             occupancy,
                "occupancy_label":       _OCCUPANCY_LABELS.get(occupancy, "🟡 Medium"),
                "effective_eta":         eta["eta_minutes"] + penalty,
            })
        enriched.sort(key=lambda x: x["effective_eta"])
        result = enriched[:count]
        logger.info("Returning %d hospitals. Top: %s (%d min eff.)",
                    len(result), result[0]["name"] if result else "N/A",
                    result[0]["effective_eta"] if result else 0)
        return result

    def calculate_eta_to_hospital(self, patient_lat: float, patient_lon: float, hospital_lat: float, hospital_lon: float) -> dict:
        if self._initialized:
            return self._azure_maps_eta(patient_lat, patient_lon, hospital_lat, hospital_lon)
        return self._fallback_eta(patient_lat, patient_lon, hospital_lat, hospital_lon)

    def _germany_search(self, patient_lat: float, patient_lon: float, radius_km: int = 100) -> list[dict]:
        scored = sorted(
            [{**h, "distance_km": round(self._haversine_distance(patient_lat, patient_lon, h["lat"], h["lon"]), 1)}
             for h in GERMANY_HOSPITALS],
            key=lambda x: x["distance_km"]
        )
        within = [h for h in scored if h["distance_km"] <= radius_km]
        return (within[:10] if within else scored[:5])

    def _azure_maps_eta(self, patient_lat, patient_lon, hospital_lat, hospital_lon) -> dict:
        try:
            resp = requests.get(
                "https://atlas.microsoft.com/route/directions/json",
                params={
                    "subscription-key": self.subscription_key,
                    "api-version": "1.0",
                    "query": f"{patient_lat},{patient_lon}:{hospital_lat},{hospital_lon}",
                    "traffic": "true", "departAt": "now", "travelMode": "car",
                }, timeout=10)
            resp.raise_for_status()
            routes = resp.json().get("routes", [])
            if not routes:
                return self._fallback_eta(patient_lat, patient_lon, hospital_lat, hospital_lon)
            s = routes[0]["summary"]
            eta_min   = max(1, round(s.get("travelTimeInSeconds", 0) / 60))
            dist_km   = round(s.get("lengthInMeters", 0) / 1000, 1)
            delay_min = round(s.get("trafficDelayInSeconds", 0) / 60)
            note = f" (+{delay_min} min traffic)" if delay_min > 0 else ""
            return {"eta_minutes": eta_min, "distance_km": dist_km,
                    "traffic_delay_minutes": delay_min,
                    "route_summary": f"{dist_km} km · ~{eta_min} min{note}",
                    "source": "azure_maps"}
        except Exception as exc:
            logger.error("Azure Maps error: %s", exc)
            return self._fallback_eta(patient_lat, patient_lon, hospital_lat, hospital_lon)

    def _fallback_eta(self, patient_lat, patient_lon, hospital_lat, hospital_lon) -> dict:
        dist  = self._haversine_distance(patient_lat, patient_lon, hospital_lat, hospital_lon)
        eta   = max(1, round((dist * 1.3 / 30) * 60))
        return {"eta_minutes": eta, "distance_km": round(dist, 1),
                "traffic_delay_minutes": 0,
                "route_summary": f"~{round(dist,1)} km · ~{eta} min (est.)",
                "source": "estimated"}

    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2) -> float:
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))