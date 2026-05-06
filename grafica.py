import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
from controlador import SimuladorPasteurizador
from parametros import METODOS, temp_amb

# 🔥 FIREBASE
from firebase_pasteurizador import publicar_cambio_fase, _ref
import time

METODO = "LTLT"
intervalo_tiemp = 100
dt = 1.0

sim = SimuladorPasteurizador()
sim.iniciar(METODO)
T_SETPOINT = METODOS[METODO]["temp_constante"]

# listas datos
tiempos      = []
temperaturas = []
potencias    = []
bacterias    = []

# 🔥 control de fase y tiempo real
_fase_anterior      = "calentando"
_ultimo_envio_rt    = 0.0        # timestamp del ultimo envio en tiempo real
INTERVALO_RT        = 2.0        # segundos entre envios en tiempo real a Firebase

# figura
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8))
fig.suptitle(f"Simulador Pasteurizacion - Metodo {METODO}", fontsize=15, fontweight='bold')

# temperatura
ax1.set_ylabel("Temperatura oC")
ax1.set_title("Temperatura de la leche")
ax1.set_ylim(temp_amb - 5, T_SETPOINT + 15)
ax1.axhline(y=T_SETPOINT, color='green', linestyle='--', linewidth=1.5, label=f"Setpoint {T_SETPOINT}°C")
linea_temp, = ax1.plot([], [], color='blue', linewidth=2, label="Temperatura actual")
ax1.legend(loc="lower right")
ax1.grid(True, alpha=0.3)
texto_temp = ax1.text(0.02, 0.85, '', transform=ax1.transAxes, fontsize=10, color='purple')

# potencia
ax2.set_ylabel("Potencia %")
ax2.set_title("Control del PID")
ax2.set_ylim(-5, 110)
ax2.axhline(y=100, color='red', linestyle=':', linewidth=1, alpha=0.5, label="Maximo 100%")
ax2.axhline(y=0, color="gray", linestyle=':', linewidth=1, alpha=0.5)
linea_pot, = ax2.plot([], [], color='orange', linewidth=2, label="Potencia PID")
ax2.legend(loc="upper right")
ax2.grid(True, alpha=0.3)
texto_pot = ax2.text(0.02, 0.85, '', transform=ax2.transAxes, fontsize=10, color='darkorange')

# bacterias
ax3.set_ylabel("Bacterias Destruidas %")
ax3.set_title("Reduccion de bacterias por Bigelow")
ax3.set_ylim(-2, 102)
ax3.axhline(y=99.99, color='red', linestyle='--', linewidth=1.5, label="Objetivo: 99.999%")
linea_bact, = ax3.plot([], [], color='#9C27B0', linewidth=2, label="Bacterias destruidas")
ax3.legend(loc="lower right")
ax3.grid(True, alpha=0.3)
ax3.set_xlabel("Tiempo (minutos)")
texto_bac  = ax3.text(0.02, 0.15, '', transform=ax3.transAxes, fontsize=10, color='#9C27B0')
texto_fase = ax3.text(0.98, 0.85, '', transform=ax3.transAxes, fontsize=11,
                      fontweight='bold', color='darkgreen', ha='right')

# texto resultado final
texto_resultado = ax1.text(0.5, 0.5, '', transform=ax1.transAxes, fontsize=14,
                           fontweight='bold', ha='center', va='center',
                           bbox=dict(boxstyle='round', facecolor='white', alpha=0.85))


def publicar_tiempo_real(pct_bac):
    """
    🔥 Publica temperatura, potencia y bacterias en tiempo real a Firebase.
    Se llama cada INTERVALO_RT segundos para no saturar la conexion.
    """
    alarmas_raw = sim.alarmas
    alarmas_str = ",".join(str(x) for x in alarmas_raw) if alarmas_raw else ""

    datos = {
        "temperatura":          round(float(sim.temp), 2),
        "potencia":             round(float(sim.potencia), 1),
        "bacterias_destruidas": round(float(pct_bac), 4),
        "reduccion_log10":      round(float(
            np.log10(max(sim.n_base / sim.n, 1.0))
        ), 3),
        "valor_F":              round(float(sim.valor_F), 3),
        "energia_consumida_wh": round(float(sim.energia_consumida), 2),
        "tiempo_segundos":      round(float(sim.tiempo), 1),
        "alarmas":              alarmas_str,
        "timestamp":            int(time.time()),
    }
    try:
        _ref().update(datos)
    except Exception as e:
        print(f"[Firebase] Error tiempo real: {e}")


def actualizar_grafica(frame):
    global _fase_anterior, _ultimo_envio_rt

    # ── Proceso terminado ──────────────────────────────────────
    if not sim.corriendo:
        estado   = sim.get_Estado()
        aprobado = bool(estado.get("proceso_aprobado", False))

        if aprobado:
            texto_resultado.set_text("APROBADO ✓\nLeche al almacenamiento")
            texto_resultado.set_color("darkgreen")
        else:
            texto_resultado.set_text("RECHAZADO ✗\nRetorno al tanque 1")
            texto_resultado.set_color("darkred")

        texto_fase.set_text("COMPLETADO")
        texto_fase.set_color("purple")
        return linea_temp, linea_pot, linea_bact

    # ── Avanzar simulacion ─────────────────────────────────────
    sim.avanzar(dt=dt)

    # bacterias destruidas
    if sim.n < sim.n_base:
        pct_bac = (1.0 - sim.n / sim.n_base) * 100.0
    else:
        pct_bac = 0.0

    # nuevos valores a las listas
    tiempos.append(sim.tiempo / 60)
    temperaturas.append(sim.temp)
    potencias.append(sim.potencia)
    bacterias.append(pct_bac)

    # actualizacion de las lineas
    linea_temp.set_data(tiempos, temperaturas)
    linea_pot.set_data(tiempos, potencias)
    linea_bact.set_data(tiempos, bacterias)

    t_actual        = tiempos[-1]
    t_minimavisible = max(0, t_actual - 35)
    t_maxvisible    = t_actual + 2

    for ax in (ax1, ax2, ax3):
        ax.set_xlim(t_minimavisible, t_maxvisible)

    # textos actualizacion
    texto_temp.set_text(f"Temperatura actual: {sim.temp:.1f} oC")
    texto_pot.set_text(f"Potencia: {sim.potencia:.1f}%")
    texto_bac.set_text(f"Bacterias destruidas: {pct_bac:.2f}%")
    texto_fase.set_text(f"Fase: {sim.fase.upper()}")

    colores_fase = {
        "calentando":    "darkred",
        "mantenimiento": "darkorange",
        "enfriando":     "steelblue",
        "completado":    "purple",
        "esperando":     "gray"
    }
    texto_fase.set_color(colores_fase.get(sim.fase, "black"))

    # 🔥 FIREBASE — envio en tiempo real cada INTERVALO_RT segundos
    ahora = time.time()
    if ahora - _ultimo_envio_rt >= INTERVALO_RT:
        publicar_tiempo_real(pct_bac)
        _ultimo_envio_rt = ahora

    # 🔥 FIREBASE — detectar cambio de fase y publicar
    if sim.fase != _fase_anterior:
        publicar_cambio_fase(sim.fase, sim.get_Estado())
        _fase_anterior = sim.fase

    return linea_temp, linea_pot, linea_bact


# inicio simulacion
ani = animation.FuncAnimation(
    fig,
    actualizar_grafica,
    interval=intervalo_tiemp, blit=False, cache_frame_data=False
)

print(f"Iniciando simulacion {METODO}")
print(f"Setpoint: {T_SETPOINT} oC")
plt.tight_layout()
plt.show()