# -*- coding: utf-8 -*-
"""
generador_codigo_objeto.py
==========================
GENERACION DE CODIGO OBJETO (Unidad IV).

Recorre el AST y traduce el programa fuente a CODIGO OBJETO: un programa en
Python 3 listo para ejecutarse en la plataforma destino (Raspberry Pi).

Idea (adaptada a este proyecto): igual que un compilador para Arduino emitiria
un sketch en C++, aqui se emite un programa Python equivalente. El codigo
generado usa la libreria 'gpiozero' cuando se ejecuta sobre una Raspberry Pi
real; si gpiozero no esta disponible (por ejemplo en una PC normal), el mismo
archivo SIMULA el hardware por consola, de modo que el programa generado siempre
se puede ejecutar y demostrar.

Correspondencia principal lenguaje fuente -> codigo objeto (Python):
    entero/real/booleano/cadena   -> variables Python
    arreglos  tipo id[n];         -> listas Python  [0]*n
    si / sino                     -> if / else
    mientras                      -> while
    para                          -> while con inicializacion/actualizacion
    funcion id(params) { ... }    -> def id(params): ...
    imprimir(x);                  -> print(x)
    retraso(ms);                  -> time.sleep(ms/1000.0)
    dispositivo id = { ... };     -> id = Clase("id", attrs...)
    id->accion(arg);              -> id.accion(arg)
    id->valor()                   -> id.valor()
"""

import re


class GeneradorCodigoObjeto:
    """
    Uso:
        gen = GeneradorCodigoObjeto()
        codigo_python = gen.generar(ast_raiz)   # -> str
    """

    INDENT = "    "

    # tipo de dispositivo del lenguaje -> clase del runtime generado
    CLASES_DISPOSITIVO = {
        "led": "Led",
        "servo": "Servomotor",
        "motor": "MotorCC",
        "sensor": "Sensor",
        "buzzer": "Buzzer",
        "sensor_ultrasonico": "SensorUltrasonico",
        "sensor_color": "SensorColor",
        "sensor_toque": "SensorToque",
        "sensor_giro": "SensorGiro",
    }

    # accion del lenguaje -> metodo del runtime generado
    METODOS_ACCION = {
        "encender": "encender",
        "apagar": "apagar",
        "girarservo": "girarServo",
        "girarmotor": "girarMotor",
        "valor": "valor",
    }

    def __init__(self):
        self.lineas = []
        self.nivel = 0

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def generar(self, raiz):
        self.lineas = []
        self.nivel = 0
        self._preambulo()
        bloque = self._bloque_programa(raiz)
        if bloque is not None:
            for hijo in self._h(bloque):
                self._gen_sentencia(hijo)
        return "\n".join(self.lineas) + "\n"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _n(nodo):
        return str(getattr(nodo, "nombre", "")).strip()

    @staticmethod
    def _nl(nodo):
        return str(getattr(nodo, "nombre", "")).strip().lower()

    @staticmethod
    def _h(nodo):
        return getattr(nodo, "hijos", []) or []

    def _l(self, texto=""):
        if texto:
            self.lineas.append((self.INDENT * self.nivel) + texto)
        else:
            self.lineas.append("")

    def _bloque_programa(self, raiz):
        if raiz is None:
            return None
        if self._nl(raiz) == "programa":
            hijos = self._h(raiz)
            return hijos[0] if hijos else None
        return raiz

    # ------------------------------------------------------------------
    # Preambulo (runtime de dispositivos)
    # ------------------------------------------------------------------

    def _preambulo(self):
        pre = '''# -*- coding: utf-8 -*-
# ==========================================================================
#  CODIGO OBJETO GENERADO AUTOMATICAMENTE
#  Destino: Raspberry Pi / Python 3
#
#  Este archivo es el "codigo objeto": el programa final, equivalente al
#  programa fuente, listo para ejecutarse sobre la plataforma destino.
#  Si la libreria gpiozero esta disponible (Raspberry Pi), controla el
#  hardware real; en caso contrario, SIMULA cada dispositivo por consola,
#  de modo que el programa siempre se puede ejecutar para demostrarlo.
# ==========================================================================
import time

try:
    import gpiozero
    _HAY_GPIO = True
except Exception:
    _HAY_GPIO = False


class Dispositivo:
    """Clase base de los dispositivos del lenguaje."""

    def __init__(self, nombre, **attrs):
        self.nombre = nombre
        self.attrs = attrs

    def _attr(self, *nombres, defecto=None):
        for n in nombres:
            if n in self.attrs:
                return self.attrs[n]
        return defecto

    def encender(self):
        print("[%s] encender()" % self.nombre)

    def apagar(self):
        print("[%s] apagar()" % self.nombre)

    def girarServo(self, grados):
        print("[%s] girarServo(%s)" % (self.nombre, grados))

    def girarMotor(self, velocidad):
        print("[%s] girarMotor(%s)" % (self.nombre, velocidad))

    def valor(self):
        v = 0
        print("[%s] valor() -> %s" % (self.nombre, v))
        return v


class Led(Dispositivo):
    def __init__(self, nombre, **attrs):
        super().__init__(nombre, **attrs)
        self._dev = None
        if _HAY_GPIO and self._attr("pin") is not None:
            try:
                self._dev = gpiozero.LED(self._attr("pin"))
            except Exception:
                self._dev = None

    def encender(self):
        if self._dev:
            self._dev.on()
        print("[led %s] encender()" % self.nombre)

    def apagar(self):
        if self._dev:
            self._dev.off()
        print("[led %s] apagar()" % self.nombre)


class Buzzer(Dispositivo):
    def __init__(self, nombre, **attrs):
        super().__init__(nombre, **attrs)
        self._dev = None
        if _HAY_GPIO and self._attr("pin") is not None:
            try:
                self._dev = gpiozero.Buzzer(self._attr("pin"))
            except Exception:
                self._dev = None

    def encender(self):
        if self._dev:
            self._dev.on()
        print("[buzzer %s] encender()" % self.nombre)

    def apagar(self):
        if self._dev:
            self._dev.off()
        print("[buzzer %s] apagar()" % self.nombre)


class Servomotor(Dispositivo):
    def __init__(self, nombre, **attrs):
        super().__init__(nombre, **attrs)
        self._dev = None
        if _HAY_GPIO and self._attr("pin") is not None:
            try:
                self._dev = gpiozero.AngularServo(self._attr("pin"))
            except Exception:
                self._dev = None

    def girarServo(self, grados):
        if self._dev:
            try:
                self._dev.angle = grados
            except Exception:
                pass
        print("[servo %s] girarServo(%s)" % (self.nombre, grados))


class MotorCC(Dispositivo):
    def __init__(self, nombre, **attrs):
        super().__init__(nombre, **attrs)
        self._dev = None
        if _HAY_GPIO and self._attr("in1") is not None and self._attr("in2") is not None:
            try:
                self._dev = gpiozero.Motor(forward=self._attr("in1"),
                                           backward=self._attr("in2"))
            except Exception:
                self._dev = None

    def girarMotor(self, velocidad):
        if self._dev:
            try:
                v = max(-1.0, min(1.0, velocidad / 255.0))
                if v >= 0:
                    self._dev.forward(v)
                else:
                    self._dev.backward(-v)
            except Exception:
                pass
        print("[motor %s] girarMotor(%s)" % (self.nombre, velocidad))

    def apagar(self):
        if self._dev:
            try:
                self._dev.stop()
            except Exception:
                pass
        print("[motor %s] apagar()" % self.nombre)


class Sensor(Dispositivo):
    def valor(self):
        if _HAY_GPIO and self._attr("pin") is not None:
            try:
                d = gpiozero.InputDevice(self._attr("pin"))
                v = int(d.value)
            except Exception:
                v = 0
        else:
            import random
            v = random.randint(0, 1023)
        print("[sensor %s] valor() -> %s" % (self.nombre, v))
        return v


class SensorUltrasonico(Sensor):
    pass


class SensorColor(Sensor):
    pass


class SensorToque(Sensor):
    pass


class SensorGiro(Sensor):
    pass


# --------------------------------------------------------------------------
#  Programa traducido desde el lenguaje fuente
# --------------------------------------------------------------------------'''
        for ln in pre.split("\n"):
            self.lineas.append(ln)

    # ------------------------------------------------------------------
    # Sentencias
    # ------------------------------------------------------------------

    def _gen_sentencia(self, nodo):
        n = self._nl(nodo)

        if n == "declaracion":
            self._g_declaracion(nodo)
        elif n == "declaracion_error":
            pass
        elif n == "funcion":
            self._g_funcion(nodo)
        elif n == "llamada_funcion":
            self._l(self._expr_llamada(nodo))
        elif n == "imprimir":
            hijos = self._h(nodo)
            arg = self._expr(hijos[0]) if hijos else '""'
            self._l(f"print({arg})")
        elif n == "retraso":
            hijos = self._h(nodo)
            arg = self._expr(hijos[0]) if hijos else "0"
            self._l(f"time.sleep(({arg}) / 1000.0)")
        elif n == "si":
            self._g_si(nodo)
        elif n == "mientras":
            self._g_mientras(nodo)
        elif n == "para":
            self._g_para(nodo)
        elif n == "romper":
            self._l("break")
        elif n == "dispositivo":
            self._g_dispositivo(nodo)
        elif n == "accion_dispositivo":
            self._l(self._g_accion(nodo))
        elif n in ("bloque", "bloque_incompleto"):
            for h in self._h(nodo):
                self._gen_sentencia(h)

    def _g_cuerpo(self, bloque):
        hijos = self._h(bloque)
        if hijos:
            for h in hijos:
                self._gen_sentencia(h)
        else:
            self._l("pass")

    def _g_declaracion(self, nodo):
        hijos = self._h(nodo)
        total = len(hijos)

        if total == 3:  # tipo id ;
            tipo = self._nl(hijos[0])
            nombre = self._n(hijos[1])
            self._l(f"{nombre} = {self._defecto(tipo)}")
        elif total == 5:  # tipo id = expr ;
            nombre = self._n(hijos[1])
            self._l(f"{nombre} = {self._expr(hijos[3])}")
        elif total == 6:  # tipo id [tam] ;
            nombre = self._n(hijos[1])
            tam = self._n(hijos[3])
            self._l(f"{nombre} = [0] * {tam}")
        elif total == 7:  # id [indice] = expr ;
            nombre = self._n(hijos[0])
            idx = self._n(hijos[2])
            self._l(f"{nombre}[{idx}] = {self._expr(hijos[5])}")

    @staticmethod
    def _defecto(tipo):
        return {"entero": "0", "real": "0.0", "booleano": "False", "cadena": '""'}.get(tipo, "0")

    def _g_funcion(self, nodo):
        hijos = self._h(nodo)
        nombre = self._n(hijos[0])
        parametros = []
        for p in self._h(hijos[1]):
            if self._nl(p) == "parametro":
                ph = self._h(p)
                if len(ph) == 2:
                    parametros.append(self._n(ph[1]))
        self._l("")
        self._l(f"def {nombre}({', '.join(parametros)}):")
        self.nivel += 1
        self._g_cuerpo(hijos[2])
        self.nivel -= 1
        self._l("")

    def _g_si(self, nodo):
        hijos = self._h(nodo)
        self._l(f"if {self._cond(hijos[0])}:")
        self.nivel += 1
        self._g_cuerpo(hijos[1])
        self.nivel -= 1
        if len(hijos) >= 4:
            self._l("else:")
            self.nivel += 1
            self._g_cuerpo(hijos[3])
            self.nivel -= 1

    def _g_mientras(self, nodo):
        hijos = self._h(nodo)
        self._l(f"while {self._cond(hijos[0])}:")
        self.nivel += 1
        self._g_cuerpo(hijos[1])
        self.nivel -= 1

    def _g_para(self, nodo):
        hijos = self._h(nodo)
        # inicializacion
        if len(hijos) >= 1:
            self._g_asignacion_para(hijos[0])
        # condicion
        cond = self._cond(hijos[1]) if len(hijos) >= 2 else "True"
        self._l(f"while {cond}:")
        self.nivel += 1
        if len(hijos) >= 4:
            self._g_cuerpo(hijos[3])
        if len(hijos) >= 3:
            self._g_actualizacion_para(hijos[2])
        self.nivel -= 1

    def _g_asignacion_para(self, nodo):
        hijos = self._h(nodo)
        if len(hijos) == 4:     # tipo id = expr
            nombre = self._n(hijos[1])
            self._l(f"{nombre} = {self._expr(hijos[3])}")
        elif len(hijos) == 3:   # id = expr
            nombre = self._n(hijos[0])
            self._l(f"{nombre} = {self._expr(hijos[2])}")

    def _g_actualizacion_para(self, nodo):
        hijos = self._h(nodo)
        if len(hijos) == 2:     # id ++ / id --
            nombre = self._n(hijos[0])
            op = self._n(hijos[1])
            if op == "++":
                self._l(f"{nombre} = {nombre} + 1")
            elif op == "--":
                self._l(f"{nombre} = {nombre} - 1")
        elif len(hijos) == 3:   # id = expr
            nombre = self._n(hijos[0])
            self._l(f"{nombre} = {self._expr(hijos[2])}")

    def _g_dispositivo(self, nodo):
        hijos = self._h(nodo)
        tipo = self._nl(hijos[0])
        nombre = self._n(hijos[1])
        atributos = hijos[2]
        kwargs = []
        for atr in self._h(atributos):
            if self._nl(atr) == "atributo":
                ah = self._h(atr)
                if len(ah) == 2:
                    kwargs.append(f"{self._n(ah[0])}={self._expr(ah[1])}")
        clase = self.CLASES_DISPOSITIVO.get(tipo, "Dispositivo")
        if kwargs:
            self._l(f'{nombre} = {clase}("{nombre}", {", ".join(kwargs)})')
        else:
            self._l(f'{nombre} = {clase}("{nombre}")')

    def _g_accion(self, nodo):
        hijos = self._h(nodo)
        nombre = self._n(hijos[0])
        accion = self._nl(hijos[1])
        arg_nodo = hijos[2]
        metodo = self.METODOS_ACCION.get(accion, accion)
        if self._nl(arg_nodo) == "vacio":
            return f"{nombre}.{metodo}()"
        return f"{nombre}.{metodo}({self._expr(arg_nodo)})"

    # ------------------------------------------------------------------
    # Expresiones -> cadenas con codigo Python
    # ------------------------------------------------------------------

    def _cond(self, nodo):
        return self._expr(nodo)

    def _expr(self, nodo):
        if nodo is None:
            return "None"
        n = self._nl(nodo)

        if n == "constante":
            return self._expr_constante(nodo)
        if n == "arreglo":
            hijos = self._h(nodo)
            return f"{self._n(hijos[0])}[{self._n(hijos[1])}]"
        if n == "binop":
            hijos = self._h(nodo)
            izq = self._expr(hijos[0])
            op = self._op(self._n(hijos[1]))
            der = self._expr(hijos[2])
            return f"({izq} {op} {der})"
        if n == "unop":
            hijos = self._h(nodo)
            op = self._n(hijos[0])
            val = self._expr(hijos[1])
            if op == "!":
                return f"(not {val})"
            return f"(-{val})"
        if n == "valor_dispositivo":
            hijos = self._h(nodo)
            return f"{self._n(hijos[0])}.valor()"
        if n == "llamada_funcion":
            return self._expr_llamada(nodo)
        if n == "vacio":
            return ""
        return self._n(nodo)

    @staticmethod
    def _op(op):
        # &&/|| pasan a and/or; el resto coincide con Python
        return {"&&": "and", "||": "or"}.get(op, op)

    def _expr_constante(self, nodo):
        hijos = self._h(nodo)
        if not hijos:
            return "0"
        texto = self._n(hijos[0])
        if re.fullmatch(r"-?\d+", texto):
            return texto
        if re.fullmatch(r"-?\d+\.\d+", texto):
            return texto
        if texto.lower() == "true":
            return "True"
        if texto.lower() == "false":
            return "False"
        if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", texto):
            return texto  # variable / identificador
        # literal de cadena
        return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _expr_llamada(self, nodo):
        hijos = self._h(nodo)
        nombre = self._n(hijos[0])
        args = self._h(hijos[1]) if len(hijos) > 1 else []
        return f"{nombre}({', '.join(self._expr(a) for a in args)})"


# Compatibilidad con el estilo del proyecto
generador_codigo_objeto = GeneradorCodigoObjeto
