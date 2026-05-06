# firebase_pasteurizador.py
import firebase_admin
from firebase_admin import credentials, db
import time

FIREBASE_CREDENTIALS = "serviceAccountKey.json"
DATABASE_URL         = "https://pasteurizador-89cad-default-rtdb.firebaseio.com"  # <- tu URL

_inicializado = False

def inicializar_firebase():
    global _inicializado
    if _inicializado:
        return
    try:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})
        _inicializado = True
        print("[Firebase] Conectado correctamente.")
    except Exception as e:
        print(f"[Firebase] ERROR al conectar: {e}")
        raise


def _ref():
    return db.reference("/pasteurizador")


def _limpiar(valor):
    """
    Convierte valores Python a tipos seguros para JSON de Firebase.
    bool  → int (0/1)
    list  → string separado por comas
    float → round 4 decimales
    """
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, list):
        return ",".join(str(x) for x in valor) if valor else ""
    if isinstance(valor, float):
        return round(valor, 4)
    return valor


def _preparar(datos: dict) -> dict:
    return {k: _limpiar(v) for k, v in datos.items()}


# ─────────────────────────────────────────────
# ESCRITURA — Python → Firebase
# ─────────────────────────────────────────────

def publicar_estado_inicial(metodo: str, temp_setpoint: float):
    datos = {
        "fase":                 "calentando",
        "metodo":               metodo,
        "temperatura":          25.0,
        "temp_setpoint":        temp_setpoint,
        "potencia":             0.0,
        "bacterias_destruidas": 0.0,
        "reduccion_log10":      0.0,
        "valor_F":              0.0,
        "energia_consumida_wh": 0.0,
        "proceso_aprobado":     0,
        "simulacion_corriendo": 1,
        "simulacion_pausada":   0,
        "motor1_activo":        0,
        "motor2_activo":        0,
        "motor3_activo":        0,
        "led_rojo_t1":          1,
        "led_azul_t2":          0,
        "led_verde_t3":         0,
        "led_rojo_t3":          0,
        "alarmas":              "",
        "timestamp":            int(time.time()),
    }
    _ref().set(datos)
    print(f"[Firebase] Estado inicial publicado — Método: {metodo}")


def publicar_cambio_fase(fase: str, estado: dict):

    motor1       = 0
    motor2       = 0
    motor3       = 0
    led_rojo_t1  = 0
    led_azul_t2  = 0
    led_verde_t3 = 0
    led_rojo_t3  = 0

    if fase == "calentando":
        led_rojo_t1 = 1

    elif fase == "mantenimiento":
        led_rojo_t1 = 1

    elif fase == "enfriando":
        motor1      = 1
        led_azul_t2 = 1

    elif fase == "completado":
        aprobado = int(bool(estado.get("proceso_aprobado", False)))
        if aprobado:
            motor2       = 1
            led_verde_t3 = 1
        else:
            motor3      = 1
            led_rojo_t3 = 1

    alarmas_raw = estado.get("alarmas", [])
    alarmas_str = ",".join(str(x) for x in alarmas_raw) if alarmas_raw else ""

    datos = {
        "fase":                 fase,
        "temperatura":          round(float(estado.get("temperatura_actual", 0)), 2),
        "temp_setpoint":        round(float(estado.get("temp_objetivo", 0)), 2),
        "potencia":             round(float(estado.get("potencia", 0)), 1),
        "bacterias_destruidas": round(float(estado.get("bacterias_destruidas", 0)), 4),
        "reduccion_log10":      round(float(estado.get("reduccion_log10", 0)), 3),
        "valor_F":              round(float(estado.get("valor_F", 0)), 3),
        "energia_consumida_wh": round(float(estado.get("energia_consumida_wh", 0)), 2),
        "proceso_aprobado":     int(bool(estado.get("proceso_aprobado", False))),
        "simulacion_corriendo": int(bool(estado.get("simulacion_corriendo", True))),
        "simulacion_pausada":   int(bool(estado.get("simulacion_pausada", False))),
        "motor1_activo":        motor1,
        "motor2_activo":        motor2,
        "motor3_activo":        motor3,
        "led_rojo_t1":          led_rojo_t1,
        "led_azul_t2":          led_azul_t2,
        "led_verde_t3":         led_verde_t3,
        "led_rojo_t3":          led_rojo_t3,
        "alarmas":              alarmas_str,
        "timestamp":            int(time.time()),
    }

    _ref().update(datos)
    print(f"[Firebase] Cambio de fase publicado: {fase.upper()}")


def publicar_resultado_final(estado: dict, aprobado: bool,
                             reduccion: float, energia: float):
    datos = {
        "fase":                 "completado",
        "proceso_aprobado":     int(aprobado),
        "reduccion_log10":      round(float(reduccion), 3),
        "energia_consumida_wh": round(float(energia), 2),
        "simulacion_corriendo": 0,
        "motor3_activo":        int(not aprobado),
        "led_verde_t3":         int(aprobado),
        "led_rojo_t3":          int(not aprobado),
        "timestamp":            int(time.time()),
    }
    _ref().update(datos)
    resultado = "APROBADO" if aprobado else "RECHAZADO — retorno al tanque 1"
    print(f"[Firebase] Resultado final: {resultado}")


def apagar_todo():
    datos = {
        "motor1_activo": 0,
        "motor2_activo": 0,
        "motor3_activo": 0,
        "led_rojo_t1":   0,
        "led_azul_t2":   0,
        "led_verde_t3":  0,
        "led_rojo_t3":   0,
        "simulacion_corriendo": 0,
        "timestamp":     int(time.time()),
    }
    _ref().update(datos)
    print("[Firebase] Todo apagado.")