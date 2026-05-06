import json
import os

# Rutas absolutas a los JSON
_carpeta = os.path.dirname(os.path.abspath(__file__))
_ruta_tipo_leche = os.path.join(_carpeta, "tipoLeche.json")
_ruta_metodos = os.path.join(_carpeta, "pasteurizacion_metodos.json")

# Cargar tipoLeche.json
try:
    with open(_ruta_tipo_leche, "r", encoding="utf-8") as f:
        tipo_milk = json.load(f)
except FileNotFoundError:
    raise FileNotFoundError(f"No se encontró el archivo {_ruta_tipo_leche}")
except json.JSONDecodeError as error:
    raise ValueError(f"Error en la sintaxis de tipoLeche.json: {error}")

# Cargar pasteurizacion_metodos.json
try:
    with open(_ruta_metodos, "r", encoding="utf-8") as archivo:
        METODOS = json.load(archivo)
except FileNotFoundError:
    raise FileNotFoundError(f"No se encontró el archivo {_ruta_metodos}")
except json.JSONDecodeError as error:
    raise ValueError(f"Error en la sintaxis de pasteurizacion_metodos.json: {error}")

# Tipo de leche a usar
leche_utilizada = "leche_entera" # Se corrigió para que coincida con la clave del JSON
fluido = tipo_milk[leche_utilizada] # Corregido: Se accede con corchetes
densidad_leche = fluido["densidad"]
calor_especificoMilk = fluido["calor_especifico"]

# Parámetros tanque de la leche
litros = 20.0
potencia_max = 3000.0
masa_milk = litros * densidad_leche

# Parámetros térmicos
temp_amb = 25.0
delta = 75.0 # Diferencia que genera la resistencia
agua_fria_temp = 2.0
ua_enf = 150.0 # Coeficiente de enfriamiento

# Parámetros para transferencia
UA = potencia_max / delta # Coeficiente de transferencia de calor
K = 1.0 / UA # Ganancia de la planta
tau = (masa_milk * calor_especificoMilk) / UA # Constante de tiempo
tiem_muerto = 7.0 # Tiempo de retardo del sensor

# Bacterias iniciales
inicial_n = 1e6

def calculoPID(metodo="LTLT"):
    kp_base = 1.2 * tau / (K * tiem_muerto * potencia_max) # Ganancia
    ti = 2.0 * tiem_muerto # Tiempo integral
    td = 0.5 * tiem_muerto # Tiempo derivativo
    ki_base = kp_base / ti
    kd_base = kp_base * td

    # Ajustes según el método
    ajustes = {
        "LTLT": (1.0, 1.0, 1.0),
        "HTST": (1.5, 1.2, 1.0),
        "UHT":  (2.0, 1.5, 0.8)
    }

    fp, fi, fd = ajustes.get(metodo, (1.0, 1.0, 1.0))
    return kp_base * fp, ki_base * fi, kd_base * fd