import  numpy as np
import control as ctrl
from parametros import K,tau, tem_muerto, UA, calculoPID, masa_milk, calor_especificoMilk, ua_enf, temp_enf, potencia_max, agua_fria_temp, pasteurizacion_metodos, temp_amb
from maquina import  planta_pasteurizacion, empaquetamiento

#construccion del controlador 
def PID(kp, ki, kd, n=10.0): #n filtro , asi no amplificamos el ruido del sensor
    p=ctrl.TransferFunction([kp],[1]) #proporcional
    i= ctrl.TransferFunction([ki], [1,0])#integral
    d= ctrl.TransferFunction([kd*n,0],[1,n])#derivativa 

    control= p+i+d
    return control


def lazo_cerrado(kp,ki,kd):
    g= planta_pasteurizacion()
    c= PID(kp,ki,kd)

    lazo_abierto= ctrl.series(c,g)
    lazo_close=ctrl.feedback(lazo_abierto,1) #cerramos el lazo 
    return lazo_close

def resp_teorico(metodo="LTLT", kp=None, ki=None, kd=None):
    if kp is None:
        kp, ki, kd = calculoPID()
    
    datos= pasteurizacion_metodos[metodo]
    t_const= datos["temp_constante"] #objetivo
    tiempo_tot= min(5*tau,10800) # duracion de la simulacion
    
    t=np.linspace(0,tiempo_tot,3000)
    lazo_close= lazo_cerrado(kp,ki,kd)
    delta= t_const - temp_amb #incremento de temp 
    t_out, y = ctrl.step_response(lazo_close, t)

    T= temp_amb + y * delta #temp absoluto en C
    return t_out, T,t_const


#clase para unity
class SimuladorPasteurizador:
    def __init__(self):
        self.corriendo = False
        self.pausado = False
        self.metodo = "LTLT"
        self.fase="esperando"
        self.temp= temp_amb
        self.tiempo= 0.0 #tiempo transcurrido
        self.tiempo_fase= 0.0 
        self.potencia= 0.0
        #bacterias
        self.n = 1e6 #bacterias iniciales 
        self.n_base= 1e6

        #para el PID no deben cambiar
        self.integral = 0.0
        self.error_ant= 0.0

        #pertubacion
        self.perturbacion = 0.0

#inicio
def iniciar(self, metodo="LTLT"):
    self.metodo = metodo
    self.temp= temp_amb
    self.tiempo = 0.0
    self.tiempo_fase=0.0
    self.fase = "calentando"
    self.potencia= 0.0
    self.n= self.n_base
    self.integral =0.0 #reseteo de memoria
    self.error_ant= 0.0 
    self.perturbacion = 0.0
    self.corriendo = True
    self.pausado= False

    print(f"[Simulador] Iniciando: {metodo}-"f"setpoint{pasteurizacion_metodos[metodo]['temp_constante']} oC")

def pausar(self):
    if self.corriendo:
        self.pausado = True
        print(f"[Simulador]Pausado -" f"T={self.temp:.1f}C, t={self.tiempo:.0f}s")

def reanudar(self):
    if self.corriendo and self.pausado:
        self.pausado = False
        print("[Simulador] Reanudando")

def reiniciar(self):
    self.corriendo = False
    self.pausado= False
    self.temp= temp_amb
    self.fase = "esperando"
    self.potencia = 0.0
    print("[Simulador] reiniciando")

def perturbar(self, delta):
    if self.corriendo and not self.pausado:
        self.perturbacion = delta
        print(f"[Simulador] Perturbacion programada: {delta:+.1f} oC")


def potencia_PID(self, temp_constante, dt):
    error= temp_constante - self.temp
    self.integral += error * dt #suma de error, acumulacion 

    #limitacion integral
    self.integral = max(-500.0, min(500.0, self.integral))

    #que tan rapido cae el error, cambio 
    if dt>0:
        derivada= (error- self.error_ant)/dt
    else:
        derivada=0.0
    
    kp, ki, kd = calculoPID(self.metodo) #obtencion ganancias
    
    #ecuacion PID
    potencia= kp*error+ ki*self.integral + kd * derivada

    #control resistencia
    potencia= max(0.0, min(100.0, potencia))
    self.error_ant= error
    return potencia