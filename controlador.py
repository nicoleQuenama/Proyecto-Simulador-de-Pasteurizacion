import numpy as np
import control as ctrl
import matplotlib.pyplot as plt
from parametros import (K, tau, tiempo_muerto, UA, calcular_PID, masa, calor_esp, UA_enfriamiento, temp_enfriamiento, potencia_max, temp_aguafria, METODOS, temp_amb, inicial_n)
from maquina import planta_pasteurizacion, empaquetamiento

# 🔥 FIREBASE — importar modulo y inicializar conexion
from firebase_pasteurizador import (
    inicializar_firebase,
    publicar_estado_inicial,
    publicar_cambio_fase,
    publicar_resultado_final,
    apagar_todo
)
inicializar_firebase()  # 🔥 se llama una sola vez al importar el modulo


def PID(kp, ki, kd, n=10.0):

    termino_p = ctrl.TransferFunction([kp], [1])
    termino_i = ctrl.TransferFunction([ki], [1, 0])
    termino_d = ctrl.TransferFunction([kd * n, 0], [1, n])
    controlador = termino_p + termino_i + termino_d
    return controlador


def lazo_cerrado(kp, ki, kd):
    G = planta_pasteurizacion()
    C = PID(kp, ki, kd)
    lazo_ab = ctrl.series(C, G)
    lazo_cl = ctrl.feedback(lazo_ab, 1)
    return lazo_cl


def resp_teorica(metodo="LTLT", kp=None, ki=None, kd=None):

    if kp is None:
        kp, ki, kd = calcular_PID(metodo)

    datos = METODOS[metodo]
    temp_objetivo = datos["temp_constante"]
    dur_sim = min(5 * tau, 10800)
    t = np.linspace(0, dur_sim, 3000)
    lc = lazo_cerrado(kp, ki, kd)
    incremento = temp_objetivo - temp_amb
    t_out, y = ctrl.step_response(lc, t)
    T = temp_amb + y * incremento
    error_final = abs(temp_objetivo - T[-1])
    if error_final > 1.0:
        print(f"[Aviso] No llego al setpoint. Error final: {error_final:.2f}°C")
    else:
        print(f"[OK] Llego al setpoint. Error final: {error_final:.2f}°C")

    return t_out, T, temp_objetivo


class SimuladorPasteurizador:

    def __init__(self):
        self.corriendo   = False
        self.pausado     = False
        self.metodo      = "LTLT"
        self.fase        = "esperando"

        # Estado termico
        self.temp        = temp_amb
        self.tiempo      = 0.0
        self.tiempo_fase = 0.0
        self.potencia    = 0.0

        # Estado bacteriano
        # n_base nunca cambia — necesario para calcular reduccion
        # n cambia en cada paso de bacterias_actualizar()
        self.n      = inicial_n
        self.n_base = inicial_n

        # Memoria del PID
        # integral acumula el error con el tiempo (termino I)
        # error_ant guarda el error previo para la derivada (termino D)
        self.integral  = 0.0
        self.error_ant = 0.0

        # Perturbacion pendiente de aplicar
        self.perturbacion      = 0.0
        self.valor_F           = 0.0
        self.energia_consumida = 0.0
        self.alarmas           = []
        self.registro          = []

    def _anotar(self, mensaje):
        entrada = f"[t={self.tiempo:.0f}s] {mensaje}"
        self.registro.append(entrada)
        print(entrada)

    # ─────────────────────────────────────────────────────────
    def iniciar(self, metodo="LTLT"):
        self.metodo      = metodo
        self.temp        = temp_amb
        self.tiempo      = 0.0
        self.tiempo_fase = 0.0
        self.fase        = "calentando"
        self.potencia    = 0.0
        self.n           = inicial_n
        self.n_base      = inicial_n

        self.integral     = 0.0
        self.error_ant    = 0.0
        self.perturbacion = 0.0

        self.valor_F           = 0.0
        self.energia_consumida = 0.0
        self.alarmas           = []
        self.registro          = []

        self.corriendo = True
        self.pausado   = False

        self._anotar(f"Iniciando {metodo} — setpoint {METODOS[metodo]['temp_constante']}°C")

        # 🔥 FIREBASE — publicar estado inicial al arrancar
        publicar_estado_inicial(
            metodo       = metodo,
            temp_setpoint= METODOS[metodo]["temp_constante"]
        )

    # ─────────────────────────────────────────────────────────
    def pausar(self):
        if self.corriendo:
            self.pausado = True
            self._anotar(f"Pausado — T={self.temp:.1f}°C")

    def reanudar(self):
        if self.corriendo and self.pausado:
            self.pausado = False
            self._anotar("Reanudado")

    # ─────────────────────────────────────────────────────────
    def reiniciar(self):
        self.corriendo = False
        self.pausado   = False
        self.temp      = temp_amb
        self.fase      = "esperando"
        self.potencia  = 0.0
        print("[Simulador] Reiniciado")

        # 🔥 FIREBASE — apagar motores y LEDs al reiniciar
        apagar_todo()

    # ─────────────────────────────────────────────────────────
    def perturbar(self, delta):
        if self.corriendo and not self.pausado:
            self.perturbacion = delta
            self._anotar(f"Perturbacion programada: {delta:+.1f}°C")

    def potencia_PID(self, temp_objetivo, dt):

        error = temp_objetivo - self.temp
        self.integral += error * dt
        self.integral = max(-500.0, min(500.0, self.integral))
        if dt > 0:
            derivada = (error - self.error_ant) / dt
        else:
            derivada = 0.0

        if self.temp > temp_objetivo + 5.0:
            self.error_ant = error
            return 0.0

        kp, ki, kd = calcular_PID(self.metodo)
        potencia    = kp * error + ki * self.integral + kd * derivada
        potencia    = max(0.0, min(100.0, potencia))

        self.error_ant = error
        return potencia

    def actualizar_temp(self, potencia, dt):

        if self.fase in ("calentando", "mantenimiento"):
            pot_watts  = (potencia / 100.0) * potencia_max
            calor_neto = pot_watts - UA * (self.temp - temp_amb)
            dT = calor_neto / (masa * calor_esp) * dt

        elif self.fase == "enfriando":
            calor_perdido = UA_enfriamiento * (self.temp - temp_aguafria)
            dT = -calor_perdido / (masa * calor_esp) * dt

        else:
            dT = 0.0

        if self.perturbacion != 0.0:
            dT += self.perturbacion
            self._anotar(f"Perturbacion aplicada: {self.perturbacion:+.1f}°C")
            self.perturbacion = 0.0

        self.temp += dT
        self.temp = max(temp_aguafria, self.temp)

    def bacterias_actualizar(self, dt):
        datos = METODOS[self.metodo]
        TEMP_MIN_EFECTIVA = 55.0
        if self.temp < TEMP_MIN_EFECTIVA:
            return
        d_actual = datos["tiempo_muertebac"] * 10 ** (
            -(self.temp - datos["temp_ref"]) / datos["z"]
        )
        k = np.log(10) / d_actual
        self.n *= np.exp(-k * dt)
        self.n  = max(self.n, 1e-30)

    def calcular_valor_F(self, dt):
        datos = METODOS[self.metodo]
        if self.temp >= 55.0:
            self.valor_F += 10 ** (
                (self.temp - datos["temp_ref"]) / datos["z"]
            ) * dt

    def calcular_energia(self, potencia, dt):
        watts = (potencia / 100.0) * potencia_max
        self.energia_consumida += watts * (dt / 3600.0)

    def verificar_alarmas(self, temp_objetivo):
        self.alarmas = []

        if self.temp > temp_objetivo * 1.05:
            self.alarmas.append("TEMP_SOBRE_RANGO")

        if self.tiempo > 1800 and self.fase == "calentando":
            self.alarmas.append("TEMP_NO_ALCANZADA")

        if self.tiempo > 7200:
            self.alarmas.append("TIEMPO_EXCEDIDO")

        if self.alarmas:
            self._anotar(f"Alarmas activas: {self.alarmas}")

    # ─────────────────────────────────────────────────────────
    def fase_actualizar(self, dt):
        datos  = METODOS[self.metodo]
        t_sp   = datos["temp_constante"]
        t_mant = datos["tiempo"]

        if self.fase == "calentando":
            if self.temp >= t_sp * 0.98:
                self.fase        = "mantenimiento"
                self.tiempo_fase = 0.0
                self._anotar(f"Fase: MANTENIMIENTO a {t_sp}°C")
                # 🔥 FIREBASE — notificar cambio a mantenimiento
                publicar_cambio_fase("mantenimiento", self.get_Estado())

        elif self.fase == "mantenimiento":
            self.tiempo_fase += dt
            if self.tiempo_fase >= t_mant:
                self.fase        = "enfriando"
                self.tiempo_fase = 0.0
                self._anotar("Fase: ENFRIANDO")
                # 🔥 FIREBASE — notificar cambio a enfriando + activar motor 1
                publicar_cambio_fase("enfriando", self.get_Estado())

        elif self.fase == "enfriando":
            if self.temp <= temp_aguafria + 2.0:
                self.fase      = "completado"
                self.corriendo = False
                reduccion = np.log10(self.n_base / max(self.n, 1e-30))
                self._anotar(f"Fase: COMPLETADO — reduccion {reduccion:.2f} log10")
                # 🔥 FIREBASE — notificar completado (motor 2 o motor 3 segun resultado)
                publicar_cambio_fase("completado", self.get_Estado())

    # ─────────────────────────────────────────────────────────
    def avanzar(self, dt=1.0):
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
        self.calcular_valor_F(dt)
        self.calcular_energia(potencia, dt)
        self.verificar_alarmas(t_sp)
        self.tiempo += dt
        self.fase_actualizar(dt)

    # ─────────────────────────────────────────────────────────
    def evaluar_proceso(self):
        reduccion = np.log10(self.n_base / max(self.n, 1e-30))

        criterio_bacterias  = reduccion >= 5.0
        criterio_temp       = self.temp <= temp_aguafria + 3.0
        criterio_completado = self.fase == "completado"

        aprobado = criterio_bacterias and criterio_temp and criterio_completado

        print("\n=== EVALUACION FINAL ===")
        print(f"  Reduccion bacteriana: {reduccion:.2f} log10 -> {'OK' if criterio_bacterias else 'FALLA'}")
        print(f"  Temperatura final:    {self.temp:.1f}°C     -> {'OK' if criterio_temp else 'FALLA'}")
        print(f"  Proceso completado:   {self.fase}           -> {'OK' if criterio_completado else 'FALLA'}")
        print(f"  Energia consumida:    {self.energia_consumida:.2f} Wh")
        print(f"  Valor F acumulado:    {self.valor_F:.2f}")
        print(f"  RESULTADO: {'APROBADO' if aprobado else 'RECHAZADO'}")

        # 🔥 FIREBASE — publicar resultado final con aprobado/rechazado
        publicar_resultado_final(
            estado    = self.get_Estado(),
            aprobado  = aprobado,
            reduccion = reduccion,
            energia   = self.energia_consumida
        )

        return aprobado

    # ─────────────────────────────────────────────────────────
    def get_Estado(self):

        if self.n < self.n_base:
            pct_bacterias = (1.0 - self.n / self.n_base) * 100.0
        else:
            pct_bacterias = 0.0

        t_sp = METODOS[self.metodo]["temp_constante"] if self.corriendo else temp_amb

        estado = empaquetamiento(
            temp          = self.temp,
            tem_constante = t_sp,
            fase          = self.fase,
            bacterias     = pct_bacterias,
            tiempo        = self.tiempo,
            potencia      = self.potencia
        )

        estado["concentracion_restante"] = round(self.n, 2)
        estado["valor_F"]                = round(self.valor_F, 3)
        estado["reduccion_log10"]        = round(
            np.log10(max(self.n_base / self.n, 1.0)), 3
        )
        estado["energia_consumida_wh"]   = round(self.energia_consumida, 2)
        estado["alarmas"]                = self.alarmas
        estado["hay_alarma"]             = len(self.alarmas) > 0
        estado["metodo"]                 = self.metodo
        estado["simulacion_corriendo"]   = self.corriendo
        estado["simulacion_pausada"]     = self.pausado

        return estado


# ── VERIFICACION ─────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 55)
    print("  CONTROLADOR PASTEURIZADOR")
    print("=" * 55)

    kp, ki, kd = calcular_PID("LTLT")
    print(f"\nGanancias PID para LTLT:")
    print(f"  Kp = {kp:.4f}")
    print(f"  Ki = {ki:.6f}")
    print(f"  Kd = {kd:.2f}")

    print("\nCalculando respuesta teorica...")
    t, T, t_sp = resp_teorica("LTLT")

    plt.figure(figsize=(10, 4))
    plt.plot(t / 60, T, color="orange", linewidth=2, label="Temperatura")
    plt.axhline(y=t_sp, color="green", linestyle="--",
                label=f"Setpoint {t_sp}°C")
    plt.xlabel("Tiempo (minutos)")
    plt.ylabel("Temperatura (°C)")
    plt.title("Lazo Cerrado — Respuesta teorica PID LTLT")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("demo_lazo_cerrado.png", dpi=150)
    plt.close()
    print("Grafica guardada: demo_lazo_cerrado.png")

    print("\n" + "=" * 55)
    print("  Simulacion discreta — 30 minutos")
    print("=" * 55)

    sim = SimuladorPasteurizador()
    sim.iniciar("LTLT")

    tiempos      = []
    temperaturas = []
    potencias    = []
    bacterias    = []

    for _ in range(1800):
        sim.avanzar(dt=1.0)
        tiempos.append(sim.tiempo)
        temperaturas.append(sim.temp)
        potencias.append(sim.potencia)
        bacterias.append(
            (1.0 - sim.n / sim.n_base) * 100.0
            if sim.n < sim.n_base else 0.0
        )

    print(f"\n{'Tiempo':>8} {'Temp':>8} {'Potencia':>10} "
          f"{'Fase':>15} {'Bact%':>8}")
    print("-" * 55)

    for i, t_i in enumerate(tiempos):
        if i % 300 == 0:
            e = sim.get_Estado()
            print(f"{t_i/60:>7.1f}m "
                  f"{temperaturas[i]:>8.2f}°C "
                  f"{potencias[i]:>9.1f}% "
                  f"{e['fase']:>15} "
                  f"{bacterias[i]:>7.3f}%")

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))
    fig.suptitle("Simulacion Discreta — PID Pasteurizador LTLT",
                 fontsize=13, fontweight="bold")
    t_min = [t / 60 for t in tiempos]

    ax1.plot(t_min, temperaturas, color="#FF5722", linewidth=2)
    ax1.axhline(y=63.0, color="green", linestyle="--", label="Setpoint 63°C")
    ax1.set_ylabel("Temperatura (°C)")
    ax1.set_title("Temperatura de la leche")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(t_min, potencias, color="#2196F3", linewidth=2)
    ax2.set_ylabel("Potencia (%)")
    ax2.set_title("Señal de control del PID")
    ax2.set_ylim([0, 105])
    ax2.grid(True, alpha=0.3)

    ax3.plot(t_min, bacterias, color="#9C27B0", linewidth=2)
    ax3.axhline(y=99.999, color="red", linestyle="--",
                label="Objetivo FDA: 99.999%")
    ax3.set_ylabel("Bacterias destruidas (%)")
    ax3.set_xlabel("Tiempo (minutos)")
    ax3.set_title("Reduccion bacteriana")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("demo_simulacion.png", dpi=150)
    plt.close()
    print("\nGrafica guardada: demo_simulacion.png")

    sim.evaluar_proceso()