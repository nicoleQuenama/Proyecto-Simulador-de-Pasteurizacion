import numpy as np
import control as ctrl
from parametros import (
    K, tau, tiem_muerto, UA, calculoPID,
    masa_milk, calor_especificoMilk,
    ua_enf, temp_enf, potencia_max,
    agua_fria_temp, METODOS, temp_amb
)
from maquina import planta_pasteurizacion, empaquetamiento
import matplotlib.pyplot as plt


# --- CONTROLADOR Y FEEDBACK ---

def PID(kp, ki, kd, n=10.0):
    # Meto el filtro N para que el ruido del sensor no me sature la derivada.
    # Es como ponerle un "lente" más limpio al sensor para que no se vuelva loco con los cambios bruscos.
    termino_proporcional = ctrl.TransferFunction([kp], [1])
    termino_integral     = ctrl.TransferFunction([ki], [1, 0])
    termino_derivativo   = ctrl.TransferFunction([kd * n, 0], [1, n])
    
    # La suma de los tres términos nos da el controlador completo.
    return termino_proporcional + termino_integral + termino_derivativo


def lazo_cerrado(kp, ki, kd):
    # g representa nuestra planta (la máquina física de pasteurización).
    # c es el "cerebro" o controlador que acabamos de definir.
    g = planta_pasteurizacion()
    c = PID(kp, ki, kd)
    
    # Conectamos en serie el controlador con la planta.
    lazo_abierto = ctrl.series(c, g)
    
    # Creamos el feedback (retroalimentación) con una ganancia unitaria (1).
    # Esto permite que el sistema se compare a sí mismo constantemente.
    return ctrl.feedback(lazo_abierto, 1)


def resp_teorico(metodo="LTLT", kp=None, ki=None, kd=None):
    # Si no entran ganancias por parámetro, uso las de la sintonización por defecto.
    # Es como tener un "ajuste de fábrica" siempre listo.
    if kp is None:
        kp, ki, kd = calculoPID(metodo)

    datos         = METODOS[metodo]
    temp_objetivo = datos["temp_constante"]
    
    # Definimos el tiempo total de la gráfica basándonos en la constante de tiempo (tau).
    tiempo_tot    = min(5 * tau, 10800) 

    t           = np.linspace(0, tiempo_tot, 3000)
    lazo_close  = lazo_cerrado(kp, ki, kd)
    delta        = temp_objetivo - temp_amb 

    # Calculamos la respuesta al escalón (step_response) para ver cómo llega al setpoint.
    t_out, y = ctrl.step_response(lazo_close, t)
    T = temp_amb + y * delta 

    # Check de seguridad por si el PID no converge o "se dispara".
    # Si el error final es muy grande, algo está mal sintonizado.
    error_final = abs(temp_objetivo - T[-1])
    if error_final > 1.0:
        print(f"Error alto: {error_final:.2f} °C")
    else:
        print(f"Setpoint OK: {error_final:.2f} °C")

    return t_out, T, temp_objetivo


# --- CLASE DEL SIMULADOR ---

class SimuladorPasteurizador:
    """
    Clase que maneja toda la lógica del proceso.
    Aquí arreglamos el bug del error anterior y metimos un Anti-Windup real.
    El Anti-Windup es como un "freno" para que la integral no siga acumulando error 
    cuando la potencia ya está al 100%.
    """

    N_MIN_LOG = 4
    N_MAX_LOG = 8

    def __init__(self):
        # Inicializamos todas las variables que rastrean el estado del sistema.
        self.registro  = []
        self.corriendo = False
        self.pausado   = False
        self.metodo    = "LTLT"
        self.fase      = "esperando" # Estados: esperando, calentando, mantenimiento, enfriando.
        self.temp      = temp_amb
        self.tiempo    = 0.0
        self.tiempo_fase = 0.0
        self.potencia  = 0.0

        # Genero carga bacteriana random para que cada simulación sea un reto diferente.
        self.n_inicial = self._generar_bacterias()
        self.n         = self.n_inicial

        # Variables necesarias para el algoritmo PID discreto.
        self.integral  = 0.0
        self.error_ant = 0.0 
        self.perturbacion_watts = 0.0

    # --- Helpers (Funciones de apoyo) ---

    def _generar_bacterias(self):
        # Usamos una escala logarítmica para representar millones de bacterias.
        exp = np.random.uniform(self.N_MIN_LOG, self.N_MAX_LOG)
        return 10 ** exp

    def _anotar(self, mensaje):
        # Este es nuestro "log". Guarda lo que pasa para mostrarlo al final.
        entrada = f"[t={self.tiempo:.0f}s] {mensaje}"
        self.registro.append(entrada)
        print(entrada)

    def _limite_windup(self):
        # Calculamos hasta dónde puede llegar la integral antes de saturar.
        _, ki, _ = calculoPID(self.metodo)
        if ki > 0:
            return 100.0 / ki 
        return 500.0

    # --- Máquina de Estados (El flujo del proceso) ---

    def iniciar(self, metodo="LTLT"):
        # Reseteamos todo para una nueva corrida.
        self.metodo      = metodo
        self.temp        = temp_amb
        self.tiempo      = 0.0
        self.tiempo_fase = 0.0
        self.fase        = "calentando"
        self.potencia    = 0.0
        self.integral    = 0.0
        self.error_ant   = 0.0
        self.perturbacion_watts = 0.0
        self.corriendo   = True
        self.pausado     = False

        self.n_inicial = self._generar_bacterias()
        self.n         = self.n_inicial

        self._anotar(f"Iniciando {metodo} | N0: {self.n_inicial:.2e}")

    def reiniciar_lote(self):
        # Permite cambiar el tanque de leche sin apagar toda la lógica de la máquina.
        if not self.corriendo:
            self.n_inicial = self._generar_bacterias()
            self.n         = self.n_inicial
            self._anotar(f"Lote nuevo: {self.n_inicial:.2e}")
        else:
            print("ERROR: No se puede cambiar el lote mientras el proceso está en marcha.")

    def pausar(self):
        if self.corriendo:
            self.pausado = True

    def reanudar(self):
        if self.corriendo and self.pausado:
            self.pausado = False

    def perturbar(self, watts):
        # Simula un "golpe" de calor o frío externo (ruido térmico).
        # Es útil para probar qué tan robusto es nuestro PID.
        if self.corriendo and not self.pausado:
            self.perturbacion_watts = watts

    # --- Lógica PID Discreto ---

    def potencia_PID(self, temp_constante, dt):
        # El corazón del control: Error = Setpoint - Real.
        error = temp_constante - self.temp

        # Shutdown de emergencia: Si la temperatura se dispara, apagamos resistencias.
        if self.temp > temp_constante + 5.0:
            self.error_ant = error
            return 0.0

        # Cálculo Integral con protección Anti-Windup (el clamp que mencionamos arriba).
        self.integral += error * dt
        lim = self._limite_windup()
        self.integral = max(-lim, min(lim, self.integral))

        # Cálculo de la Derivada: ¿Qué tan rápido está cambiando el error?
        derivada = (error - self.error_ant) / dt if dt > 0 else 0.0

        # Sumamos las tres acciones (P + I + D).
        kp, ki, kd = calculoPID(self.metodo)
        potencia = kp * error + ki * self.integral + kd * derivada
        
        # Clamp 0-100%: La potencia no puede ser negativa ni mayor a la capacidad máxima.
        potencia = max(0.0, min(100.0, potencia))

        # Guardamos el error actual para la siguiente iteración (clave para la derivada).
        self.error_ant = error
        return potencia

    # --- Modelo de la Planta (Física Térmica) ---

    def actualizar_temp(self, potencia, dt):
        # Aquí simulamos la transferencia de calor real.
        if self.fase in ("calentando", "mantenimiento"):
            pot_watts = (potencia / 100.0) * potencia_max
            calor_tot = pot_watts - UA * (self.temp - temp_amb) 
            dT = calor_tot / (masa_milk * calor_especificoMilk) * dt

        elif self.fase == "enfriando":
            # En el enfriamiento, el calor se pierde hacia el agua fría.
            calor_per = ua_enf * (self.temp - agua_fria_temp) 
            dT = -calor_per / (masa_milk * calor_especificoMilk) * dt

        else:
            dT = 0.0

        # Si hubo una perturbación manual, la aplicamos aquí.
        if self.perturbacion_watts != 0.0:
            dT += self.perturbacion_watts / (masa_milk * calor_especificoMilk) * dt
            self.perturbacion_watts = 0.0

        self.temp += dT
        # La temperatura nunca puede ser menor que la del agua de enfriamiento.
        self.temp = max(agua_fria_temp, self.temp)

    def bacterias_actualizar(self, dt):
        # Modelo Bigelow: Calculamos cuántas bacterias mueren por cada segundo de calor.
        datos = METODOS[self.metodo]
        if self.temp < 55.0:
            return # A menos de 55°C, las bacterias no mueren significativamente.

        d_actual = datos["tiempo_muertebac"] * 10 ** (
            -(self.temp - datos["temp_ref"]) / datos["z"]
        )
        k = np.log(10) / d_actual
        self.n *= np.exp(-k * dt)
        self.n = max(self.n, 1e-30) # Evitamos que llegue a cero absoluto para evitar errores matemáticos.

    def fase_actualizar(self, dt):
        # Controla el paso de una etapa a otra (Calentamiento -> Mantenimiento -> Enfriamiento).
        datos = METODOS[self.metodo]
        t_sp  = datos["temp_constante"]
        t_mant = datos["tiempo"]

        if self.fase == "calentando":
            # Si llegamos al 98% de la temperatura objetivo, empezamos el cronómetro de mantenimiento.
            if self.temp >= t_sp * 0.98:
                self.fase        = "mantenimiento"
                self.tiempo_fase = 0.0
                self._anotar(f"Setpoint alcanzado: {t_sp}°C")

        elif self.fase == "mantenimiento":
            self.tiempo_fase += dt
            if self.tiempo_fase >= t_mant:
                self.fase        = "enfriando"
                self.tiempo_fase = 0.0
                self._anotar("Fin de tiempo de mantenimiento")

        elif self.fase == "enfriando":
            # Terminamos cuando la leche está fría y segura para envasar.
            if self.temp <= agua_fria_temp + 2.0:
                self.fase      = "completado"
                self.corriendo = False
                reduccion = np.log10(self.n_inicial / max(self.n, 1e-30))
                self._anotar(f"Proceso finalizado. Reducción: {reduccion:.2f} log")

    def avanzar(self, dt=1.0):
        # Esta es la función que "mueve" el tiempo en la simulación paso a paso.
        if not self.corriendo or self.pausado:
            return

        t_sp = METODOS[self.metodo]["temp_constante"]

        if self.fase in ("calentando", "mantenimiento"):
            potencia = self.potencia_PID(t_sp, dt)
        else:
            potencia = 0.0

        self.potencia = potencia
        self.actualizar_temp(potencia, dt)
        self.bacterias_actualizar(dt)
        self.tiempo += dt
        self.fase_actualizar(dt)

    # --- Empaquetamiento de datos (Serialización) ---

    def get_Estado(self):
        # Preparamos un diccionario con toda la info actual para que la interfaz la lea fácil.
        pct_bac = (
            (1.0 - self.n / self.n_inicial) * 100.0
            if self.n < self.n_inicial else 0.0
        )
        t_sp = METODOS[self.metodo]["temp_constante"] if self.corriendo else temp_amb

        estado = empaquetamiento(
            temp=self.temp,
            tem_constante=t_sp,
            fase=self.fase,
            bacterias=pct_bac,
            tiempo=self.tiempo,
            potencia=self.potencia
        )

        # Calculamos la reducción logarítmica (Lo que pide la FDA para seguridad alimentaria).
        reduccion = np.log10(max(self.n_inicial / max(self.n, 1e-30), 1.0))

        estado["reduccion_log10"]       = round(reduccion, 3)
        estado["metodo"]                 = self.metodo
        estado["simulacion_corriendo"]   = self.corriendo
        estado["simulacion_pausada"]     = self.pausado
        estado["bacterias_iniciales"]    = round(self.n_inicial, 2)
        estado["bacterias_actuales"]     = round(self.n, 4)
        estado["seguro_fda"]             = reduccion >= 5.0 # Si es > 5 log, la leche es segura.

        return estado