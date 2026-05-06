import  numpy as np
import control as ctrl
from parametros import K,tau, tiem_muerto, UA, calculoPID, masa_milk, calor_especificoMilk, ua_enf, temp_enf, potencia_max, agua_fria_temp, METODOS, temp_amb
from maquina import  planta_pasteurizacion, empaquetamiento
import matplotlib.pyplot as plt

#construccion del controlador 
def PID(kp, ki, kd, n=10.0): #n filtro , asi no amplificamos el ruido del sensor
    termino_proporcional=ctrl.TransferFunction([kp],[1]) #proporcional
    termino_integral= ctrl.TransferFunction([ki], [1,0])#integral
    termino_derivativo= ctrl.TransferFunction([kd*n,0],[1,n])#derivativa 

    control=termino_proporcional+termino_integral+termino_derivativo
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
    
    datos= METODOS[metodo]
    temp_objetivo= datos["temp_constante"] #objetivo
    tiempo_tot= min(5*tau,10800) # duracion de la simulacion
    
    t=np.linspace(0,tiempo_tot,3000)
    lazo_close= lazo_cerrado(kp,ki,kd)
    delta= temp_objetivo - temp_amb #incremento de temp 
    t_out, y = ctrl.step_response(lazo_close, t)

    T= temp_amb + y * delta #temp absoluto en C

    #verificacion
    temp_final= T[-1]
    error_final=abs(temp_objetivo-temp_final)
    if error_final >1.0:
        print(f"No se llego al setpint, error final: {error_final:.2f} oC")
    else:
        print(f"Se llego al setpoint, error final {error_final:.2f} oC")

    return t_out, T,temp_objetivo


#clase para unity
class SimuladorPasteurizador:
    def __init__(self):
        self.registro=[]
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


     #almacenamos formando un registro
    def _anotar(self, mensaje):
        entrada= f"[t={self.tiempo:.0f}s] {mensaje}"
        self.registro.append(entrada)
        print(entrada)
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

        self._anotar(f"[Simulador] Iniciando: {metodo}-"f"setpoint{METODOS[metodo]['temp_constante']} oC")

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

        #control de exceso de temp
        if self.temp > temp_constante + 5.0:
            self.error_ant=error
            return 0.0
    
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

    def actualizar_temp(self, potencia, dt):
        if self.fase in ("calentando", "mantenimiento"):
            #activamos resistencia
            pot_watts= (potencia/100.0)* potencia_max
            calor_tot= pot_watts - UA *(self.temp - temp_amb)
            dT = calor_tot/(masa_milk * calor_especificoMilk)* dt
        elif self.fase == "enfriando":
            #resistencia apagada
            calor_per= ua_enf * (self.temp - agua_fria_temp)
            dT = -calor_per/(masa_milk * calor_especificoMilk) *dt
        else:
            dT=0.0
        
        #aplicacion de la perturbacion
        if self.perturbacion != 0.0:
            dT += self.perturbacion
            print(f"[Simulador] perturbacion aplicada: {self.perturbacion:+.1f} oC")
            self.perturbacion = 0.0
        self.temp += dT
        self.temp = max(agua_fria_temp, self.temp) #temp no puede ser menor a agua fria


    def bacterias_actualizar(self, dt):
        datos=  METODOS[self.metodo]
        temp_minima_efec= 55.0
        #reudccion de baterias
        if self.temp <temp_minima_efec :
            return

        #formula bigelow
        d_actual = datos["tiempo_muertebac"] * 10 **(
            -(self.temp - datos["temp_ref"])/datos["z"]
        )

        #muerte en el momento
        k= np.log(10)/d_actual
        self.n *= np.exp(-k*dt)
        self.n= max(self.n, 1e-30)

    def fase_actualizar(self, dt):
        datos= METODOS[self.metodo]
        t_sp= datos["temp_constante"]
        t_mant= datos["tiempo"]

        if self.fase == "calentando":
            if self.temp >= t_sp * 0.98:
                self.fase= "mantenimiento"
                self.tiempo_fase  = 0.0
                self._anotar(f"[Simulador] mateniendo temperatura a{t_sp} oC")
        elif self.fase =="mantenimiento":
            self.tiempo_fase += dt
            if self.tiempo_fase >= t_mant:
                self.fase = "enfriando"
                self.tiempo_fase = 0.0
                self._anotar("[Simulador] Enfriando")
        elif self.fase == "enfriando":
            if self.temp <= agua_fria_temp + 2.0:
                self.fase = "completado"
                self.corriendo = False
                reduccion = np.log10(self.n_base / max(self.n, 1e-30))
                self._anotar(f"[Simulador]Completado")
                self._anotar(f"Reduccion bacteriana: {reduccion:.2f} log10")


    def avanzar(self, dt=1.0):
        if not self.corriendo or self.pausado:
            return
        
        t_sp= METODOS[self.metodo]["temp_constante"]

        #calculo pid para la potencia
        if self.fase in("calentando", "mantenimiento"):
            potencia= self.potencia_PID(t_sp, dt)
        else:
            potencia = 0.0 #apagamos resistencia 

        self.potencia= potencia
        self.actualizar_temp(potencia, dt)
        self.bacterias_actualizar(dt)
        self.tiempo += dt
        self.fase_actualizar(dt)

    def get_Estado(self):
        if self.n <self.n_base:
            pct_bacterias = (1.0 - self.n / self.n_base) * 100.0
        else:
            pct_bacterias = 0.0
        t_sp = METODOS[self.metodo]["temp_constante"] if self.corriendo else temp_amb

        estado= empaquetamiento(
            temp= self.temp,
            tem_constante= t_sp,
            fase= self.fase,
            bacterias= pct_bacterias,
            tiempo= self.tiempo,
            potencia= self.potencia
        )
        estado["reduccion_log10"] = round(
            np.log10(max(self.n_base / self.n, 1.0)),3
        )
        estado["metodo"]= self.metodo
        estado["simulacion_corriendo"]= self.corriendo
        estado["simulacion_pausada"]= self.pausado
        return estado
    
    def imprimir(self):
        print("\n==== Registro de procesos====")
        for evento in self.registro:
            print("", evento)

if __name__=="__main__":
    
    #lazo cerrado
    print("="*55)
    print("CONTROLADOR PASTEURIZADOR")
    print("="*55)

    kp, ki, kd = calculoPID("LTLT")
    print(f"Ganacias PID para LTLT:")
    print(f"KP={kp:.4f}")
    print(f"KI={ki:.6f}")
    print(f"KD={kd:.2f}")

    t,T, t_sp = resp_teorico("LTLT")
    plt.figure(figsize=(10,4))
    plt.plot(t/60, T, color="orange", linewidth=2, label ="temperatura actual")
    plt.axhline(y=t_sp, color="green", linestyle="--", linewidth=1.5, label=f"Setpoint{t_sp}oC")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("demo_lazo_cerrado.png", dpi=150)
    plt.close()
    print("\nGráfica guardada: demo_lazo_cerrado.png")

    # ── DEMOSTRACIÓN 2: simulación discreta paso a paso ─────
    # Muestra el PID funcionando en tiempo real con la clase
    print("\n" + "=" * 55)
    print("  Simulación discreta — 30 minutos")
    print("=" * 55)

    sim = SimuladorPasteurizador()
    sim.iniciar("LTLT")

    tiempos      = []
    temperaturas = []
    potencias    = []
    bacterias    = []

    # Simular 1800 pasos de 1 segundo = 30 minutos
    for _ in range(1800):
        sim.avanzar(dt=1.0)
        tiempos.append(sim.tiempo)
        temperaturas.append(sim.temp)
        potencias.append(sim.potencia)
        bacterias.append(
            (1.0 - sim.n / sim.n_base) * 100.0
            if sim.n < sim.n_base else 0.0
        )

    # Imprimir tabla de resultados cada 5 minutos
    print(f"\n{'Tiempo':>8} {'Temp':>8} {'Potencia':>10} "f"{'Fase':>15} {'Bact%':>8}")
    print("-" * 55)

    for i, t_i in enumerate(tiempos):
        if i % 300 == 0:   # cada 300 segundos = 5 minutos
            estado = sim.get_Estado()
            print(f"{t_i/60:>7.1f}m " f"{temperaturas[i]:>8.2f}°C "f"{potencias[i]:>9.1f}% "f"{estado['fase']:>15} "f"{bacterias[i]:>7.3f}%")

    # Gráfica de la simulación discreta
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))
    fig.suptitle("Simulación Discreta — PID Pasteurizador LTLT",
                 fontsize=13, fontweight='bold')

    t_min = [t / 60 for t in tiempos]

    # Temperatura
    ax1.plot(t_min, temperaturas, color='#FF5722', linewidth=2)
    ax1.axhline(y=63.0, color='green', linestyle='--',
                label='Setpoint 63°C')
    ax1.set_ylabel("Temperatura (°C)")
    ax1.set_title("Temperatura de la leche")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Potencia del PID
    ax2.plot(t_min, potencias, color='#2196F3', linewidth=2)
    ax2.set_ylabel("Potencia (%)")
    ax2.set_title("Señal de control del PID")
    ax2.set_ylim([0, 105])
    ax2.grid(True, alpha=0.3)

    # Bacterias destruidas
    ax3.plot(t_min, bacterias, color='#9C27B0', linewidth=2)
    ax3.axhline(y=99.999, color='red', linestyle='--',
                label='Objetivo FDA: 99.999%')
    ax3.set_ylabel("Bacterias destruidas (%)")
    ax3.set_xlabel("Tiempo (minutos)")
    ax3.set_title("Reducción bacteriana")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("demo_simulacion.png", dpi=150)
    plt.close()
    print("\nGráfica guardada: demo_simulacion.png")

    # Resultado final
    estado_final = sim.get_Estado()
    print("\n" + "=" * 55)
    print("  RESULTADO FINAL")
    print("=" * 55)
    print(f"  Temperatura final:     {estado_final['temperatura_actual']}°C")
    print(f"  Fase:                  {estado_final['fase']}")
    print(f"  Bacterias destruidas:  {estado_final['bacterias_destruidas']}%")
    print(f"  Reducción log10:       {estado_final['reduccion_log10']}")
    aprobado = estado_final['proceso_aceptado']
    print(f"  Proceso:               {'APROBADO' if aprobado else 'RECHAZADO'}")
