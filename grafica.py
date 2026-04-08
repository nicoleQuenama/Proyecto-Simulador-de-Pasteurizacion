
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from controlador import construir_animacion, SimuladorPasteurizador
from parametros import METODOS

# ── CONFIGURACIÓN DEL PROCESO ──────────────────────────────────────────────────

# Aquí elegimos qué receta usar. Opciones: "LTLT", "HTST", "UHT"
METODO = "LTLT"       

# Milisegundos entre cada actualización de la gráfica.
# Menor número = animación más fluida, pero consume más procesador (CPU).
INTERVALO_MS = 100    

# dt: Paso de integración en segundos (nuestro salto en el tiempo).
# Tip de auxiliatura: Si es muy pequeño es más preciso, pero la simulación irá lenta.
# Para procesos ultra rápidos como UHT, usen un DT de 0.1 para no perder detalles.
DT = 1.0

# Ventana visible en el eje X según el método (en minutos).
# Como HTST y UHT son muy rápidos, no tiene sentido ver una gráfica de 35 minutos vacía.
VENTANA_METODO = {
    "LTLT": 35.0,
    "HTST": 3.0,
    "UHT":  1.0,
}

# ── RESUMEN FINAL (CONTROL DE CALIDAD) ─────────────────────────────────────────

def _mostrar_resumen(sim, ax3):
    """
    Función para mostrar los resultados finales cuando el lote termina.
    Imprime en la consola y dibuja un cuadro de texto directamente en la gráfica.
    """
    # Sacamos toda la info del simulador usando el empaquetado que definimos.
    estado = sim.get_Estado()
    log10  = estado["reduccion_log10"]
    n_ini  = estado["bacterias_iniciales"]
    seguro = estado["seguro_fda"]
    
    # Veredicto basado en la norma: Si bajamos 5 órdenes de magnitud (log5), la leche es segura.
    veredicto = "APROBADO (≥5-log FDA)" if seguro else "RECHAZADO (<5-log FDA)"

    # ── Reporte en Consola ──
    print("\n" + "=" * 50)
    print("  RESUMEN FINAL DEL LOTE")
    print("=" * 50)
    print(f"  Método:                {METODO}")
    print(f"  Bacterias iniciales:  {n_ini:.2e}")
    print(f"  Reducción log10:      {log10:.3f}")
    print(f"  Veredicto FDA:        {veredicto}")
    print("=" * 50)

    # ── Reporte en Gráfica (Cuadro de texto) ──
    # Si está aprobado usamos verde, si no, un rojo de advertencia.
    color_box   = "#2e7d32" if seguro else "#c62828"
    color_texto = "white"

    resumen = (
        f"Lote finalizado\n"
        f"N inicial: {n_ini:.2e}\n"
        f"Reducción: {log10:.2f} log₁₀\n"
        f"{veredicto}"
    )

    # Dibujamos el cuadro informativo sobre la tercera subgráfica (ax3).
    ax3.text(
        0.98, 0.5, resumen,
        transform=ax3.transAxes,
        fontsize=9,
        verticalalignment="center",
        horizontalalignment="right",
        bbox=dict(
            boxstyle="round,pad=0.5",
            facecolor=color_box,
            alpha=0.88,
            edgecolor="none",
        ),
        color=color_texto,
        fontweight="bold",
        zorder=10,
    )
    plt.draw()


# ── LANZADOR PRINCIPAL ────────────────────────────────────────────────────────

def lanzar(metodo=METODO, intervalo_ms=INTERVALO_MS, dt=DT):
    """
    Esta función arma la figura y arranca la animación.
    Es como el "encendido" de nuestra máquina virtual.
    """
    # Buscamos cuánto tiempo debe mostrar la gráfica según el método elegido.
    ventana = VENTANA_METODO.get(metodo, 35.0)

    print("=" * 50)
    print(f"  Simulador Pasteurizador — {metodo}")
    print(f"  Setpoint: {METODOS[metodo]['temp_constante']} °C")
    print(f"  Tiempo de mantenimiento: {METODOS[metodo]['tiempo']} s")
    print("=" * 50)

    # Llamamos a la función del controlador que ya tiene configurados los ejes y el PID.
    fig, ani, sim = construir_animacion(
        metodo=metodo,
        intervalo_ms=intervalo_ms,
        dt=dt,
    )

    # Recuperamos los ejes (ax1: Temp, ax2: Potencia, ax3: Bacterias).
    ax1, ax2, ax3 = fig.get_axes()

    # Ajustamos la escala inicial del eje X para que se vea ordenado desde el segundo 0.
    for ax in (ax1, ax2, ax3):
        ax.set_xlim(0, ventana)

    # Variable tipo bandera para no imprimir el resumen muchas veces al final.
    resumen_mostrado = {"hecho": False}

    # --- GUARDIA DE SEGURIDAD ---
    # Interceptamos la función de animación original para saber cuándo termina el proceso.
    func_original = ani._func

    def frame_con_guardia(frame):
        resultado = func_original(frame)

        # Si el simulador dejó de correr y aún no mostramos el resumen, es hora de hacerlo.
        if not sim.corriendo and not resumen_mostrado["hecho"]:
            resumen_mostrado["hecho"] = True
            _mostrar_resumen(sim, ax3)

        return resultado

    # Reemplazamos la función de la animación por nuestra versión con "guardia".
    ani._func = frame_con_guardia

    print(f"\nBacterias iniciales detectadas: {sim.n_inicial:.2e}")
    print("Iniciando simulación en tiempo real...\n")

    plt.tight_layout()
    plt.show()


# ── PUNTO DE ENTRADA ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Si ejecutas este archivo directamente, se lanza la animación con los parámetros de arriba.
    lanzar(metodo=METODO, intervalo_ms=INTERVALO_MS, dt=DT)