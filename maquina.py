import numpy as np
import control as ctrl
import matplotlib.pyplot as plt
from parametros import K, tau, tiempo_muerto, temp_amb, METODOS, potencia_max

#simulacion 
def planta_pasteurizacion():
    K_pct = K * potencia_max / 100.0
    num_planta = [K_pct]
    den_planta = [tau, 1.0]
    G_planta   = ctrl.TransferFunction(num_planta, den_planta)
    num_pade = [-tiempo_muerto / 2.0, 1.0]   # -theta/2·s + 1
    den_pade = [ tiempo_muerto / 2.0, 1.0]   #  theta/2·s + 1
    G_retardo = ctrl.TransferFunction(num_pade, den_pade)

    G = ctrl.series(G_retardo, G_planta)
    return G

def lazo_abierto(G, potencia_pct=50.0, duracion=7200):
    t= np.linspace(0, duracion, 2000)
    t_out, y = ctrl.step_response(G, t)
    T = temp_amb + y * potencia_pct
    return t_out, T

#empaquetamiento para unity(quitar lo que va mandar)
def empaquetamiento(temp, tem_constante, fase, bacterias,tiempo, potencia):

    if temp < tem_constante * 0.98:
        estado = "calentando"
    elif temp > tem_constante * 1.02:
        estado = "enfriando"
    else:
        estado = "constante"
    T_min = temp_amb
    T_max = 135.0   # temperatura maxima del sistema por UHT
    calor = (temp - T_min) / (T_max - T_min)
    calor = max(0.0, min(1.0, calor))
    error = tem_constante - temp
    aprobado = bacterias >= 99.999

    datos = {
        "temperatura_actual"   : round(temp, 2),
        "temp_objetivo"        : round(tem_constante, 2),
        "error_temp"           : round(error, 2),
        "potencia"             : round(potencia, 1),
        "fase"                 : fase,
        "estado_animacion"     : estado,
        "calor_normalizado"    : round(calor, 3),
        "bacterias_destruidas" : round(bacterias, 4),
        "proceso_aprobado"     : aprobado,
        "tiempo"               : round(tiempo, 1),
    }
    return datos

if __name__ == "__main__":

    print("Construyendo planta...")
    G = planta_pasteurizacion()
    print(G)

    print("\nSimulando lazo abierto al 50%...")
    t, T = lazo_abierto(G, potencia_pct=50.0, duracion=7200)

    plt.figure(figsize=(10, 4))
    plt.plot(t / 60, T, color="#FF5722", linewidth=2)
    plt.axhline(y=63.0, color="green", linestyle="--", label="Setpoint LTLT 63°C")
    plt.xlabel("Tiempo (minutos)")
    plt.ylabel("Temperatura (°C)")
    plt.title("Lazo abierto — 50% potencia constante, sin controlador")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("verificacion_planta.png", dpi=150)
    plt.close()
    print("Grafica guardada: verificacion_planta.png")
