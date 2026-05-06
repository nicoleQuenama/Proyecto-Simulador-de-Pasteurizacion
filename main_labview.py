import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from controlador import SimuladorPasteurizador

def ejecutar_simulacion(metodo, tiempo_segundos):
    sim = SimuladorPasteurizador()
    sim.iniciar(metodo)

    tiempos = []
    temperaturas = []
    potencias = []
    bacterias=[]
    pasos = int(tiempo_segundos)
    for _ in range(pasos):
        sim.avanzar(dt=1.0)

        tiempos.append(float(sim.tiempo /60.0))
        temperaturas.append(float(sim.temp))
        potencias.append(float(sim.potencia))

        #bacterias destruidas
        if sim.n < sim.n_base:
            pct = (1.0- sim.n/ sim.n_base)* 100.0
        else:
            pct = 0.0
        bacterias.append(float(pct))

    return tiempos,bacterias,temperaturas,potencias