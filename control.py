import  numpy as np
import control as ctrl
from parametros import K,tau, tem_muerto, UA, calculoPID, masa_milk, calor_especificoMilk, ua_enf, temp_enf, potencia_max, agua_fria_temp, pasteurizacion_metodos, temp_amb
from maquina import  planta_pasteurizacion, empaquetamiento

def PID(kp, ki, kd, n=10.0):
    p=ctrl.TransferFunction([kp],[1])
    i= ctrl.TransferFunction([ki], [1,0])
    d= ctrl.TransferFunction([kd*n,0],[1,n])

    control= p+i+d
    return control

def lazo_cerrado(kp,ki,kd):
    g= planta_pasteurizacion()
    c= calculoPID(kp,ki,kd)

    lazo_abierto= ctrl.series(c,g)
    lazo_close=ctrl.feedback(lazo_abierto,1)
    return lazo_cerrado

def resp_teorico(metodo="LTLT", kp=None, ki=None, kd=None):
    if kp is None:
        kp, ki, kd = calculoPID()
    
    datos= pasteurizacion_metodos[metodo]
    t_const= datos["temp_constante"]
    tiempo_tot= min(5*tau,10800)
    
    t=np.linspace(0,tiempo_tot,3000)
    lazo_close= lazo_cerrado(kp,ki,kd)
    delta= t_const - temp_amb
    t_out, y = ctrl.step_response(lazo_close, t)

    T= temp_amb+y*delta
    return t_out, T,t_const

