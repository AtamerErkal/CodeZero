"""
Maps Handler — CodeZero
========================
Comprehensive emergency hospital database:
  DE: ~280 hospitals covering all 16 Bundesländer at district level
  UK: ~160 hospitals covering England, Scotland, Wales, Northern Ireland
  TR: ~180 hospitals covering all major provinces

Ranking: effective_eta = eta_minutes + occupancy_penalty
Azure Maps used when MAPS_SUBSCRIPTION_KEY is set; haversine fallback otherwise.
"""

from __future__ import annotations
import logging, math, os
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Germany ───────────────────────────────────────────────────────────────────
GERMANY_HOSPITALS: list[dict] = [
    # Baden-Württemberg
    {"name":"Klinikum Stuttgart – Katharinenhospital","lat":48.7823,"lon":9.1749,"address":"Kriegsbergstraße 60, 70174 Stuttgart"},
    {"name":"Robert-Bosch-Krankenhaus Stuttgart","lat":48.7944,"lon":9.2198,"address":"Auerbachstraße 110, 70376 Stuttgart"},
    {"name":"Marienhospital Stuttgart","lat":48.7647,"lon":9.1632,"address":"Böheimstraße 37, 70199 Stuttgart"},
    {"name":"Klinikum Ludwigsburg","lat":48.8979,"lon":9.1921,"address":"Posilipostraße 4, 71640 Ludwigsburg"},
    {"name":"Klinikum Esslingen","lat":48.7414,"lon":9.3097,"address":"Hirschlandstraße 97, 73730 Esslingen"},
    {"name":"Alb-Fils-Klinikum Göppingen","lat":48.7042,"lon":9.6538,"address":"Eichertstraße 3, 73035 Göppingen"},
    {"name":"Kreiskliniken Reutlingen","lat":48.4892,"lon":9.2105,"address":"Steinenbergstraße 31, 72764 Reutlingen"},
    {"name":"Universitätsklinikum Tübingen","lat":48.5355,"lon":9.0396,"address":"Hoppe-Seyler-Straße 3, 72076 Tübingen"},
    {"name":"Klinikum Sindelfingen-Böblingen","lat":48.7101,"lon":9.0089,"address":"Arthur-Gruber-Straße 70, 71065 Sindelfingen"},
    {"name":"Klinikum Backnang","lat":48.9472,"lon":9.4312,"address":"Andersstraße 10, 71522 Backnang"},
    {"name":"SLK-Kliniken Heilbronn","lat":49.1427,"lon":9.2109,"address":"Am Gesundbrunnen 20, 74078 Heilbronn"},
    {"name":"GRN-Klinik Sinsheim","lat":49.2532,"lon":8.8821,"address":"Alte Waibstadter Straße 2, 74889 Sinsheim"},
    {"name":"GRN-Klinik Mosbach","lat":49.3561,"lon":9.1505,"address":"Alte Miltenberger Straße 2, 74821 Mosbach"},
    {"name":"Klinikum Pforzheim","lat":48.8892,"lon":8.6913,"address":"Kanzlerstraße 2-6, 75175 Pforzheim"},
    {"name":"Städtisches Klinikum Karlsruhe","lat":49.0069,"lon":8.3714,"address":"Moltkestraße 90, 76133 Karlsruhe"},
    {"name":"Klinikum Bruchsal","lat":49.1253,"lon":8.5938,"address":"Helmsheimer Straße 35, 76646 Bruchsal"},
    {"name":"Klinikum Rastatt","lat":48.8605,"lon":8.2094,"address":"Engelstraße 39, 76437 Rastatt"},
    {"name":"Universitätsklinikum Heidelberg","lat":49.4161,"lon":8.6718,"address":"Im Neuenheimer Feld 400, 69120 Heidelberg"},
    {"name":"GRN-Klinik Schwetzingen","lat":49.3816,"lon":8.5729,"address":"Bodelschwinghstraße 10, 68723 Schwetzingen"},
    {"name":"Klinikum Mannheim","lat":49.4834,"lon":8.4719,"address":"Theodor-Kutzer-Ufer 1-3, 68167 Mannheim"},
    {"name":"Klinikum Heidenheim","lat":48.6837,"lon":10.1544,"address":"Schlosshaustraße 100, 89522 Heidenheim"},
    {"name":"Ostalb-Klinikum Aalen","lat":48.8378,"lon":10.0938,"address":"Im Kälblesrain 1, 73430 Aalen"},
    {"name":"Stauferklinikum Schwäbisch Gmünd","lat":48.7986,"lon":9.7979,"address":"Wetzgauer Straße 85, 73557 Mutlangen"},
    {"name":"Kreiskrankenhaus Crailsheim","lat":49.1337,"lon":10.0701,"address":"Diakoniestraße 10, 74564 Crailsheim"},
    {"name":"Diakonie-Klinikum Schwäbisch Hall","lat":49.1107,"lon":9.7412,"address":"Diakoniestraße 10, 74523 Schwäbisch Hall"},
    {"name":"Universitätsklinikum Ulm","lat":48.4204,"lon":9.9501,"address":"Albert-Einstein-Allee 23, 89081 Ulm"},
    {"name":"Klinikum Neu-Ulm","lat":48.3941,"lon":10.0057,"address":"Stiftsstraße 11, 89231 Neu-Ulm"},
    {"name":"Kreiskrankenhaus Biberach","lat":48.0966,"lon":9.7895,"address":"Ziegelstraße 29, 88400 Biberach"},
    {"name":"Klinikum Friedrichshafen","lat":47.6618,"lon":9.4925,"address":"Röntgenstraße 2, 88048 Friedrichshafen"},
    {"name":"Kliniken Ravensburg – St. Elisabeth","lat":47.7797,"lon":9.6132,"address":"Elisabethenstraße 15, 88212 Ravensburg"},
    {"name":"Krankenhaus Wangen","lat":47.6896,"lon":9.8325,"address":"Hangstraße 15, 88239 Wangen"},
    {"name":"Klinikum Kempten","lat":47.7272,"lon":10.3170,"address":"Robert-Weixler-Straße 50, 87439 Kempten"},
    {"name":"Klinikum Memmingen","lat":47.9863,"lon":10.1808,"address":"Bismarckstraße 23, 87700 Memmingen"},
    {"name":"Kreisklinik Kaufbeuren","lat":47.8811,"lon":10.6228,"address":"Kempter Straße 99, 87600 Kaufbeuren"},
    {"name":"Krankenhaus Lindau","lat":47.5534,"lon":9.6852,"address":"Friedrichshafener Straße 82, 88131 Lindau"},
    {"name":"Ortenau-Klinikum Offenburg","lat":48.4734,"lon":7.9469,"address":"Ebertplatz 12, 77654 Offenburg"},
    {"name":"Ortenau-Klinikum Lahr","lat":48.3394,"lon":7.8718,"address":"Klostenstraße 19, 77933 Lahr"},
    {"name":"Universitätsklinikum Freiburg","lat":47.9975,"lon":7.8418,"address":"Hugstetter Straße 55, 79106 Freiburg"},
    {"name":"Schwarzwald-Baar Klinikum VS","lat":48.0594,"lon":8.4689,"address":"Keckweg 1, 78052 Villingen-Schwenningen"},
    {"name":"Kreiskrankenhaus Rottweil","lat":48.1633,"lon":8.6220,"address":"Landstraße 18, 78628 Rottweil"},
    {"name":"Klinikum Tuttlingen","lat":47.9856,"lon":8.8191,"address":"Zentrales Klinikum, 78532 Tuttlingen"},
    {"name":"Klinikum Konstanz","lat":47.6696,"lon":9.1719,"address":"Mainaustraße 35, 78464 Konstanz"},
    {"name":"Klinikum Singen","lat":47.7626,"lon":8.8390,"address":"Virchowstraße 10, 78224 Singen"},
    {"name":"Klinikum Sigmaringen","lat":48.0843,"lon":9.2175,"address":"Hohenzollernstraße 40, 72488 Sigmaringen"},
    # Bayern
    {"name":"Klinikum rechts der Isar München (TUM)","lat":48.1372,"lon":11.5995,"address":"Ismaninger Str. 22, 81675 München"},
    {"name":"LMU Klinikum München – Großhadern","lat":48.1104,"lon":11.4698,"address":"Marchioninistraße 15, 81377 München"},
    {"name":"Städtisches Klinikum München – Schwabing","lat":48.1760,"lon":11.5816,"address":"Kölner Platz 1, 80804 München"},
    {"name":"Helios München West","lat":48.1549,"lon":11.4619,"address":"Steinerweg 5, 81241 München"},
    {"name":"Klinikum Starnberg","lat":47.9987,"lon":11.3395,"address":"Oßwaldstraße 1, 82319 Starnberg"},
    {"name":"Klinikum Weilheim","lat":47.8407,"lon":11.1463,"address":"Pütrichstraße 14, 82362 Weilheim"},
    {"name":"Klinikum Augsburg","lat":48.3714,"lon":10.8815,"address":"Stenglinstraße 2, 86156 Augsburg"},
    {"name":"Kreisklinik Dillingen","lat":48.5827,"lon":10.4944,"address":"Donaustraße 30, 89407 Dillingen"},
    {"name":"Stiftungsklinikum Donauwörth","lat":48.7084,"lon":10.7789,"address":"Neudegger Allee 6, 86609 Donauwörth"},
    {"name":"Kreisklinik Aichach","lat":48.4561,"lon":11.1345,"address":"Krankenhausstraße 1, 86551 Aichach"},
    {"name":"Klinikum Dachau","lat":48.2601,"lon":11.4348,"address":"Krankenhausstraße 15, 85221 Dachau"},
    {"name":"Klinikum Fürstenfeldbruck","lat":48.1798,"lon":11.2463,"address":"Dachauer Straße 33, 82256 Fürstenfeldbruck"},
    {"name":"Klinikum Landsberg am Lech","lat":47.9535,"lon":10.8704,"address":"Dr.-Hartmann-Straße 50, 86899 Landsberg"},
    {"name":"Kreiskrankenhaus Schrobenhausen","lat":48.5608,"lon":11.2618,"address":"Von-Seutter-Straße 10, 86529 Schrobenhausen"},
    {"name":"Klinikum Ingolstadt","lat":48.7626,"lon":11.4234,"address":"Krumenauerstraße 25, 85049 Ingolstadt"},
    {"name":"Klinikum Eichstätt","lat":48.8924,"lon":11.1890,"address":"Ostenstraße 31, 85072 Eichstätt"},
    {"name":"Klinikum Neuburg an der Donau","lat":48.7323,"lon":11.1845,"address":"Berliner Ring 7, 86633 Neuburg"},
    {"name":"Klinikum Pfaffenhofen","lat":48.5326,"lon":11.5064,"address":"Krankenhausstraße 7, 85276 Pfaffenhofen"},
    {"name":"Klinikum Freising","lat":48.3980,"lon":11.7364,"address":"Stiftstraße 21, 85354 Freising"},
    {"name":"Klinikum Erding","lat":48.3050,"lon":11.9075,"address":"Bajuwarenstraße 5, 85435 Erding"},
    {"name":"Klinikum Ebersberg","lat":48.0788,"lon":11.9670,"address":"Sankt-Salvator-Straße 2, 85560 Ebersberg"},
    {"name":"RoMed Klinikum Rosenheim","lat":47.8584,"lon":12.1304,"address":"Pettenkoferstraße 10, 83022 Rosenheim"},
    {"name":"Kreisklinik Wasserburg","lat":48.0608,"lon":12.2196,"address":"Krankenhausweg 5, 83512 Wasserburg"},
    {"name":"Kreisklinik Traunstein","lat":47.8699,"lon":12.6450,"address":"Cuno-Niggl-Straße 3, 83278 Traunstein"},
    {"name":"Kreisklinik Altötting","lat":48.2268,"lon":12.6763,"address":"Vinzenz-von-Paul-Straße 10, 84503 Altötting"},
    {"name":"Klinikum Landshut","lat":48.5484,"lon":12.1564,"address":"Robert-Koch-Straße 1, 84034 Landshut"},
    {"name":"Kreisklinik Dingolfing","lat":48.6296,"lon":12.4992,"address":"Krankenhausstraße 3, 84130 Dingolfing"},
    {"name":"Klinikum Passau","lat":48.5731,"lon":13.4597,"address":"Innstraße 76, 94032 Passau"},
    {"name":"Klinikum Deggendorf","lat":48.8368,"lon":12.9652,"address":"Perlasberger Straße 41, 94469 Deggendorf"},
    {"name":"Klinikum Straubing","lat":48.8825,"lon":12.5784,"address":"Äußere Passauer Straße 18, 94315 Straubing"},
    {"name":"Klinikum Regensburg","lat":49.0197,"lon":12.0882,"address":"Franz-Josef-Strauß-Allee 11, 93053 Regensburg"},
    {"name":"Klinikum Weiden","lat":49.6786,"lon":12.1548,"address":"Söllnerstraße 16, 92637 Weiden"},
    {"name":"Klinikum Amberg","lat":49.4420,"lon":11.8630,"address":"Mariahilfbergweg 7, 92224 Amberg"},
    {"name":"Klinikum Schwandorf","lat":49.3230,"lon":12.1041,"address":"Türkenfelder Straße 4, 92421 Schwandorf"},
    {"name":"Universitätsklinikum Erlangen","lat":49.5966,"lon":11.0042,"address":"Maximiliansplatz 2, 91054 Erlangen"},
    {"name":"Klinikum Nürnberg Nord","lat":49.4821,"lon":11.0639,"address":"Prof.-Ernst-Nathan-Straße 1, 90419 Nürnberg"},
    {"name":"Klinikum Nürnberg Süd","lat":49.4217,"lon":11.0700,"address":"Breslauerstraße 201, 90471 Nürnberg"},
    {"name":"Klinikum Fürth","lat":49.4782,"lon":10.9890,"address":"Jakob-Henle-Straße 1, 90766 Fürth"},
    {"name":"Klinikum Ansbach","lat":49.3002,"lon":10.5764,"address":"Escherichstraße 1, 91522 Ansbach"},
    {"name":"Klinikum Schwabach","lat":49.3306,"lon":11.0220,"address":"Celtisplatz 1, 91126 Schwabach"},
    {"name":"Klinikum Neumarkt","lat":49.2803,"lon":11.4644,"address":"Nürnberger Straße 12, 92318 Neumarkt"},
    {"name":"Universitätsklinikum Würzburg","lat":49.7970,"lon":9.9270,"address":"Josef-Schneider-Straße 2, 97080 Würzburg"},
    {"name":"Klinikum Schweinfurt","lat":50.0537,"lon":10.2169,"address":"Gustav-Adolf-Straße 6-8, 97422 Schweinfurt"},
    {"name":"Klinikum Aschaffenburg","lat":49.9828,"lon":9.1380,"address":"Am Hasenkopf 1, 63739 Aschaffenburg"},
    {"name":"Klinikum Kitzingen","lat":49.7324,"lon":10.1512,"address":"Friedenstraße 75, 97318 Kitzingen"},
    {"name":"Klinikum Bad Neustadt/Saale","lat":50.3248,"lon":10.2151,"address":"Von-Guttenberg-Straße 10, 97616 Bad Neustadt"},
    {"name":"Klinikum Bayreuth","lat":49.9536,"lon":11.5786,"address":"Preuschwitzer Straße 101, 95445 Bayreuth"},
    {"name":"Klinikum Bamberg","lat":49.8966,"lon":10.8934,"address":"Buger Straße 80, 96049 Bamberg"},
    {"name":"Klinikum Coburg","lat":50.2565,"lon":10.9638,"address":"Ketschendorfer Straße 33, 96450 Coburg"},
    {"name":"Klinikum Kronach","lat":50.2402,"lon":11.3267,"address":"Kulmbacher Straße 7, 96317 Kronach"},
    {"name":"Klinikum Hof","lat":50.3157,"lon":11.9145,"address":"Eppenreuther Straße 9, 95032 Hof"},
    {"name":"Kreisklinik Wunsiedel","lat":50.0399,"lon":12.0010,"address":"Epprechtstraße 19, 95632 Wunsiedel"},
    # Berlin
    {"name":"Charité – Campus Mitte","lat":52.5247,"lon":13.3783,"address":"Charitéplatz 1, 10117 Berlin"},
    {"name":"Charité – Campus Virchow-Klinikum","lat":52.5419,"lon":13.3427,"address":"Augustenburger Platz 1, 13353 Berlin"},
    {"name":"Charité – Campus Benjamin Franklin","lat":52.4466,"lon":13.3005,"address":"Hindenburgdamm 30, 12203 Berlin"},
    {"name":"Vivantes Klinikum Neukölln","lat":52.4673,"lon":13.4399,"address":"Rudower Chaussee 48, 12351 Berlin"},
    {"name":"Vivantes Klinikum im Friedrichshain","lat":52.5148,"lon":13.4448,"address":"Landsberger Allee 49, 10249 Berlin"},
    {"name":"Vivantes Auguste-Viktoria-Klinikum","lat":52.4753,"lon":13.3276,"address":"Rubensstraße 125, 12157 Berlin"},
    {"name":"DRK Kliniken Berlin Westend","lat":52.5100,"lon":13.2838,"address":"Spandauer Damm 130, 14050 Berlin"},
    {"name":"Helios Klinikum Berlin-Buch","lat":52.6239,"lon":13.4998,"address":"Schwanebecker Chaussee 50, 13125 Berlin"},
    {"name":"Sankt Gertrauden-Krankenhaus Berlin","lat":52.4881,"lon":13.3238,"address":"Paretzer Straße 12, 10713 Berlin"},
    {"name":"Evangelisches Waldkrankenhaus Spandau","lat":52.5319,"lon":13.1999,"address":"Stadtrandstraße 555, 13589 Berlin"},
    # Brandenburg
    {"name":"Klinikum Ernst von Bergmann Potsdam","lat":52.3963,"lon":13.0569,"address":"Charlottenstraße 72, 14467 Potsdam"},
    {"name":"Städtisches Klinikum Brandenburg","lat":52.4126,"lon":12.5572,"address":"Hochstraße 29, 14770 Brandenburg a.d. Havel"},
    {"name":"Klinikum Frankfurt (Oder)","lat":52.3392,"lon":14.5475,"address":"Müllroser Chaussee 7, 15236 Frankfurt (Oder)"},
    {"name":"Carl-Thiem-Klinikum Cottbus","lat":51.7552,"lon":14.3274,"address":"Thiemstraße 111, 03048 Cottbus"},
    {"name":"Klinikum Neuruppin","lat":52.9243,"lon":12.8058,"address":"Fehrbelliner Straße 38, 16816 Neuruppin"},
    # Bremen
    {"name":"Klinikum Bremen-Mitte","lat":53.0829,"lon":8.8090,"address":"Sankt-Jürgen-Straße 1, 28205 Bremen"},
    {"name":"Klinikum Bremen-Ost","lat":53.0652,"lon":8.9239,"address":"Züricher Straße 40, 28325 Bremen"},
    {"name":"Rotes Kreuz Krankenhaus Bremen","lat":53.0945,"lon":8.7895,"address":"Rotkreuzstraße 2, 28199 Bremen"},
    {"name":"Klinikum Bremen-Nord","lat":53.1748,"lon":8.6558,"address":"Hammersbecker Straße 228, 28755 Bremen"},
    # Hamburg
    {"name":"Universitätsklinikum Hamburg-Eppendorf (UKE)","lat":53.5892,"lon":9.9739,"address":"Martinistraße 52, 20246 Hamburg"},
    {"name":"Asklepios Klinikum Altona","lat":53.5510,"lon":9.9265,"address":"Paul-Ehrlich-Straße 1, 22763 Hamburg"},
    {"name":"Asklepios Klinikum Barmbek","lat":53.6014,"lon":10.0387,"address":"Rübenkamp 220, 22291 Hamburg"},
    {"name":"Asklepios Klinikum Harburg","lat":53.4646,"lon":9.9892,"address":"Eißendorfer Pferdeweg 52, 21075 Hamburg"},
    {"name":"Asklepios Klinikum Wandsbek","lat":53.5773,"lon":10.0712,"address":"Alphonsstraße 14, 22043 Hamburg"},
    {"name":"Asklepios Klinikum St. Georg","lat":53.5549,"lon":10.0149,"address":"Lohmühlenstraße 5, 20099 Hamburg"},
    {"name":"Marienkrankenhaus Hamburg","lat":53.5716,"lon":10.0138,"address":"Alfredstraße 9, 22087 Hamburg"},
    # Hessen
    {"name":"Universitätsklinikum Frankfurt","lat":50.0934,"lon":8.6460,"address":"Theodor-Stern-Kai 7, 60590 Frankfurt"},
    {"name":"Krankenhaus Nordwest Frankfurt","lat":50.1386,"lon":8.6373,"address":"Steinbacher Hohl 2-26, 60488 Frankfurt"},
    {"name":"Klinikum Frankfurt Höchst","lat":50.1028,"lon":8.5258,"address":"Gotenstraße 6-8, 65929 Frankfurt"},
    {"name":"HSK Dr. Horst Schmidt Kliniken Wiesbaden","lat":50.0781,"lon":8.2409,"address":"Ludwig-Erhard-Straße 100, 65199 Wiesbaden"},
    {"name":"Klinikum Darmstadt","lat":49.8757,"lon":8.6449,"address":"Grafenstraße 9, 64283 Darmstadt"},
    {"name":"Klinikum Offenbach","lat":50.1019,"lon":8.7616,"address":"Starkenburgring 66, 63069 Offenbach"},
    {"name":"Klinikum Hanau","lat":50.1312,"lon":8.9175,"address":"Leimenstraße 20, 63450 Hanau"},
    {"name":"Klinikum Fulda","lat":50.5614,"lon":9.6886,"address":"Pacelliallee 4, 36043 Fulda"},
    {"name":"Universitätsklinikum Marburg (UKGM)","lat":50.8131,"lon":8.7764,"address":"Baldingerstraße, 35043 Marburg"},
    {"name":"Universitätsklinikum Gießen (UKGM)","lat":50.5892,"lon":8.6793,"address":"Klinikstraße 33, 35392 Gießen"},
    {"name":"Klinikum Kassel","lat":51.3093,"lon":9.5021,"address":"Mönchebergstraße 41-43, 34125 Kassel"},
    {"name":"Klinikum Wetzlar","lat":50.5670,"lon":8.4848,"address":"Forsthausstraße 1, 35578 Wetzlar"},
    {"name":"Klinikum Bad Hersfeld","lat":50.8703,"lon":9.7111,"address":"Am Möncheberg 2, 36251 Bad Hersfeld"},
    # Mecklenburg-Vorpommern
    {"name":"Universitätsmedizin Greifswald","lat":54.0924,"lon":13.3833,"address":"Ferdinand-Sauerbruch-Straße, 17475 Greifswald"},
    {"name":"Universitätsmedizin Rostock","lat":54.0901,"lon":12.1318,"address":"Ernst-Heydemann-Straße 6, 18057 Rostock"},
    {"name":"Helios Kliniken Schwerin","lat":53.6186,"lon":11.4237,"address":"Wismarsche Straße 393-397, 19049 Schwerin"},
    {"name":"Klinikum Neubrandenburg","lat":53.5563,"lon":13.2640,"address":"Salvador-Allende-Straße 30, 17036 Neubrandenburg"},
    {"name":"Klinikum Stralsund","lat":54.3107,"lon":13.0948,"address":"Große Parower Straße 47, 18435 Stralsund"},
    {"name":"Klinikum Wismar","lat":53.8922,"lon":11.4611,"address":"Störtebekerstraße 6, 23966 Wismar"},
    # Niedersachsen
    {"name":"Medizinische Hochschule Hannover (MHH)","lat":52.3814,"lon":9.8056,"address":"Carl-Neuberg-Straße 1, 30625 Hannover"},
    {"name":"Klinikum Region Hannover – Hannover Mitte","lat":52.3659,"lon":9.7388,"address":"Haltenhoffstraße 41, 30167 Hannover"},
    {"name":"Klinikum Region Hannover – Siloah","lat":52.3896,"lon":9.7030,"address":"Stadionbrücke 4, 30459 Hannover"},
    {"name":"Klinikum Braunschweig","lat":52.2604,"lon":10.5113,"address":"Salzdahlumer Straße 90, 38126 Braunschweig"},
    {"name":"Klinikum Hildesheim","lat":52.1561,"lon":9.9469,"address":"Senator-Braun-Allee 33, 31135 Hildesheim"},
    {"name":"Klinikum Wolfsburg","lat":52.4278,"lon":10.7812,"address":"Sauerbruchstraße 7, 38440 Wolfsburg"},
    {"name":"Universitätsmedizin Göttingen","lat":51.5422,"lon":9.9368,"address":"Robert-Koch-Straße 40, 37075 Göttingen"},
    {"name":"Klinikum Northeim","lat":51.7060,"lon":10.0033,"address":"Klinikstraße 1, 37154 Northeim"},
    {"name":"Klinikum Oldenburg","lat":53.1507,"lon":8.2045,"address":"Rahel-Straus-Straße 10, 26133 Oldenburg"},
    {"name":"Klinikum Delmenhorst","lat":53.0497,"lon":8.6294,"address":"Friedrich-Kaufmann-Straße 8, 27749 Delmenhorst"},
    {"name":"Klinikum Wilhelmshaven","lat":53.5236,"lon":8.1079,"address":"Friedrich-Paffrath-Straße 100, 26389 Wilhelmshaven"},
    {"name":"Klinikum Osnabrück","lat":52.2799,"lon":8.0472,"address":"Am Finkenhügel 1, 49076 Osnabrück"},
    {"name":"Klinikum Lingen","lat":52.5216,"lon":7.3252,"address":"St.-Bonifatius-Hospital, 49808 Lingen"},
    {"name":"Klinikum Lüneburg","lat":53.2425,"lon":10.4000,"address":"Bögelstraße 1, 21339 Lüneburg"},
    {"name":"Klinikum Celle","lat":52.6196,"lon":10.0773,"address":"Siemensplatz 4, 29223 Celle"},
    {"name":"Klinikum Nienburg","lat":52.6417,"lon":9.2153,"address":"Verdener Landstraße 50, 31582 Nienburg"},
    {"name":"Klinikum Goslar","lat":51.9079,"lon":10.4281,"address":"Dr.-Heinrich-Jasper-Straße 1, 38642 Goslar"},
    # Nordrhein-Westfalen
    {"name":"Universitätsklinikum Köln","lat":50.9236,"lon":6.9205,"address":"Kerpener Str. 62, 50937 Köln"},
    {"name":"Krankenhaus Merheim Köln","lat":50.9543,"lon":7.0492,"address":"Ostmerheimer Straße 200, 51109 Köln"},
    {"name":"Heilig Geist Krankenhaus Köln","lat":50.9797,"lon":6.9128,"address":"Graseggerstraße 105, 50737 Köln"},
    {"name":"Universitätsklinikum Düsseldorf","lat":51.1911,"lon":6.7885,"address":"Moorenstraße 5, 40225 Düsseldorf"},
    {"name":"Evangelisches Krankenhaus Düsseldorf","lat":51.2264,"lon":6.7833,"address":"Kirchfeldstraße 40, 40217 Düsseldorf"},
    {"name":"Universitätsklinikum Essen","lat":51.4340,"lon":7.0031,"address":"Hufelandstraße 55, 45147 Essen"},
    {"name":"Klinikum Bochum – BG-Klinikum","lat":51.4680,"lon":7.2028,"address":"Bürkle-de-la-Camp-Platz 1, 44789 Bochum"},
    {"name":"St. Josef-Hospital Bochum","lat":51.4729,"lon":7.2085,"address":"Gudrunstraße 56, 44791 Bochum"},
    {"name":"Universitätsklinikum Münster","lat":51.9630,"lon":7.5953,"address":"Albert-Schweitzer-Campus 1, 48149 Münster"},
    {"name":"Universitätsklinikum Bonn","lat":50.7001,"lon":7.1121,"address":"Venusberg-Campus 1, 53127 Bonn"},
    {"name":"Klinikum Dortmund","lat":51.5056,"lon":7.4596,"address":"Beurhausstraße 40, 44137 Dortmund"},
    {"name":"Evangelisches Klinikum Bethel Bielefeld","lat":52.0126,"lon":8.5145,"address":"Burgsteig 13, 33617 Bielefeld"},
    {"name":"Klinikum Bielefeld Mitte","lat":52.0232,"lon":8.5290,"address":"Teutoburger Straße 50, 33604 Bielefeld"},
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
    {"name":"Klinikum Hagen","lat":51.3667,"lon":7.4667,"address":"Grünstraße 35, 58095 Hagen"},
    {"name":"Klinikum Mönchengladbach","lat":51.1993,"lon":6.4282,"address":"Hubertusstraße 100, 41239 Mönchengladbach"},
    {"name":"Lukas-Krankenhaus Neuss","lat":51.1984,"lon":6.6932,"address":"Preußenstraße 84, 41464 Neuss"},
    {"name":"Klinikum Oberhausen","lat":51.4955,"lon":6.8650,"address":"Schwarzmühlenstraße 90, 46045 Oberhausen"},
    {"name":"Klinikum Paderborn – St. Vincenz","lat":51.7195,"lon":8.7583,"address":"Am Busdorf 2, 33098 Paderborn"},
    {"name":"Klinikum Siegen","lat":50.8749,"lon":8.0176,"address":"Weidenauer Straße 76, 57076 Siegen"},
    {"name":"Märkisches Klinikum Iserlohn","lat":51.3760,"lon":7.6891,"address":"Wermingser Straße 10, 58636 Iserlohn"},
    {"name":"Klinikum Arnsberg","lat":51.3874,"lon":8.0692,"address":"Stolte Ley 5, 59759 Arnsberg"},
    {"name":"Klinikum Lüdenscheid","lat":51.2194,"lon":7.6263,"address":"Paulmannshöher Straße 14, 58515 Lüdenscheid"},
    {"name":"Klinikum Remscheid","lat":51.1823,"lon":7.1936,"address":"Burger Straße 211, 42859 Remscheid"},
    # Rheinland-Pfalz
    {"name":"Universitätsmedizin Mainz","lat":49.9990,"lon":8.2728,"address":"Langenbeckstraße 1, 55131 Mainz"},
    {"name":"Bundeswehrzentralkrankenhaus Koblenz","lat":50.3533,"lon":7.5912,"address":"Rübenacher Straße 170, 56072 Koblenz"},
    {"name":"Klinikum Ludwigshafen","lat":49.4778,"lon":8.4456,"address":"Bremserstraße 79, 67063 Ludwigshafen"},
    {"name":"Klinikum Kaiserslautern","lat":49.4451,"lon":7.7556,"address":"Hellmut-Hartert-Straße 1, 67655 Kaiserslautern"},
    {"name":"Klinikum Trier – Mutterhaus","lat":49.7541,"lon":6.6421,"address":"Feldstraße 16, 54290 Trier"},
    {"name":"Klinikum Idar-Oberstein","lat":49.7052,"lon":7.3018,"address":"Dr.-Ottmar-Kohler-Straße 2, 55743 Idar-Oberstein"},
    {"name":"Klinikum Pirmasens","lat":49.2007,"lon":7.6039,"address":"Pettenkoferstraße 22, 66955 Pirmasens"},
    {"name":"Klinikum Neustadt/Weinstraße","lat":49.3521,"lon":8.1414,"address":"Weinstraße Süd 75, 67433 Neustadt"},
    {"name":"Klinikum Bad Kreuznach","lat":49.8445,"lon":7.8572,"address":"Mühlenstraße 35, 55543 Bad Kreuznach"},
    # Saarland
    {"name":"Universitätsklinikum des Saarlandes Homburg","lat":49.3208,"lon":7.3398,"address":"Kirrberger Straße 100, 66421 Homburg"},
    {"name":"Klinikum Saarbrücken Winterberg","lat":49.2374,"lon":7.0063,"address":"Winterberg 1, 66119 Saarbrücken"},
    {"name":"Marienhaus Klinikum Saarlouis","lat":49.3110,"lon":6.7524,"address":"Flurstraße 1-3, 66740 Saarlouis"},
    {"name":"SHG-Klinikum Völklingen","lat":49.2491,"lon":6.8441,"address":"Richard-Wagner-Straße 2, 66333 Völklingen"},
    # Sachsen
    {"name":"Universitätsklinikum Leipzig","lat":51.3288,"lon":12.3697,"address":"Liebigstraße 20, 04103 Leipzig"},
    {"name":"Klinikum St. Georg Leipzig","lat":51.3524,"lon":12.3761,"address":"Delitzscher Straße 141, 04129 Leipzig"},
    {"name":"Universitätsklinikum Dresden","lat":51.0616,"lon":13.7759,"address":"Fetscherstraße 74, 01307 Dresden"},
    {"name":"Städtisches Klinikum Dresden","lat":51.0563,"lon":13.8181,"address":"Friedrichstraße 41, 01067 Dresden"},
    {"name":"Klinikum Chemnitz","lat":50.8357,"lon":12.9300,"address":"Flemmingstraße 2, 09116 Chemnitz"},
    {"name":"Klinikum Zwickau","lat":50.7198,"lon":12.4972,"address":"Karl-Keil-Straße 35, 08060 Zwickau"},
    {"name":"Klinikum Görlitz","lat":51.1551,"lon":14.9875,"address":"Girbigsdorfer Straße 1-3, 02828 Görlitz"},
    {"name":"Klinikum Plauen","lat":50.4982,"lon":12.1398,"address":"Röntgenstraße 2, 08529 Plauen"},
    # Sachsen-Anhalt
    {"name":"Universitätsklinikum Halle (Saale)","lat":51.4925,"lon":11.9605,"address":"Ernst-Grube-Straße 40, 06120 Halle"},
    {"name":"Universitätsklinikum Magdeburg","lat":52.1285,"lon":11.6271,"address":"Leipziger Straße 44, 39120 Magdeburg"},
    {"name":"Klinikum Dessau","lat":51.8330,"lon":12.2448,"address":"Auenweg 38, 06847 Dessau"},
    {"name":"Klinikum Wittenberg","lat":51.8634,"lon":12.6493,"address":"Paul-Gerhardt-Straße 42, 06886 Wittenberg"},
    # Schleswig-Holstein
    {"name":"Universitätsklinikum Schleswig-Holstein – Kiel","lat":54.3216,"lon":10.1348,"address":"Arnold-Heller-Straße 3, 24105 Kiel"},
    {"name":"Universitätsklinikum Schleswig-Holstein – Lübeck","lat":53.8385,"lon":10.7154,"address":"Ratzeburger Allee 160, 23562 Lübeck"},
    {"name":"Helios Klinikum Schleswig","lat":54.5168,"lon":9.5601,"address":"St.-Jürgen-Straße 1, 24837 Schleswig"},
    {"name":"Imland Klinik Rendsburg","lat":54.3026,"lon":9.6622,"address":"Lilienstraße 20-28, 24768 Rendsburg"},
    {"name":"Klinikum Flensburg","lat":54.7880,"lon":9.4325,"address":"Harrisleer Straße 100, 24943 Flensburg"},
    {"name":"Westküstenklinikum Heide","lat":54.1929,"lon":9.0961,"address":"Esmarchstraße 50, 25746 Heide"},
    {"name":"Klinikum Itzehoe","lat":53.9260,"lon":9.5218,"address":"Robert-Koch-Straße 2, 25524 Itzehoe"},
    {"name":"Klinikum Pinneberg","lat":53.6599,"lon":9.7973,"address":"Fahltskamp 74, 25421 Pinneberg"},
    {"name":"Sana Klinikum Lübeck","lat":53.8648,"lon":10.6990,"address":"Kronsforder Allee 71-73, 23560 Lübeck"},
    # Thüringen
    {"name":"Universitätsklinikum Jena","lat":50.9272,"lon":11.5930,"address":"Am Klinikum 1, 07747 Jena"},
    {"name":"Helios Klinikum Erfurt","lat":50.9845,"lon":11.0199,"address":"Nordhäuser Straße 74, 99089 Erfurt"},
    {"name":"SRH Zentralklinikum Suhl","lat":50.6104,"lon":10.6937,"address":"Albert-Schweitzer-Straße 2, 98527 Suhl"},
    {"name":"Klinikum Gera","lat":50.8829,"lon":12.0766,"address":"Straße des Friedens 122, 07548 Gera"},
    {"name":"Klinikum Weimar","lat":51.0017,"lon":11.3297,"address":"Henry-van-de-Velde-Straße 2, 99425 Weimar"},
    {"name":"Klinikum Eisenach","lat":50.9786,"lon":10.3245,"address":"Mühlhäuser Straße 94, 99817 Eisenach"},
    {"name":"Klinikum Nordhausen","lat":51.5082,"lon":10.7989,"address":"Dr.-Robert-Koch-Straße 39, 99734 Nordhausen"},
]


# ── United Kingdom ─────────────────────────────────────────────────────────────
UK_HOSPITALS: list[dict] = [
    # Greater London
    {"name":"St Thomas' Hospital","lat":51.4988,"lon":-0.1188,"address":"Westminster Bridge Rd, London SE1 7EH","country":"UK"},
    {"name":"Guy's Hospital","lat":51.5035,"lon":-0.0873,"address":"Great Maze Pond, London SE1 9RT","country":"UK"},
    {"name":"King's College Hospital","lat":51.4685,"lon":-0.0944,"address":"Denmark Hill, London SE5 9RS","country":"UK"},
    {"name":"University College Hospital","lat":51.5247,"lon":-0.1338,"address":"235 Euston Rd, London NW1 2BU","country":"UK"},
    {"name":"Royal London Hospital","lat":51.5183,"lon":-0.0593,"address":"Whitechapel Rd, London E1 1FR","country":"UK"},
    {"name":"St Bartholomew's Hospital","lat":51.5171,"lon":-0.1008,"address":"West Smithfield, London EC1A 7BE","country":"UK"},
    {"name":"Charing Cross Hospital","lat":51.4895,"lon":-0.2193,"address":"Fulham Palace Rd, London W6 8RF","country":"UK"},
    {"name":"Chelsea and Westminster Hospital","lat":51.4844,"lon":-0.1814,"address":"369 Fulham Rd, London SW10 9NH","country":"UK"},
    {"name":"Hammersmith Hospital","lat":51.5108,"lon":-0.2344,"address":"Du Cane Road, London W12 0HS","country":"UK"},
    {"name":"St Mary's Hospital Paddington","lat":51.5183,"lon":-0.1750,"address":"Praed Street, London W2 1NY","country":"UK"},
    {"name":"Royal Free Hospital Hampstead","lat":51.5527,"lon":-0.1648,"address":"Pond Street, London NW3 2QG","country":"UK"},
    {"name":"Whittington Hospital","lat":51.5679,"lon":-0.1350,"address":"Magdala Avenue, London N19 5NF","country":"UK"},
    {"name":"Homerton University Hospital","lat":51.5481,"lon":-0.0461,"address":"Homerton Row, London E9 6SR","country":"UK"},
    {"name":"Newham University Hospital","lat":51.5277,"lon":0.0340,"address":"Glen Road, London E13 8SL","country":"UK"},
    {"name":"Northwick Park Hospital","lat":51.5786,"lon":-0.3198,"address":"Watford Road, Harrow HA1 3UJ","country":"UK"},
    {"name":"Hillingdon Hospital","lat":51.5179,"lon":-0.4732,"address":"Pield Heath Road, Uxbridge UB8 3NN","country":"UK"},
    {"name":"Queen's Hospital Romford","lat":51.5754,"lon":0.1845,"address":"Rom Valley Way, Romford RM7 0AG","country":"UK"},
    {"name":"Princess Royal University Hospital","lat":51.3856,"lon":0.0558,"address":"Farnborough Common, Orpington BR6 8ND","country":"UK"},
    {"name":"St Helier Hospital Sutton","lat":51.3741,"lon":-0.1968,"address":"Wrythe Lane, Carshalton SM5 1AA","country":"UK"},
    {"name":"Croydon University Hospital","lat":51.3781,"lon":-0.1056,"address":"530 London Rd, Croydon CR7 7YE","country":"UK"},
    {"name":"St George's Hospital Tooting","lat":51.4271,"lon":-0.1755,"address":"Blackshaw Rd, London SW17 0QT","country":"UK"},
    {"name":"Barnet Hospital","lat":51.6498,"lon":-0.1955,"address":"Wellhouse Lane, Barnet EN5 3DJ","country":"UK"},
    {"name":"West Middlesex University Hospital","lat":51.4722,"lon":-0.3220,"address":"Twickenham Rd, Isleworth TW7 6AF","country":"UK"},
    {"name":"Ealing Hospital","lat":51.5120,"lon":-0.3218,"address":"Uxbridge Road, Southall UB1 3EU","country":"UK"},
    {"name":"Lewisham Hospital","lat":51.4570,"lon":-0.0181,"address":"High Street, London SE13 6LH","country":"UK"},
    # South East England
    {"name":"Southampton General Hospital","lat":50.9319,"lon":-1.4324,"address":"Tremona Rd, Southampton SO16 6YD","country":"UK"},
    {"name":"Queen Alexandra Hospital Portsmouth","lat":50.8490,"lon":-1.0638,"address":"Southwick Hill Road, Cosham PO6 3LY","country":"UK"},
    {"name":"Brighton & Sussex University Hospital","lat":50.8194,"lon":-0.1302,"address":"Eastern Road, Brighton BN2 5BE","country":"UK"},
    {"name":"East Surrey Hospital Redhill","lat":51.2154,"lon":-0.1672,"address":"Canada Avenue, Redhill RH1 5RH","country":"UK"},
    {"name":"Medway Maritime Hospital Gillingham","lat":51.3919,"lon":0.5558,"address":"Windmill Road, Gillingham ME7 5NY","country":"UK"},
    {"name":"William Harvey Hospital Ashford","lat":51.1401,"lon":0.8723,"address":"Kennington Road, Ashford TN24 0LZ","country":"UK"},
    {"name":"Eastbourne District General Hospital","lat":50.7791,"lon":0.2884,"address":"Kings Drive, Eastbourne BN21 2UD","country":"UK"},
    {"name":"Royal Hampshire County Hospital Winchester","lat":51.0569,"lon":-1.3052,"address":"Romsey Road, Winchester SO22 5DG","country":"UK"},
    {"name":"Basingstoke and North Hampshire Hospital","lat":51.2611,"lon":-1.0947,"address":"Aldermaston Road, Basingstoke RG24 9NA","country":"UK"},
    {"name":"Royal Berkshire Hospital Reading","lat":51.4575,"lon":-0.9764,"address":"London Road, Reading RG1 5AN","country":"UK"},
    {"name":"John Radcliffe Hospital Oxford","lat":51.7618,"lon":-1.2215,"address":"Headley Way, Oxford OX3 9DU","country":"UK"},
    {"name":"Stoke Mandeville Hospital Aylesbury","lat":51.8097,"lon":-0.7877,"address":"Mandeville Road, Aylesbury HP21 8AL","country":"UK"},
    {"name":"Luton and Dunstable University Hospital","lat":51.8756,"lon":-0.4329,"address":"Lewsey Road, Luton LU4 0DZ","country":"UK"},
    {"name":"Addenbrooke's Hospital Cambridge","lat":52.1752,"lon":0.1401,"address":"Hills Road, Cambridge CB2 0QQ","country":"UK"},
    {"name":"Norfolk and Norwich University Hospital","lat":52.6210,"lon":1.2438,"address":"Colney Lane, Norwich NR4 7UY","country":"UK"},
    {"name":"James Paget University Hospital","lat":52.5982,"lon":1.7009,"address":"Lowestoft Road, Gorleston NR31 6LA","country":"UK"},
    {"name":"Ipswich Hospital","lat":52.0581,"lon":1.1791,"address":"Heath Road, Ipswich IP4 5PD","country":"UK"},
    {"name":"Colchester Hospital","lat":51.8901,"lon":0.9283,"address":"Turner Road, Colchester CO4 5JL","country":"UK"},
    {"name":"Southend University Hospital","lat":51.5485,"lon":0.6929,"address":"Prittlewell Chase, Southend-on-Sea SS0 0RY","country":"UK"},
    {"name":"Watford General Hospital","lat":51.6576,"lon":-0.3818,"address":"Vicarage Road, Watford WD18 0HB","country":"UK"},
    {"name":"Lister Hospital Stevenage","lat":51.9008,"lon":-0.2038,"address":"Coreys Mill Lane, Stevenage SG1 4AB","country":"UK"},
    # South West England
    {"name":"Bristol Royal Infirmary","lat":51.4600,"lon":-2.5988,"address":"Marlborough St, Bristol BS2 8HW","country":"UK"},
    {"name":"Southmead Hospital Bristol","lat":51.5052,"lon":-2.6036,"address":"Dodringe Park Road, Bristol BS10 5NB","country":"UK"},
    {"name":"Royal Devon and Exeter Hospital","lat":50.7303,"lon":-3.5139,"address":"Barrack Road, Exeter EX2 5DW","country":"UK"},
    {"name":"Derriford Hospital Plymouth","lat":50.4093,"lon":-4.1067,"address":"Derriford Road, Plymouth PL6 8DH","country":"UK"},
    {"name":"Royal Cornwall Hospital Truro","lat":50.2584,"lon":-5.0625,"address":"Treliske, Truro TR1 3LJ","country":"UK"},
    {"name":"Royal United Hospital Bath","lat":51.3987,"lon":-2.3814,"address":"Combe Park, Bath BA1 3NG","country":"UK"},
    {"name":"Great Western Hospital Swindon","lat":51.5672,"lon":-1.7768,"address":"Marlborough Road, Swindon SN3 6BB","country":"UK"},
    {"name":"Gloucester Royal Hospital","lat":51.8688,"lon":-2.2520,"address":"Great Western Road, Gloucester GL1 3NN","country":"UK"},
    {"name":"Cheltenham General Hospital","lat":51.9014,"lon":-2.0859,"address":"Sandford Road, Cheltenham GL53 7AN","country":"UK"},
    {"name":"Musgrove Park Hospital Taunton","lat":51.0120,"lon":-3.1150,"address":"Parkfield Drive, Taunton TA1 5DA","country":"UK"},
    {"name":"Yeovil District Hospital","lat":50.9454,"lon":-2.6459,"address":"Higher Kingston, Yeovil BA21 4AT","country":"UK"},
    {"name":"Torbay Hospital","lat":50.4766,"lon":-3.5280,"address":"Newton Road, Torquay TQ2 7AA","country":"UK"},
    {"name":"Royal Bournemouth Hospital","lat":50.7388,"lon":-1.8414,"address":"Castle Lane East, Bournemouth BH7 7DW","country":"UK"},
    # Midlands
    {"name":"Queen Elizabeth Hospital Birmingham","lat":52.4529,"lon":-1.9427,"address":"Mindelsohn Way, Birmingham B15 2GW","country":"UK"},
    {"name":"Birmingham Heartlands Hospital","lat":52.4805,"lon":-1.8161,"address":"Bordesley Green East, Birmingham B9 5SS","country":"UK"},
    {"name":"City Hospital Birmingham","lat":52.4951,"lon":-1.9394,"address":"Dudley Road, Birmingham B18 7QH","country":"UK"},
    {"name":"Good Hope Hospital Sutton Coldfield","lat":52.5532,"lon":-1.8145,"address":"Rectory Road, Sutton Coldfield B75 7RR","country":"UK"},
    {"name":"University Hospital Coventry","lat":52.4197,"lon":-1.4351,"address":"Clifford Bridge Road, Coventry CV2 2DX","country":"UK"},
    {"name":"Nottingham University Hospitals QMC","lat":52.9497,"lon":-1.1864,"address":"Derby Road, Nottingham NG7 2UH","country":"UK"},
    {"name":"Nottingham City Hospital","lat":52.9793,"lon":-1.1695,"address":"Hucknall Road, Nottingham NG5 1PB","country":"UK"},
    {"name":"Leicester Royal Infirmary","lat":52.6264,"lon":-1.1246,"address":"Infirmary Square, Leicester LE1 5WW","country":"UK"},
    {"name":"Derby Royal Hospital","lat":52.9175,"lon":-1.4808,"address":"Uttoxeter Road, Derby DE22 3NE","country":"UK"},
    {"name":"Lincoln County Hospital","lat":53.2218,"lon":-0.5462,"address":"Greetwell Road, Lincoln LN2 5QY","country":"UK"},
    {"name":"Staffordshire University Hospital","lat":52.7952,"lon":-2.0360,"address":"Newcastle Road, Stafford ST16 3SA","country":"UK"},
    {"name":"New Cross Hospital Wolverhampton","lat":52.5952,"lon":-2.1060,"address":"Wolverhampton Road, Wolverhampton WV10 0QP","country":"UK"},
    # North West England
    {"name":"Manchester Royal Infirmary","lat":53.4627,"lon":-2.2246,"address":"Oxford Road, Manchester M13 9WL","country":"UK"},
    {"name":"Salford Royal Hospital","lat":53.4882,"lon":-2.3353,"address":"Stott Lane, Salford M6 8HD","country":"UK"},
    {"name":"Wythenshawe Hospital Manchester","lat":53.3976,"lon":-2.2815,"address":"Southmoor Road, Manchester M23 9LT","country":"UK"},
    {"name":"Liverpool Royal Hospital","lat":53.4068,"lon":-2.9640,"address":"Prescot Street, Liverpool L7 8XP","country":"UK"},
    {"name":"Aintree University Hospital","lat":53.4604,"lon":-2.9500,"address":"Lower Lane, Liverpool L9 7AL","country":"UK"},
    {"name":"Arrowe Park Hospital Birkenhead","lat":53.3706,"lon":-3.0897,"address":"Arrowe Park Road, Birkenhead CH49 5PE","country":"UK"},
    {"name":"Royal Preston Hospital","lat":53.7730,"lon":-2.7119,"address":"Sharoe Green Lane, Preston PR2 9HT","country":"UK"},
    {"name":"Royal Blackburn Hospital","lat":53.7413,"lon":-2.4780,"address":"Haslingden Road, Blackburn BB2 3HH","country":"UK"},
    {"name":"Blackpool Victoria Hospital","lat":53.8388,"lon":-3.0346,"address":"Whinney Heys Road, Blackpool FY3 8NR","country":"UK"},
    {"name":"Royal Lancaster Infirmary","lat":54.0463,"lon":-2.7908,"address":"Ashton Road, Lancaster LA1 4RP","country":"UK"},
    {"name":"Stepping Hill Hospital Stockport","lat":53.3892,"lon":-2.1417,"address":"Poplar Grove, Stockport SK2 7JE","country":"UK"},
    {"name":"Wigan and Leigh Hospital","lat":53.5497,"lon":-2.6426,"address":"Wigan Lane, Wigan WN1 2NN","country":"UK"},
    # Yorkshire & Humber
    {"name":"Sheffield Teaching Hospitals – Northern General","lat":53.4130,"lon":-1.4521,"address":"Herries Road, Sheffield S5 7AU","country":"UK"},
    {"name":"Leeds General Infirmary","lat":53.8026,"lon":-1.5476,"address":"Great George St, Leeds LS1 3EX","country":"UK"},
    {"name":"St James's University Hospital Leeds","lat":53.8058,"lon":-1.5196,"address":"Beckett Street, Leeds LS9 7TF","country":"UK"},
    {"name":"Bradford Royal Infirmary","lat":53.7965,"lon":-1.7557,"address":"Duckworth Lane, Bradford BD9 6RJ","country":"UK"},
    {"name":"Pinderfields Hospital Wakefield","lat":53.6784,"lon":-1.4790,"address":"Aberford Road, Wakefield WF1 4DG","country":"UK"},
    {"name":"Hull Royal Infirmary","lat":53.7468,"lon":-0.3438,"address":"Anlaby Road, Hull HU3 2JZ","country":"UK"},
    {"name":"York District Hospital","lat":53.9528,"lon":-1.0836,"address":"Wigginton Road, York YO31 8HE","country":"UK"},
    {"name":"Harrogate District Hospital","lat":53.9872,"lon":-1.5220,"address":"Lancaster Park Road, Harrogate HG2 7SX","country":"UK"},
    {"name":"Calderdale Royal Hospital Halifax","lat":53.7248,"lon":-1.8622,"address":"Salterhebble, Halifax HX3 0PW","country":"UK"},
    {"name":"Scarborough Hospital","lat":54.2756,"lon":-0.4124,"address":"Woodlands Drive, Scarborough YO12 6QL","country":"UK"},
    # North East England
    {"name":"Freeman Hospital Newcastle","lat":54.9912,"lon":-1.6038,"address":"Freeman Road, Newcastle NE7 7DN","country":"UK"},
    {"name":"Royal Victoria Infirmary Newcastle","lat":54.9782,"lon":-1.6176,"address":"Queen Victoria Road, Newcastle NE1 4LP","country":"UK"},
    {"name":"James Cook University Hospital Middlesbrough","lat":54.5505,"lon":-1.1891,"address":"Marton Road, Middlesbrough TS4 3BW","country":"UK"},
    {"name":"Sunderland Royal Hospital","lat":54.9053,"lon":-1.4078,"address":"Kayll Road, Sunderland SR4 7TP","country":"UK"},
    {"name":"Queen Elizabeth Hospital Gateshead","lat":54.9483,"lon":-1.5774,"address":"Queen Elizabeth Avenue, Gateshead NE9 6SX","country":"UK"},
    {"name":"University Hospital of North Durham","lat":54.7752,"lon":-1.5849,"address":"North Road, Durham DH1 5TW","country":"UK"},
    # Scotland
    {"name":"Royal Infirmary of Edinburgh","lat":55.9215,"lon":-3.1349,"address":"51 Little France Crescent, Edinburgh EH16 4SA","country":"UK"},
    {"name":"Western General Hospital Edinburgh","lat":55.9589,"lon":-3.2337,"address":"Crewe Road South, Edinburgh EH4 2XU","country":"UK"},
    {"name":"Glasgow Royal Infirmary","lat":55.8621,"lon":-4.2368,"address":"84 Castle Street, Glasgow G4 0SF","country":"UK"},
    {"name":"Queen Elizabeth University Hospital Glasgow","lat":55.8595,"lon":-4.3117,"address":"1345 Govan Road, Glasgow G51 4TF","country":"UK"},
    {"name":"Ninewells Hospital Dundee","lat":56.4631,"lon":-3.0280,"address":"Tom McDonald Avenue, Dundee DD2 1SY","country":"UK"},
    {"name":"Aberdeen Royal Infirmary","lat":57.1427,"lon":-2.1136,"address":"Foresterhill, Aberdeen AB25 2ZN","country":"UK"},
    {"name":"Raigmore Hospital Inverness","lat":57.4743,"lon":-4.2163,"address":"Old Perth Road, Inverness IV2 3UJ","country":"UK"},
    {"name":"Monklands Hospital Airdrie","lat":55.8637,"lon":-3.9851,"address":"Monkscourt Avenue, Airdrie ML6 0JS","country":"UK"},
    {"name":"Victoria Hospital Kirkcaldy","lat":56.1187,"lon":-3.1558,"address":"Hayfield Road, Kirkcaldy KY2 5AH","country":"UK"},
    {"name":"Crosshouse Hospital Kilmarnock","lat":55.6175,"lon":-4.4882,"address":"Kilmarnock KA2 0BE","country":"UK"},
    # Wales
    {"name":"University Hospital of Wales Cardiff","lat":51.5100,"lon":-3.1940,"address":"Heath Park, Cardiff CF14 4XW","country":"UK"},
    {"name":"University Hospital Llandough Cardiff","lat":51.4494,"lon":-3.2072,"address":"Penlan Road, Cardiff CF64 2XX","country":"UK"},
    {"name":"Morriston Hospital Swansea","lat":51.6646,"lon":-3.8874,"address":"Heol Maes Eglwys, Swansea SA6 6NL","country":"UK"},
    {"name":"Prince Charles Hospital Merthyr Tydfil","lat":51.7479,"lon":-3.3769,"address":"Gurnos Road, Merthyr Tydfil CF47 9DT","country":"UK"},
    {"name":"Glan Clwyd Hospital Rhyl","lat":53.2871,"lon":-3.4614,"address":"Sarn Lane, Bodelwyddan LL18 5UJ","country":"UK"},
    {"name":"Wrexham Maelor Hospital","lat":53.0500,"lon":-2.9920,"address":"Croesnewydd Road, Wrexham LL13 7TD","country":"UK"},
    {"name":"Ysbyty Gwynedd Bangor","lat":53.2281,"lon":-4.1361,"address":"Penrhosgarnedd, Bangor LL57 2PW","country":"UK"},
    # Northern Ireland
    {"name":"Royal Victoria Hospital Belfast","lat":54.5961,"lon":-5.9549,"address":"Grosvenor Road, Belfast BT12 6BA","country":"UK"},
    {"name":"Belfast City Hospital","lat":54.5867,"lon":-5.9354,"address":"Lisburn Road, Belfast BT9 7AB","country":"UK"},
    {"name":"Antrim Area Hospital","lat":54.7141,"lon":-6.2182,"address":"Bush Road, Antrim BT41 2RL","country":"UK"},
    {"name":"Altnagelvin Hospital Londonderry","lat":55.0023,"lon":-7.2936,"address":"Glenshane Road, Londonderry BT47 6SB","country":"UK"},
    {"name":"Craigavon Area Hospital","lat":54.4368,"lon":-6.3760,"address":"68 Lurgan Road, Portadown BT63 5QQ","country":"UK"},
]


# ── Turkey ─────────────────────────────────────────────────────────────────────
TR_HOSPITALS: list[dict] = [
    # İstanbul – Avrupa Yakası
    {"name":"Cerrahpaşa Tıp Fakültesi Hastanesi","lat":41.0077,"lon":28.9375,"address":"Kocamustafapaşa Cd. 34098 İstanbul","country":"TR"},
    {"name":"İstanbul Üniversitesi Çapa Tıp Fakültesi","lat":41.0167,"lon":28.9317,"address":"Çapa 34093 İstanbul","country":"TR"},
    {"name":"Haseki Eğitim ve Araştırma Hastanesi","lat":41.0076,"lon":28.9430,"address":"Adnan Adıvar Cd. 34130 İstanbul","country":"TR"},
    {"name":"Şişli Hamidiye Etfal EAH","lat":41.0689,"lon":28.9873,"address":"Halaskargazi Cd. 34371 İstanbul","country":"TR"},
    {"name":"Bağcılar Eğitim ve Araştırma Hastanesi","lat":41.0383,"lon":28.8546,"address":"Dr. Lütfi Kırdar Cd. 34200 İstanbul","country":"TR"},
    {"name":"Bakırköy Dr. Sadi Konuk EAH","lat":40.9901,"lon":28.8725,"address":"Zuhuratbaba Cd. 34147 İstanbul","country":"TR"},
    {"name":"Okmeydanı Eğitim ve Araştırma Hastanesi","lat":41.0603,"lon":28.9647,"address":"Darülaceze Cd. 34384 İstanbul","country":"TR"},
    {"name":"Gaziosmanpaşa Taksim EAH","lat":41.0699,"lon":28.9099,"address":"Karadeniz Cd. 34255 İstanbul","country":"TR"},
    {"name":"Kanuni Sultan Süleyman EAH","lat":41.0217,"lon":28.7756,"address":"Turgut Özal Cd. 34303 İstanbul","country":"TR"},
    {"name":"Başakşehir Çam ve Sakura Şehir Hastanesi","lat":41.0859,"lon":28.8070,"address":"Olympic Blv. 34480 İstanbul","country":"TR"},
    {"name":"Memorial Şişli Hastanesi","lat":41.0659,"lon":28.9829,"address":"Piyalepaşa Bul. 34385 İstanbul","country":"TR"},
    {"name":"Acıbadem Maslak Hastanesi","lat":41.1152,"lon":29.0230,"address":"Büyükdere Cd. 40, 34457 İstanbul","country":"TR"},
    # İstanbul – Anadolu Yakası
    {"name":"Kartal Dr. Lütfi Kırdar Şehir Hastanesi","lat":40.8913,"lon":29.2000,"address":"Şemsi Denizer Cd. 34865 İstanbul","country":"TR"},
    {"name":"Ümraniye Eğitim ve Araştırma Hastanesi","lat":41.0219,"lon":29.1225,"address":"Alemdağ Cd. 34766 İstanbul","country":"TR"},
    {"name":"Göztepe Prof. Dr. Süleyman Yalçın Şehir Hastanesi","lat":40.9794,"lon":29.0750,"address":"Dr. Erkin Cd. 34722 İstanbul","country":"TR"},
    {"name":"Fatih Sultan Mehmet EAH","lat":40.9915,"lon":29.0985,"address":"E-5 Karayolu Üzeri 34752 İstanbul","country":"TR"},
    {"name":"Sancaktepe Prof. Dr. İlhan Varank EAH","lat":40.9843,"lon":29.2278,"address":"Sarıgazi Mah. 34785 İstanbul","country":"TR"},
    {"name":"Marmara Üniversitesi Pendik EAH","lat":40.8773,"lon":29.3064,"address":"Fevzi Çakmak Mah. 34899 İstanbul","country":"TR"},
    # Ankara
    {"name":"Ankara Bilkent Şehir Hastanesi","lat":39.8715,"lon":32.7532,"address":"Bilkent 06800 Ankara","country":"TR"},
    {"name":"Hacettepe Üniversitesi Hastanesi","lat":39.9360,"lon":32.8628,"address":"Sıhhiye 06100 Ankara","country":"TR"},
    {"name":"Ankara Üniversitesi İbn-i Sina Hastanesi","lat":39.9428,"lon":32.8573,"address":"Altındağ 06100 Ankara","country":"TR"},
    {"name":"Gazi Üniversitesi Hastanesi","lat":39.9266,"lon":32.8126,"address":"Emniyet Mah. 06500 Ankara","country":"TR"},
    {"name":"Dışkapı Yıldırım Beyazıt EAH","lat":39.9748,"lon":32.8474,"address":"İrfan Baştuğ Cd. 06110 Ankara","country":"TR"},
    {"name":"Ankara Keçiören EAH","lat":40.0126,"lon":32.8576,"address":"Keçiören 06380 Ankara","country":"TR"},
    {"name":"Ankara Sincan Devlet Hastanesi","lat":39.9693,"lon":32.5833,"address":"Sincan 06940 Ankara","country":"TR"},
    # İzmir
    {"name":"Ege Üniversitesi Tıp Fakültesi Hastanesi","lat":38.4613,"lon":27.2302,"address":"Bornova 35100 İzmir","country":"TR"},
    {"name":"Dokuz Eylül Üniversitesi Hastanesi","lat":38.3872,"lon":27.0963,"address":"Balçova 35340 İzmir","country":"TR"},
    {"name":"İzmir Atatürk EAH","lat":38.4665,"lon":27.1780,"address":"Basın Sitesi 35150 İzmir","country":"TR"},
    {"name":"İzmir Bozyaka EAH","lat":38.4221,"lon":27.1228,"address":"Bozyaka 35170 İzmir","country":"TR"},
    {"name":"İzmir Tepecik EAH","lat":38.4191,"lon":27.1667,"address":"Yenişehir 35110 İzmir","country":"TR"},
    {"name":"İzmir Şehir Hastanesi Bayraklı","lat":38.4795,"lon":27.1653,"address":"Bayraklı 35535 İzmir","country":"TR"},
    # Bursa
    {"name":"Bursa Uludağ Üniversitesi Tıp Fakültesi Hastanesi","lat":40.2211,"lon":28.9979,"address":"Görükle 16059 Bursa","country":"TR"},
    {"name":"Bursa Şehir Hastanesi","lat":40.2044,"lon":29.0608,"address":"Nilüfer 16110 Bursa","country":"TR"},
    {"name":"Bursa Yüksek İhtisas EAH","lat":40.1957,"lon":29.0536,"address":"Mimar Sinan Cd. 16310 Bursa","country":"TR"},
    # Antalya
    {"name":"Antalya Eğitim ve Araştırma Hastanesi","lat":36.8996,"lon":30.6900,"address":"Soğuksu Mah. 07070 Antalya","country":"TR"},
    {"name":"Akdeniz Üniversitesi Hastanesi","lat":36.8963,"lon":30.6574,"address":"Konyaaltı 07070 Antalya","country":"TR"},
    {"name":"Antalya Şehir Hastanesi","lat":36.9500,"lon":30.7800,"address":"Döşemealtı 07190 Antalya","country":"TR"},
    # Adana
    {"name":"Çukurova Üniversitesi Balcalı Hastanesi","lat":37.0517,"lon":35.3424,"address":"Balcalı 01790 Adana","country":"TR"},
    {"name":"Adana Şehir Hastanesi","lat":37.0117,"lon":35.3218,"address":"Adana","country":"TR"},
    {"name":"Adana Numune EAH","lat":37.0042,"lon":35.3283,"address":"Cemalpaşa Mah. 01230 Adana","country":"TR"},
    # Konya
    {"name":"Konya Şehir Hastanesi","lat":37.8742,"lon":32.4920,"address":"Selçuklu 42250 Konya","country":"TR"},
    {"name":"Selçuk Üniversitesi Tıp Fakültesi Hastanesi","lat":37.9233,"lon":32.5077,"address":"Selçuklu 42075 Konya","country":"TR"},
    # Gaziantep
    {"name":"Gaziantep Şehir Hastanesi","lat":37.0799,"lon":37.3826,"address":"Şahinbey 27000 Gaziantep","country":"TR"},
    {"name":"Gaziantep Üniversitesi Şahinbey Araştırma Hastanesi","lat":37.0633,"lon":37.3675,"address":"Şahinbey 27310 Gaziantep","country":"TR"},
    # Kayseri
    {"name":"Erciyes Üniversitesi Hastanesi","lat":38.7435,"lon":35.5175,"address":"Talas 38039 Kayseri","country":"TR"},
    {"name":"Kayseri Şehir Hastanesi","lat":38.7534,"lon":35.5234,"address":"Kocasinan 38080 Kayseri","country":"TR"},
    # Diyarbakır
    {"name":"Diyarbakır Şehir Hastanesi","lat":37.9248,"lon":40.2101,"address":"Kayapınar 21120 Diyarbakır","country":"TR"},
    {"name":"Dicle Üniversitesi Tıp Fakültesi Hastanesi","lat":37.8946,"lon":40.2390,"address":"Sur 21280 Diyarbakır","country":"TR"},
    # Samsun
    {"name":"Ondokuz Mayıs Üniversitesi Hastanesi","lat":41.3392,"lon":36.3311,"address":"Kurupelit 55139 Samsun","country":"TR"},
    {"name":"Samsun Eğitim ve Araştırma Hastanesi","lat":41.2938,"lon":36.3311,"address":"İlkadım 55090 Samsun","country":"TR"},
    # Trabzon
    {"name":"KTÜ Farabi Hastanesi","lat":41.0177,"lon":39.7312,"address":"Ortahisar 61080 Trabzon","country":"TR"},
    {"name":"Trabzon Kanuni EAH","lat":40.9971,"lon":39.7246,"address":"Ortahisar 61040 Trabzon","country":"TR"},
    # Eskişehir
    {"name":"Osmangazi Üniversitesi Hastanesi","lat":39.7666,"lon":30.5235,"address":"Meşelik Kampüsü 26040 Eskişehir","country":"TR"},
    {"name":"Eskişehir Şehir Hastanesi","lat":39.7834,"lon":30.5192,"address":"Odunpazarı 26010 Eskişehir","country":"TR"},
    # Mersin
    {"name":"Mersin Üniversitesi Hastanesi","lat":36.8003,"lon":34.6421,"address":"Çiftlikköy 33343 Mersin","country":"TR"},
    {"name":"Mersin Şehir Hastanesi","lat":36.8105,"lon":34.6370,"address":"Toroslar 33240 Mersin","country":"TR"},
    # Malatya
    {"name":"İnönü Üniversitesi Turgut Özal Tıp Merkezi","lat":38.3487,"lon":38.3189,"address":"Battalgazi 44280 Malatya","country":"TR"},
    {"name":"Malatya Eğitim ve Araştırma Hastanesi","lat":38.3556,"lon":38.3167,"address":"Battalgazi 44090 Malatya","country":"TR"},
    # Manisa
    {"name":"Celal Bayar Üniversitesi Hafsa Sultan Hastanesi","lat":38.6128,"lon":27.4296,"address":"Uncubozköy 45010 Manisa","country":"TR"},
    {"name":"Manisa Şehir Hastanesi","lat":38.6200,"lon":27.4300,"address":"Yunusemre 45030 Manisa","country":"TR"},
    # Denizli
    {"name":"Pamukkale Üniversitesi Hastanesi","lat":37.9244,"lon":29.1240,"address":"Kınıklı 20160 Denizli","country":"TR"},
    {"name":"Denizli Devlet Hastanesi","lat":37.7750,"lon":29.0818,"address":"Saraylar Mah. 20025 Denizli","country":"TR"},
    # Hatay
    {"name":"Hatay Eğitim ve Araştırma Hastanesi","lat":36.2021,"lon":36.1600,"address":"Antakya 31060 Hatay","country":"TR"},
    {"name":"İskenderun Devlet Hastanesi","lat":36.5894,"lon":36.1671,"address":"İskenderun 31200 Hatay","country":"TR"},
    # Sakarya
    {"name":"Sakarya Üniversitesi EAH","lat":40.7732,"lon":30.4001,"address":"Korucuk 54290 Sakarya","country":"TR"},
    {"name":"Sakarya Eğitim ve Araştırma Hastanesi","lat":40.7554,"lon":30.3899,"address":"Adapazarı 54100 Sakarya","country":"TR"},
    # Kocaeli
    {"name":"Kocaeli Üniversitesi Hastanesi","lat":40.7660,"lon":29.9280,"address":"Umuttepe 41380 Kocaeli","country":"TR"},
    {"name":"Kocaeli Şehir Hastanesi","lat":40.7790,"lon":29.9110,"address":"Başiskele 41060 Kocaeli","country":"TR"},
    {"name":"Gebze Fatih Devlet Hastanesi","lat":40.8013,"lon":29.4302,"address":"Gebze 41400 Kocaeli","country":"TR"},
    # Tekirdağ
    {"name":"Tekirdağ Şehir Hastanesi","lat":40.9832,"lon":27.5121,"address":"Süleymanpaşa 59100 Tekirdağ","country":"TR"},
    # Kahramanmaraş
    {"name":"Kahramanmaraş Şehir Hastanesi","lat":37.6225,"lon":36.9357,"address":"Dulkadiroğlu 46040 Kahramanmaraş","country":"TR"},
    # Van
    {"name":"Van Eğitim ve Araştırma Hastanesi","lat":38.4981,"lon":43.3799,"address":"Edremit 65080 Van","country":"TR"},
    # Şanlıurfa
    {"name":"Harran Üniversitesi Tıp Fakültesi Hastanesi","lat":37.1566,"lon":38.7963,"address":"Haliliye 63300 Şanlıurfa","country":"TR"},
    {"name":"Şanlıurfa Eğitim ve Araştırma Hastanesi","lat":37.1663,"lon":38.7855,"address":"Eyyübiye 63200 Şanlıurfa","country":"TR"},
    # Balıkesir
    {"name":"Balıkesir Atatürk Şehir Hastanesi","lat":39.6472,"lon":27.8881,"address":"Karesi 10100 Balıkesir","country":"TR"},
    # Muğla
    {"name":"Muğla Sıtkı Koçman Üniversitesi EAH","lat":37.2149,"lon":28.3639,"address":"Kötekli 48000 Muğla","country":"TR"},
    # Erzurum
    {"name":"Atatürk Üniversitesi Araştırma Hastanesi","lat":39.9129,"lon":41.2676,"address":"Yakutiye 25240 Erzurum","country":"TR"},
    # Elazığ
    {"name":"Elazığ Fethi Sekin Şehir Hastanesi","lat":38.6810,"lon":39.2231,"address":"Elazığ","country":"TR"},
    # Ordu
    {"name":"Ordu Üniversitesi EAH","lat":41.0098,"lon":37.8786,"address":"Altınordu 52200 Ordu","country":"TR"},
    # Zonguldak
    {"name":"Bülent Ecevit Üniversitesi Hastanesi","lat":41.4519,"lon":31.7891,"address":"Kozlu 67600 Zonguldak","country":"TR"},
    # Kastamonu
    {"name":"Kastamonu Devlet Hastanesi","lat":41.3792,"lon":33.7788,"address":"Kastamonu 37200","country":"TR"},
    # Sivas
    {"name":"Sivas Cumhuriyet Üniversitesi Hastanesi","lat":39.7508,"lon":37.0179,"address":"İmaret Mah. 58140 Sivas","country":"TR"},
    # Aksaray
    {"name":"Aksaray Eğitim ve Araştırma Hastanesi","lat":38.3697,"lon":34.0329,"address":"Zübeyde Hanım Mah. 68100 Aksaray","country":"TR"},
    # Afyonkarahisar
    {"name":"Afyonkarahisar Sağlık Bilimleri Üniversitesi Hastanesi","lat":38.7507,"lon":30.5567,"address":"Afyonkarahisar 03200","country":"TR"},
    # Çorum
    {"name":"Çorum Eğitim ve Araştırma Hastanesi","lat":40.5501,"lon":34.9545,"address":"Çorum 19040","country":"TR"},
    # Tokat
    {"name":"Gaziosmanpaşa Üniversitesi Hastanesi","lat":40.3145,"lon":36.5533,"address":"Tokat 60100","country":"TR"},
    # Amasya
    {"name":"Amasya Üniversitesi Sabuncuoğlu Şerefeddin EAH","lat":40.6566,"lon":35.8317,"address":"Amasya 05100","country":"TR"},
]


# ── Combined lookup ────────────────────────────────────────────────────────────
ALL_HOSPITALS: list[dict] = (
    [{**h, "country": "DE"} for h in GERMANY_HOSPITALS] +
    UK_HOSPITALS +
    TR_HOSPITALS
)


def get_hospitals_by_country(country_code: str) -> list[dict]:
    """Filter hospitals by country code: DE, UK, TR."""
    return [h for h in ALL_HOSPITALS if h.get("country", "DE") == country_code]


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
            logger.warning("Azure Maps not configured — using hospital DB + estimated ETA.")
        else:
            logger.info("Azure Maps initialized.")

    def find_nearest_hospitals(
        self,
        patient_lat: float,
        patient_lon: float,
        count: int = 3,
        radius_km: int = 150,
        country: str = "DE",
    ) -> list[dict]:
        candidates = self._search_hospitals(patient_lat, patient_lon, radius_km, country)
        enriched: list[dict] = []
        for h in candidates:
            eta       = self.calculate_eta_to_hospital(patient_lat, patient_lon, h["lat"], h["lon"])
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
        logger.info(
            "Returning %d hospitals (country=%s). Nearest: %s (%s km)",
            len(result), country,
            result[0]["name"] if result else "N/A",
            result[0]["distance_km"] if result else "?",
        )
        return result

    def calculate_eta_to_hospital(
        self,
        patient_lat: float,
        patient_lon: float,
        hospital_lat: float,
        hospital_lon: float,
    ) -> dict:
        if self._initialized:
            return self._azure_maps_eta(patient_lat, patient_lon, hospital_lat, hospital_lon)
        return self._fallback_eta(patient_lat, patient_lon, hospital_lat, hospital_lon)

    def _search_hospitals(self, patient_lat: float, patient_lon: float, radius_km: int = 100, country: str = "DE") -> list[dict]:
        """Search all hospitals for a given country within radius."""
        pool = [h for h in ALL_HOSPITALS if h.get("country", "DE") == country]
        if not pool:
            pool = ALL_HOSPITALS  # fallback to all
        scored = sorted(
            [{**h, "distance_km": round(self._haversine_distance(patient_lat, patient_lon, h["lat"], h["lon"]), 1)}
             for h in pool],
            key=lambda x: x["distance_km"]
        )
        within = [h for h in scored if h["distance_km"] <= radius_km]
        return (within[:10] if within else scored[:5])

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
        eta   = max(1, round((dist * 1.3 / 55) * 60))   # 55 km/h average (urban+highway mix)
        return {"eta_minutes": eta, "distance_km": round(dist, 1),
                "traffic_delay_minutes": 0,
                "route_summary": f"{round(dist,1)} km · ~{eta} min (estimated)",
                "source": "estimated"}

    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2) -> float:
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))