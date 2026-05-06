import json
import os

#importacion de los parametros de la leche
_carpeta   = os.path.dirname(os.path.abspath(__file__))
_rutmet_json = os.path.join(_carpeta, "tipoLeche.json")
try:
    with open(_rutmet_json, "r", encoding="utf-8") as archivo:
        tipleche = json.load(archivo)
except FileNotFoundError:
    raise FileNotFoundError(f"No se encontro el archivo: {_rutmet_json}")
except json.JSONDecodeError as e:
    raise ValueError(f"Error en la sintaxis del JSON: {e}")

leche_utilizada = "leche_entera"
fluido  = tipleche[leche_utilizada]
volumen_litros = 20.0
potencia_max = 3000.0 #watts
temp_amb = 25.0   #enfriamiento leche
delta_t_max = 75.0
temp_enfriamiento = 4.0
UA_enfriamiento= 150.0
temp_aguafria = 2.0
inicial_n = 1e6
densidad= fluido["densidad"]
calor_esp   = fluido["calor_especifico"]
masa= volumen_litros * densidad
UA = potencia_max / delta_t_max
K = 1.0 / UA
tau = (masa * calor_esp) / UA
tiempo_muerto = 7.0  #cambio de una temperatura a otra


def calcular_PID(metodo="LTLT"):
    Kp_base = 1.2 * tau / (K * tiempo_muerto * potencia_max)
    Ti = 2.0 * tiempo_muerto
    Td = 0.5 * tiempo_muerto
    Ki_base = Kp_base / Ti
    Kd_base = Kp_base * Td

    ajustes = {
        "LTLT": (1.0, 1.0, 1.0),
        "HTST": (1.5, 1.2, 1.0),
        "UHT" : (2.0, 1.5, 0.8),
    }

    fp, fi, fd = ajustes.get(metodo, (1.0, 1.0, 1.0))
    Kp = Kp_base * fp
    Ki = Ki_base * fi
    Kd = Kd_base * fd

    return Kp, Ki, Kd

#apertura para los pasteurizadores
_carpeta   = os.path.dirname(os.path.abspath(__file__))
_ruta_json = os.path.join(_carpeta, "pasteurizacion_metodos.json")

try:
    with open(_ruta_json, "r", encoding="utf-8") as archivo:
        METODOS = json.load(archivo)
except FileNotFoundError:
    raise FileNotFoundError(f"No se encontro el archivo: {_ruta_json}")
except json.JSONDecodeError as e:
    raise ValueError(f"Error en la sintaxis del JSON: {e}")