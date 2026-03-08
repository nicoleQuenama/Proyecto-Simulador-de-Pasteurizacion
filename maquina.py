import numpy as np
import control as ctrl
import matplotlib.pyplot as plt
from parametros import K, tau, tem_muerto,temp_amb, calculoPID, pasteurizacion_metodos

def planta_pasteurizacion():
    num= [K]
    densidad=[tau, 1.0]
    g_planta=ctrl.TransferFunction(num, densidad)

    nupade=[-tem_muerto/2.0,1.0]
    denpade=[tem_muerto/2.0,1.0]
    g_retardo=ctrl.TransferFunction(nupade, denpade)
    g= ctrl.series(g_planta, g_retardo)
    return g

#lazo abierto
def lazo_abierto(g, pot=50.0, duracion=7200):
    t_in= np.linspace(0, duracion, 2000)
    t_out, y = ctrl.step_response(g,t_in)
    incremento= y * pot
    temp=temp_amb + incremento

    return t_out, temp

def empaquetamiento(temp, tem_constante, fase, bacterias, tiempo, potencia):
    if temp < tem_constante * 0.99:
        estado= "calentando la leche"
    elif temp> tem_constante *7.02:
        estado="iniciando enfriamiento"
    else:
        estado= "en equilibrio"

    #manejo para unity
    temp_min = temp_amb
    t_max= 135.0
    
    calor=(temp-temp_min)/(t_max-temp_min)
    calor = max(0.0,min(1.0,calor))

    #margen que falta para llegar a la temp
    temp_margen= tem_constante - temp
    bacterias_aceptadas= bacterias>=99.99

    datos={
        "temperatura_actual":round(temp,2),
        "temperatura_constante": round(tem_constante,2),
        "error_margen_temperatura":round(temp_margen, 2),
        "potencia": round(potencia,1),
        "fase": fase,
        "estado_temperatura_animacion": estado,
        "calor": round(calor,3),
        "bacterias_destruidas":round(bacterias, 4),
        "proceso_aceptado": bacterias_aceptadas,
        "tiempo": round(tiempo,1),
    }
    return datos


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

    # Verificar preparar_datos_unity con valores de ejemplo
    print("\nEjemplo de datos para Unity:")
    datos = empaquetamiento(
        temp     = 45.3,
        tem_constante  = 63.0,
        fase         = "calentando",
        bacterias= 0.0,
        tiempo       = 120.0,
        potencia     = 78.5
    )
    for clave, valor in datos.items():
        print(f"  {clave}: {valor}")