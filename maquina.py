import numpy as np
import control as ctrl
import matplotlib.pyplot as plt
from parametros import K, tau, tiem_muerto,temp_amb, METODOS, potencia_max

#simulacion de la planta de pasteurizacion
def planta_pasteurizacion() -> ctrl.TransferFunction:
    k_pct= K*potencia_max/100.0 #ganancia en celsius
    g_planta= ctrl.TransferFunction([k_pct], [tau,1.0])

    num_pade=[-tiem_muerto/2.0,1.0]
    den_pade=[-tiem_muerto/2.0,1.0]
    g_retardo= ctrl.TransferFunction(num_pade, den_pade)

    return ctrl.series(g_retardo, g_planta)

#lazo abierto
def lazo_abierto(g:ctrl.TransferFunction, pot=50.0, duracion=7200):
    #calculo de incremento por %
    t= np.linspace(0, duracion, 2000)
    t_out, y = ctrl.step_response(g,t)
    T= temp_amb + y * pot
    return t_out, T

if __name__ == "__main__":

    print("Construyendo modelo de la planta...")
    G = planta_pasteurizacion()
    print("Función de transferencia:")
    print(G)

    print("\nSimulando lazo abierto al 50% de potencia...")
    t, T = lazo_abierto(G, pot=50.0, duracion=7200)

    # Graficar
    plt.figure(figsize=(10, 5))
    plt.plot(t / 60, T, color='#FF5722', linewidth=2)
    plt.axhline(y=63.0, color='green', linestyle='--',
                label='Setpoint LTLT: 63°C')
    plt.xlabel("Tiempo (minutos)")
    plt.ylabel("Temperatura (°C)")
    plt.title("Lazo abierto — 50% potencia constante, sin controlador")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("verificacion_planta.png", dpi=150)
    plt.close()
    print("Gráfica guardada: verificacion_planta.png")