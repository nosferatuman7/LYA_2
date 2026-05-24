# -*- coding: utf-8 -*-
"""
interprete.py
=============
INTERPRETE / EJECUTOR del lenguaje (Unidad IV - "mostrar la ejecucion del lenguaje").

Recorre el AST producido por el analizador sintactico y EJECUTA el programa:
  - declaracion y uso de variables (entero, real, booleano, cadena) y arreglos
  - expresiones aritmeticas, relacionales, logicas y unarias
  - estructuras de control: si / sino, mientras, para, romper
  - funciones (definicion, llamada y paso de parametros)
  - imprimir(...) y retraso(...)
  - dispositivos: definicion y acciones (encender, apagar, girarServo, girarMotor, valor)

Los dispositivos se SIMULAN: cada accion se reporta en la consola de ejecucion y
las lecturas de sensores (valor()) devuelven un valor simulado. Asi se observa el
comportamiento del programa sin necesidad de hardware fisico (Raspberry Pi).

El interprete incluye una guarda contra bucles infinitos (por ejemplo
"mientras (true)"): al superar 'max_iteraciones' la ejecucion se detiene de forma
controlada e informa al usuario.
"""

import re
import random


# ---------------------------------------------------------------------------
# Senales internas de control de flujo
# ---------------------------------------------------------------------------

class SenalRomper(Exception):
    """Se lanza al ejecutar 'romper' para salir del bucle actual."""
    pass


class LimiteIteraciones(Exception):
    """Se lanza cuando se supera el limite de iteraciones (posible bucle infinito)."""
    pass


class ErrorEjecucion(Exception):
    """Error de ejecucion controlado del interprete."""
    pass


# ---------------------------------------------------------------------------
# Dispositivo simulado
# ---------------------------------------------------------------------------

class DispositivoSimulado:
    """Representa, en memoria, un dispositivo declarado en el lenguaje."""

    def __init__(self, nombre, tipo, atributos):
        self.nombre = nombre
        self.tipo = tipo               # tipo en minusculas (led, motor, sensor, ...)
        self.atributos = atributos     # dict con sus atributos (pin, pwm, in1, ...)
        self.estado = "apagado"
        self.ultimo_angulo = None

    def __repr__(self):
        return f"DispositivoSimulado({self.tipo} {self.nombre})"


# ---------------------------------------------------------------------------
# Interprete
# ---------------------------------------------------------------------------

class Interprete:
    """
    Uso:
        interp = Interprete(salida=print)
        interp.ejecutar(ast_raiz)
    """

    def __init__(self, salida=None, max_iteraciones=1000, semilla=42):
        # 'salida' es una funcion que recibe un texto (ej. la consola de la GUI).
        self.salida = salida if salida is not None else (lambda t: print(t))
        self.max_iteraciones = max_iteraciones

        self.dispositivos = {}     # nombre -> DispositivoSimulado
        self.funciones = {}        # nombre -> {nombre, parametros, cuerpo}
        self.ambitos = [{}]        # pila de ambitos (diccionarios)
        self.global_ambito = self.ambitos[0]

        self._iteraciones = 0
        self._rng = random.Random(semilla)

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def ejecutar(self, raiz):
        """Ejecuta el programa representado por el AST 'raiz'."""
        self.dispositivos = {}
        self.funciones = {}
        self.ambitos = [{}]
        self.global_ambito = self.ambitos[0]
        self._iteraciones = 0

        if raiz is None:
            self._emit("[ejecucion] no hay AST para ejecutar")
            return

        try:
            self._ejecutar_nodo(raiz)
        except LimiteIteraciones:
            self._emit(
                f"[ejecucion] se alcanzo el limite de {self.max_iteraciones} iteraciones "
                f"(posible bucle infinito). Ejecucion detenida de forma segura."
            )
        except SenalRomper:
            # 'romper' fuera de un bucle: lo ignoramos
            pass
        except ErrorEjecucion as e:
            self._emit(f"[ejecucion] error en tiempo de ejecucion: {e}")
        except Exception as e:  # red de seguridad
            self._emit(f"[ejecucion] error inesperado: {e}")

    # ------------------------------------------------------------------
    # Helpers de nodos
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

    def _emit(self, texto):
        self.salida(str(texto))

    # ------------------------------------------------------------------
    # Manejo de ambitos (scopes)
    # ------------------------------------------------------------------

    def _push(self):
        self.ambitos.append({})

    def _pop(self):
        if len(self.ambitos) > 1:
            self.ambitos.pop()

    def _declarar(self, nombre, valor):
        self.ambitos[-1][nombre] = valor

    def _asignar(self, nombre, valor):
        for amb in reversed(self.ambitos):
            if nombre in amb:
                amb[nombre] = valor
                return
        self.ambitos[-1][nombre] = valor

    def _obtener(self, nombre):
        for amb in reversed(self.ambitos):
            if nombre in amb:
                return amb[nombre]
        return None

    def _existe(self, nombre):
        return any(nombre in amb for amb in self.ambitos)

    # ------------------------------------------------------------------
    # Recorrido principal (sentencias)
    # ------------------------------------------------------------------

    def _ejecutar_nodo(self, nodo):
        if nodo is None:
            return None

        n = self._nl(nodo)

        if n == "programa":
            for h in self._h(nodo):
                if self._nl(h) in ("bloque", "bloque_incompleto"):
                    # el bloque del programa corre en el ambito global
                    self._ejecutar_bloque(h, nuevo_ambito=False)
                else:
                    self._ejecutar_nodo(h)
            return None

        if n in ("bloque", "bloque_incompleto"):
            return self._ejecutar_bloque(nodo)

        if n == "declaracion":
            return self._ejec_declaracion(nodo)
        if n == "declaracion_error":
            return None
        if n == "funcion":
            return None  # las funciones ya se registran (hoisting) en el bloque
        if n == "llamada_funcion":
            return self._ejec_llamada(nodo)
        if n == "imprimir":
            return self._ejec_imprimir(nodo)
        if n == "retraso":
            return self._ejec_retraso(nodo)
        if n == "si":
            return self._ejec_si(nodo)
        if n == "mientras":
            return self._ejec_mientras(nodo)
        if n == "para":
            return self._ejec_para(nodo)
        if n == "romper":
            raise SenalRomper()
        if n == "dispositivo":
            return self._ejec_dispositivo(nodo)
        if n == "accion_dispositivo":
            return self._ejec_accion(nodo)

        # cualquier otra cosa: intentar evaluarla como expresion
        return self._eval(nodo)

    def _ejecutar_bloque(self, nodo, nuevo_ambito=True):
        if nuevo_ambito:
            self._push()

        # 1) hoisting de funciones declaradas en este bloque
        for h in self._h(nodo):
            if self._nl(h) == "funcion":
                self._registrar_funcion(h)

        # 2) ejecucion del resto de sentencias en orden
        for h in self._h(nodo):
            if self._nl(h) == "funcion":
                continue
            self._ejecutar_nodo(h)

        if nuevo_ambito:
            self._pop()

    # ------------------------------------------------------------------
    # Declaraciones
    # ------------------------------------------------------------------

    def _ejec_declaracion(self, nodo):
        hijos = self._h(nodo)
        total = len(hijos)

        # tipo id ;
        if total == 3:
            tipo = self._nl(hijos[0])
            nombre = self._n(hijos[1])
            self._declarar(nombre, self._valor_por_defecto(tipo))
            return None

        # tipo id = expr ;
        if total == 5:
            nombre = self._n(hijos[1])
            valor = self._eval(hijos[3])
            self._declarar(nombre, valor)
            return None

        # tipo id [tam] ;
        if total == 6:
            nombre = self._n(hijos[1])
            tam = self._entero(self._n(hijos[3]), 0)
            self._declarar(nombre, [0] * max(tam, 0))
            return None

        # id [indice] = expr ;
        if total == 7:
            nombre = self._n(hijos[0])
            idx = self._entero(self._n(hijos[2]), 0)
            valor = self._eval(hijos[5])
            arr = self._obtener(nombre)
            if isinstance(arr, list) and 0 <= idx < len(arr):
                arr[idx] = valor
            else:
                self._emit(f"[ejecucion] no se pudo asignar {nombre}[{idx}] (indice o arreglo invalido)")
            return None

        return None

    @staticmethod
    def _valor_por_defecto(tipo):
        if tipo in ("entero",):
            return 0
        if tipo in ("real", "real_tipo"):
            return 0.0
        if tipo in ("booleano",):
            return False
        if tipo in ("cadena", "cadena_tipo"):
            return ""
        return 0

    # ------------------------------------------------------------------
    # imprimir / retraso
    # ------------------------------------------------------------------

    def _ejec_imprimir(self, nodo):
        hijos = self._h(nodo)
        valor = self._eval(hijos[0]) if hijos else ""
        self._emit(self._formatear(valor))

    def _ejec_retraso(self, nodo):
        hijos = self._h(nodo)
        valor = self._eval(hijos[0]) if hijos else 0
        self._emit(f"[retraso] esperar {self._formatear(valor)} ms")

    # ------------------------------------------------------------------
    # Control: si / mientras / para
    # ------------------------------------------------------------------

    def _ejec_si(self, nodo):
        hijos = self._h(nodo)
        condicion = bool(self._eval(hijos[0]))
        if condicion:
            self._ejecutar_bloque(hijos[1])
        elif len(hijos) >= 4:
            # hijos[2] es el nodo 'sino'
            self._ejecutar_bloque(hijos[3])

    def _ejec_mientras(self, nodo):
        hijos = self._h(nodo)
        condicion = hijos[0]
        cuerpo = hijos[1]
        while bool(self._eval(condicion)):
            self._tick()
            try:
                self._ejecutar_bloque(cuerpo)
            except SenalRomper:
                break

    def _ejec_para(self, nodo):
        hijos = self._h(nodo)
        self._push()  # ambito de la variable de control
        try:
            if len(hijos) >= 1:
                self._ejec_asignacion_para(hijos[0])
            while len(hijos) >= 2 and bool(self._eval(hijos[1])):
                self._tick()
                try:
                    if len(hijos) >= 4:
                        self._ejecutar_bloque(hijos[3])
                except SenalRomper:
                    break
                if len(hijos) >= 3:
                    self._ejec_actualizacion_para(hijos[2])
        finally:
            self._pop()

    def _ejec_asignacion_para(self, nodo):
        hijos = self._h(nodo)
        if len(hijos) == 4:        # tipo id = expr
            nombre = self._n(hijos[1])
            self._declarar(nombre, self._eval(hijos[3]))
        elif len(hijos) == 3:      # id = expr
            nombre = self._n(hijos[0])
            self._asignar(nombre, self._eval(hijos[2]))

    def _ejec_actualizacion_para(self, nodo):
        hijos = self._h(nodo)
        if len(hijos) == 2:        # id ++ / id --
            nombre = self._n(hijos[0])
            op = self._n(hijos[1])
            actual = self._obtener(nombre)
            if actual is None:
                actual = 0
            if op == "++":
                self._asignar(nombre, actual + 1)
            elif op == "--":
                self._asignar(nombre, actual - 1)
        elif len(hijos) == 3:      # id = expr
            nombre = self._n(hijos[0])
            self._asignar(nombre, self._eval(hijos[2]))

    def _tick(self):
        self._iteraciones += 1
        if self._iteraciones > self.max_iteraciones:
            raise LimiteIteraciones()

    # ------------------------------------------------------------------
    # Funciones
    # ------------------------------------------------------------------

    def _registrar_funcion(self, nodo):
        hijos = self._h(nodo)
        if len(hijos) < 3:
            return
        nombre = self._n(hijos[0])
        parametros = []
        for pnodo in self._h(hijos[1]):
            if self._nl(pnodo) == "parametro":
                ph = self._h(pnodo)
                if len(ph) == 2:
                    parametros.append({"tipo": self._nl(ph[0]), "nombre": self._n(ph[1])})
        self.funciones[nombre] = {"nombre": nombre, "parametros": parametros, "cuerpo": hijos[2]}

    def _ejec_llamada(self, nodo):
        hijos = self._h(nodo)
        if len(hijos) < 2:
            return None
        nombre = self._n(hijos[0])
        args_nodo = hijos[1]
        argumentos = [self._eval(a) for a in self._h(args_nodo)]
        return self._invocar(nombre, argumentos)

    def _invocar(self, nombre, argumentos):
        funcion = self.funciones.get(nombre)
        if funcion is None:
            self._emit(f"[ejecucion] la funcion '{nombre}' no esta definida")
            return None

        parametros = funcion["parametros"]
        cuerpo = funcion["cuerpo"]

        # Las funciones ven el ambito global + sus propios parametros
        stack_previo = self.ambitos
        self.ambitos = [self.global_ambito, {}]
        for i, p in enumerate(parametros):
            valor = argumentos[i] if i < len(argumentos) else None
            self.ambitos[-1][p["nombre"]] = valor

        try:
            self._ejecutar_bloque(cuerpo, nuevo_ambito=False)
        except SenalRomper:
            pass
        finally:
            self.ambitos = stack_previo
        return None

    # ------------------------------------------------------------------
    # Dispositivos
    # ------------------------------------------------------------------

    def _ejec_dispositivo(self, nodo):
        hijos = self._h(nodo)
        if len(hijos) < 3:
            return None
        tipo = self._nl(hijos[0])
        nombre = self._n(hijos[1])
        atributos_nodo = hijos[2]

        atributos = {}
        for atr in self._h(atributos_nodo):
            if self._nl(atr) == "atributo":
                ah = self._h(atr)
                if len(ah) == 2:
                    clave = self._n(ah[0])
                    valor = self._eval(ah[1])
                    atributos[clave] = valor

        self.dispositivos[nombre] = DispositivoSimulado(nombre, tipo, atributos)
        detalle = ", ".join(f"{k}={self._formatear(v)}" for k, v in atributos.items())
        self._emit(f"[dispositivo] {tipo} '{nombre}' creado ({detalle})")
        return None

    def _ejec_accion(self, nodo):
        hijos = self._h(nodo)
        if len(hijos) < 3:
            return None
        nombre = self._n(hijos[0])
        accion = self._nl(hijos[1])
        arg_nodo = hijos[2]

        disp = self.dispositivos.get(nombre)
        argumento = None if self._nl(arg_nodo) == "vacio" else self._eval(arg_nodo)
        etiqueta = nombre if disp is None else f"{disp.tipo} {nombre}"

        if disp is None:
            self._emit(f"[ejecucion] aviso: dispositivo '{nombre}' no declarado; se simula de todos modos")

        if accion == "encender":
            if disp:
                disp.estado = "encendido"
            self._emit(f"[{etiqueta}] encender()")
        elif accion == "apagar":
            if disp:
                disp.estado = "apagado"
            self._emit(f"[{etiqueta}] apagar()")
        elif accion == "girarservo":
            if disp:
                disp.ultimo_angulo = argumento
            self._emit(f"[{etiqueta}] girarServo({self._formatear(argumento)})")
        elif accion == "girarmotor":
            if disp:
                disp.ultimo_angulo = argumento
            self._emit(f"[{etiqueta}] girarMotor({self._formatear(argumento)})")
        elif accion == "valor":
            lectura = self._simular_lectura(disp)
            self._emit(f"[{etiqueta}] valor() -> {lectura}")
            return lectura
        else:
            self._emit(f"[{etiqueta}] {accion}({self._formatear(argumento) if argumento is not None else ''})")
        return None

    def _simular_lectura(self, disp):
        if disp is None:
            return self._rng.randint(0, 1023)
        tipo = disp.tipo
        if tipo == "sensor_color":
            return self._rng.randint(0, 7)
        if tipo == "sensor_toque":
            return self._rng.randint(0, 1)
        if tipo == "sensor_giro":
            return self._rng.randint(-180, 180)
        # sensor, sensor_ultrasonico, hubs, etc.
        return self._rng.randint(0, 1023)

    # ------------------------------------------------------------------
    # Evaluacion de expresiones (devuelven valores de Python)
    # ------------------------------------------------------------------

    def _eval(self, nodo):
        if nodo is None:
            return None
        n = self._nl(nodo)

        if n == "constante":
            return self._eval_constante(nodo)
        if n == "arreglo":
            return self._eval_arreglo(nodo)
        if n == "binop":
            return self._eval_binop(nodo)
        if n == "unop":
            return self._eval_unop(nodo)
        if n == "valor_dispositivo":
            return self._eval_valor_dispositivo(nodo)
        if n == "llamada_funcion":
            return self._ejec_llamada(nodo)
        if n == "vacio":
            return None
        return None

    def _eval_constante(self, nodo):
        hijos = self._h(nodo)
        if not hijos:
            return None
        return self._interpretar_literal(self._n(hijos[0]))

    def _interpretar_literal(self, texto):
        if re.fullmatch(r"-?\d+", texto):
            return int(texto)
        if re.fullmatch(r"-?\d+\.\d+", texto):
            return float(texto)
        tl = texto.lower()
        if tl == "true":
            return True
        if tl == "false":
            return False
        # identificador (variable)
        if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", texto):
            if self._existe(texto):
                return self._obtener(texto)
            self._emit(f"[ejecucion] aviso: '{texto}' sin valor asignado; se usa 0")
            return 0
        # literal de cadena
        return texto

    def _eval_arreglo(self, nodo):
        hijos = self._h(nodo)
        nombre = self._n(hijos[0])
        idx = self._entero(self._n(hijos[1]), 0)
        arr = self._obtener(nombre)
        if isinstance(arr, list) and 0 <= idx < len(arr):
            return arr[idx]
        self._emit(f"[ejecucion] aviso: acceso invalido a {nombre}[{idx}]")
        return 0

    def _eval_binop(self, nodo):
        hijos = self._h(nodo)
        izq = self._eval(hijos[0])
        op = self._n(hijos[1])
        der = self._eval(hijos[2])
        try:
            if op == "+":
                if isinstance(izq, str) or isinstance(der, str):
                    return f"{self._formatear(izq)}{self._formatear(der)}"
                return izq + der
            if op == "-":
                return izq - der
            if op == "*":
                return izq * der
            if op == "/":
                if der == 0:
                    self._emit("[ejecucion] aviso: division entre cero; se usa 0")
                    return 0
                if isinstance(izq, int) and isinstance(der, int):
                    return int(izq / der)  # division entera (trunca hacia cero)
                return izq / der
            if op == "%":
                if der == 0:
                    self._emit("[ejecucion] aviso: modulo entre cero; se usa 0")
                    return 0
                return izq % der
            if op == "==":
                return izq == der
            if op == "!=":
                return izq != der
            if op == "<":
                return izq < der
            if op == ">":
                return izq > der
            if op == "<=":
                return izq <= der
            if op == ">=":
                return izq >= der
            if op == "&&":
                return bool(izq) and bool(der)
            if op == "||":
                return bool(izq) or bool(der)
        except Exception as e:
            self._emit(f"[ejecucion] aviso: operacion invalida '{op}': {e}")
            return 0
        return 0

    def _eval_unop(self, nodo):
        hijos = self._h(nodo)
        op = self._n(hijos[0])
        valor = self._eval(hijos[1])
        if op == "!":
            return not bool(valor)
        if op == "-":
            try:
                return -valor
            except Exception:
                return 0
        return valor

    def _eval_valor_dispositivo(self, nodo):
        hijos = self._h(nodo)
        nombre = self._n(hijos[0])
        disp = self.dispositivos.get(nombre)
        lectura = self._simular_lectura(disp)
        etiqueta = nombre if disp is None else f"{disp.tipo} {nombre}"
        self._emit(f"[{etiqueta}] valor() -> {lectura}")
        return lectura

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @staticmethod
    def _formatear(valor):
        if isinstance(valor, bool):
            return "true" if valor else "false"
        if valor is None:
            return ""
        return str(valor)

    @staticmethod
    def _entero(texto, por_defecto=0):
        try:
            return int(texto)
        except Exception:
            return por_defecto


# Instancia de conveniencia (compatibilidad con el estilo del proyecto)
interprete = Interprete
