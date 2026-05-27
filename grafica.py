import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider, Button
import numpy as np
from controlador import SimuladorPasteurizador
from parametros import METODOS, temp_amb, calculoPID

METODO = "LTLT"
intervalo_tiemp = 100
dt = 1.02

sim = SimuladorPasteurizador()
sim.iniciar(METODO)
T_SETPOINT_BASE = METODOS[METODO]["temp_constante"]
T_SETPOINT = T_SETPOINT_BASE

kp_base, ki_base, kd_base = calculoPID(METODO)
sim.kp = kp_base
sim.ki = ki_base
sim.kd = kd_base

tiempos = []
temperaturas = []
potencias = []
bacterias = []
p_hist = []
i_hist = []
d_hist = []

fig = plt.figure(figsize=(14, 10))
fig.suptitle(f"Simulador Pasteurizacion - Metodo {METODO}", fontsize=15, fontweight='bold')

gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
ax1 = fig.add_subplot(gs[0, 0])
ax2 = fig.add_subplot(gs[0, 1])
ax3 = fig.add_subplot(gs[1, 0])
ax4 = fig.add_subplot(gs[1, 1])

ax1.set_ylabel("Temperatura °C")
ax1.set_title("Temperatura de la leche")
ax1.set_ylim(temp_amb - 5, T_SETPOINT_BASE + 15)
ax1.axhline(y=T_SETPOINT, color='green', linestyle='--', linewidth=1.5, label=f"Setpoint {T_SETPOINT}°C")
linea_temp, = ax1.plot([], [], color='blue', linewidth=2, label="Temperatura actual")
ax1.legend(loc="lower right")
ax1.grid(True, alpha=0.3)
texto_temp = ax1.text(0.02, 0.85, '', transform=ax1.transAxes, fontsize=10, color='purple')

ax2.set_ylabel("Potencia (%) / Componentes PID")
ax2.set_title("Control del PID y componentes")
ax2.set_ylim(-110, 110)
ax2.axhline(y=100, color='red', linestyle=':', linewidth=1, alpha=0.5, label="Max 100%")
ax2.axhline(y=0, color='gray', linestyle=':', linewidth=1, alpha=0.5)
ax2.axhline(y=-100, color='red', linestyle=':', linewidth=1, alpha=0.5)
linea_pot, = ax2.plot([], [], color='orange', linewidth=2, label="Potencia PID")
linea_p, = ax2.plot([], [], color='red', linewidth=1, alpha=0.7, label="P")
linea_i, = ax2.plot([], [], color='blue', linewidth=1, alpha=0.7, label="I")
linea_d, = ax2.plot([], [], color='green', linewidth=1, alpha=0.7, label="D")
ax2.legend(loc="upper right", fontsize=8)
ax2.grid(True, alpha=0.3)
texto_pot = ax2.text(0.02, 0.02, '', transform=ax2.transAxes, fontsize=9, color='black', verticalalignment='bottom')

ax3.set_ylabel("Bacterias Destruidas %")
ax3.set_title("Reduccion de bacterias por Bigelow")
ax3.set_ylim(-2, 102)
ax3.axhline(y=99.999, color='red', linestyle='--', linewidth=1.5, label="Objetivo 99.999%")
linea_bact, = ax3.plot([], [], color='#9C27B0', linewidth=2, label="Bacterias destruidas")
ax3.legend(loc="lower right")
ax3.grid(True, alpha=0.3)
texto_bac = ax3.text(0.02, 0.15, '', transform=ax3.transAxes, fontsize=10, color='#9C27B0')

ax4.set_xlim(0, 1)
ax4.set_ylim(0, 1)
ax4.axis('off')
texto_info = ax4.text(0.05, 0.75, '', transform=ax4.transAxes, fontsize=11,
                      verticalalignment='top', fontfamily='monospace')
texto_fallo = ax4.text(0.05, 0.10, '', transform=ax4.transAxes, fontsize=13,
                       fontweight='bold', color='red', verticalalignment='bottom')

sl_ax_kp = fig.add_axes([0.08, 0.05, 0.16, 0.025])
sl_ax_ki = fig.add_axes([0.28, 0.05, 0.16, 0.025])
sl_ax_kd = fig.add_axes([0.48, 0.05, 0.16, 0.025])
sl_ax_sp = fig.add_axes([0.08, 0.10, 0.16, 0.025])
sl_ax_ruido = fig.add_axes([0.28, 0.10, 0.16, 0.025])
btn_ax = fig.add_axes([0.50, 0.10, 0.14, 0.035])

s_kp = Slider(sl_ax_kp, 'Kp (x ZN)', 0.1, 5.0, valinit=1.0, valfmt='%.2f')
s_ki = Slider(sl_ax_ki, 'Ki (x ZN)', 0.1, 5.0, valinit=1.0, valfmt='%.2f')
s_kd = Slider(sl_ax_kd, 'Kd (x ZN)', 0.1, 5.0, valinit=1.0, valfmt='%.2f')
s_sp = Slider(sl_ax_sp, 'Setpoint', T_SETPOINT_BASE - 15, T_SETPOINT_BASE + 15,
              valinit=T_SETPOINT_BASE, valfmt='%.1f °C')
s_ruido = Slider(sl_ax_ruido, 'Ruido σ', 0.0, 2.0, valinit=0.5, valfmt='%.1f °C')

def update_kp(val):
    sim.kp = kp_base * val
def update_ki(val):
    sim.ki = ki_base * val
def update_kd(val):
    sim.kd = kd_base * val
def update_sp(val):
    sim.temp_override = val
def update_ruido(val):
    sim.ruido_nivel = val

s_kp.on_changed(update_kp)
s_ki.on_changed(update_ki)
s_kd.on_changed(update_kd)
s_sp.on_changed(update_sp)
s_ruido.on_changed(update_ruido)

btn = Button(btn_ax, 'Inyectar -10°C', color='salmon', hovercolor='red')

def inyectar(event):
    sim.perturbar(-10.0)

btn.on_clicked(inyectar)

def actualizar_grafica(frame):
    if not sim.corriendo and not sim.fallo_total:
        return (linea_temp, linea_pot, linea_p, linea_i, linea_d, linea_bact)

    sim.avanzar(dt=dt)

    if sim.n < sim.n_base:
        pct_bac = (1.0 - sim.n / sim.n_base) * 100.0
    else:
        pct_bac = 0.0

    tiempos.append(sim.tiempo / 60)
    temperaturas.append(sim.temp)
    potencias.append(sim.potencia)
    bacterias.append(pct_bac)
    p_hist.append(sim.p_term)
    i_hist.append(sim.i_term)
    d_hist.append(sim.d_term)

    linea_temp.set_data(tiempos, temperaturas)
    linea_pot.set_data(tiempos, potencias)
    linea_p.set_data(tiempos, p_hist)
    linea_i.set_data(tiempos, i_hist)
    linea_d.set_data(tiempos, d_hist)
    linea_bact.set_data(tiempos, bacterias)

    t_actual = tiempos[-1] if tiempos else 0
    t_min = max(0, t_actual - 35)
    t_max = t_actual + 2

    for ax in (ax1, ax2, ax3):
        ax.set_xlim(t_min, t_max)

    texto_temp.set_text(f"Temperatura actual: {sim.temp:.1f} °C")
    texto_pot.set_text(
        f"P={sim.p_term:.1f}  I={sim.i_term:.1f}  D={sim.d_term:.1f}  |  "
        f"KP={sim.kp:.2f}  KI={sim.ki:.4f}  KD={sim.kd:.2f}"
    )
    texto_bac.set_text(f"Bacterias destruidas: {pct_bac:.4f}%")

    if sim.rechazado:
        ax1.set_facecolor('lightsalmon')
        sim.rechazado = False
    else:
        ax1.set_facecolor('white')

    t_sp = sim.temp_override if sim.temp_override is not None else T_SETPOINT_BASE
    error = sim.temp - t_sp if sim.corriendo else 0.0
    info_lines = [
        f"Error actual: {error:+.2f} °C",
        f"T setpoint: {t_sp:.1f} °C",
        f"Fase: {sim.fase.upper()}",
        f"Ciclo: {sim.ciclo_actual}/{sim.ciclos_maximos}",
        f"Reduccion max: {sim.reduccion_maxima:.2f} log10",
        f"Ruido σ: {sim.ruido_nivel:.1f} °C",
        f"Tiempo: {sim.tiempo:.0f} s",
    ]
    texto_info.set_text('\n'.join(info_lines))

    if sim.fallo_total:
        texto_fallo.set_text(sim.motivo_fallo)
    else:
        texto_fallo.set_text('')

    return linea_temp, linea_pot, linea_p, linea_i, linea_d, linea_bact

ani = animation.FuncAnimation(
    fig, actualizar_grafica,
    interval=intervalo_tiemp, blit=False, cache_frame_data=False
)

print(f"Iniciando simulacion {METODO}")
print(f"Setpoint base: {T_SETPOINT_BASE} °C")
print(f"Ganancias ZN: KP={kp_base:.4f}  KI={ki_base:.6f}  KD={kd_base:.2f}")
plt.show()
