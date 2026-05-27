import sys
import os

#leemos la carpeta
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from controlador import SimuladorPasteurizador

#variable global para el labview
sim = None

def iniciar_simulacion(metodo):
    global sim
    sim = SimuladorPasteurizador()
    sim.iniciar(metodo)

    return True 

def simulacion(kp, ki, kd, setpoint, ruido, inyectar_perturbacion):
    global sim

    if sim is None:
        return 0.0, 0.0, 0.0,0.0
    
    #valores para labview
    sim.kp = kp
    sim.ki = ki
    sim.kd =kd
    sim.temp_override = setpoint
    sim.ruido_nivel = ruido

    #boton de perturbacion
    if inyectar_perturbacion:
        sim.perturbar(-10.0)

    #avance del tiempo
    sim.avanzar(dt=1.0)

    #calculo de las bacterias
    if sim.n < sim.n_base:
        pct_bac = (1.0 - sim.n / sim.n_base) * 100.0
    else:
        pct_bac = 0.0

    tiempo_min = float(sim.tiempo /60.0)

    return tiempo_min, float(pct_bac), float(sim.temp), float(sim. potencia)