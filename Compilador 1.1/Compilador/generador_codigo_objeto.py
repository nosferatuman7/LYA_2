# -*- coding: utf-8 -*-
"""
generador_codigo_objeto.py
==========================
GENERACION DE CODIGO OBJETO (Unidad IV).

Recorre el AST y traduce el programa fuente a CODIGO OBJETO: un sketch de
Arduino (archivo .ino) listo para compilarse a .hex y cargarse en la
plataforma destino (Arduino Uno / Nano / Mega, etc.).

El metodo generar() devuelve el codigo fuente del sketch (.ino) como cadena.
El metodo compilar_hex() escribe el .ino en disco, llama a arduino-cli y
devuelve la ruta del .hex resultante (o lanza RuntimeError si falla).

Correspondencia principal lenguaje fuente -> codigo objeto (Arduino C++):
    entero/real/booleano/cadena   -> int / float / bool / String
    arreglos  tipo id[n];         -> tipo id[n];
    si / sino                     -> if / else
    mientras                      -> while
    para                          -> for
    funcion id(params) { ... }    -> tipo id(tipo params) { ... }
    imprimir(x);                  -> Serial.println(x)
    retraso(ms);                  -> delay(ms)
    dispositivo id = { ... };     -> declaracion de pin + setup
    id->encender();               -> digitalWrite(id_pin, HIGH)
    id->apagar();                 -> digitalWrite(id_pin, LOW)
    id->girarServo(grados);       -> id_servo.write(grados)
    id->girarMotor(vel);          -> analogWrite(id_pin, vel)
    id->valor()                   -> digitalRead(id_pin) / analogRead(id_pin)
"""

import os
import re
import shutil
import subprocess
import tempfile


class GeneradorCodigoObjeto:
    """
    Uso basico:
        gen = GeneradorCodigoObjeto()
        sketch = gen.generar(ast_raiz)          # -> str (.ino)
        hex_path = gen.compilar_hex(ast_raiz)   # -> str (ruta del .hex)

    compilar_hex() requiere arduino-cli instalado y en el PATH.
    Placa por defecto: arduino:avr:uno
    Cambiala con:  gen.fqbn = "arduino:avr:mega"
    """

    INDENT = "    "
    fqbn  = "arduino:avr:uno"   # Fully Qualified Board Name por defecto

    # tipo del lenguaje fuente -> tipo C++ de Arduino
    TIPOS_CPP = {
        "entero":   "int",
        "real":     "float",
        "booleano": "bool",
        "cadena":   "String",
    }

    # tipo de dispositivo del lenguaje -> categoria interna
    CATEGORIA_DISPOSITIVO = {
        "led":                "salida_digital",
        "buzzer":             "salida_digital",
        "motor":              "salida_pwm",
        "servo":              "servo",
        "sensor":             "entrada_digital",
        "sensor_ultrasonico": "entrada_analogica",
        "sensor_color":       "entrada_analogica",
        "sensor_toque":       "entrada_digital",
        "sensor_giro":        "entrada_analogica",
    }

    def __init__(self):
        self.lineas_globales   = []
        self.lineas_setup      = []
        self.lineas_loop       = []
        self.lineas_funciones  = []
        self.nivel = 0
        self._destino     = None
        self._dispositivos = {}
        self._usa_servo   = False

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def generar(self, raiz):
        """Devuelve el sketch Arduino (.ino) como cadena de texto."""
        self._reset()
        bloque = self._bloque_programa(raiz)

        # Primera pasada: registrar dispositivos (necesario para setup)
        if bloque is not None:
            for hijo in self._h(bloque):
                if self._nl(hijo) == "dispositivo":
                    self._registrar_dispositivo(hijo)

        # Segunda pasada: generar codigo
        self._destino = "loop"
        if bloque is not None:
            for hijo in self._h(bloque):
                self._gen_sentencia(hijo)

        return self._ensamblar()

    def compilar_hex(self, raiz, ruta_salida=None):
        """
        Genera el sketch, lo compila con arduino-cli y devuelve la ruta
        del archivo .hex resultante.

        Parametros:
            raiz        -- nodo raiz del AST
            ruta_salida -- carpeta donde copiar el .hex final
                           (por defecto: directorio de trabajo actual)

        Lanza:
            FileNotFoundError  si arduino-cli no esta en el PATH
            RuntimeError       si la compilacion falla
        """
        # Verificar que arduino-cli existe
        if shutil.which("arduino-cli") is None:
            raise FileNotFoundError(
                "arduino-cli no esta instalado o no esta en el PATH.\n"
                "Descargalo en: https://arduino.github.io/arduino-cli/"
            )

        sketch_codigo = self.generar(raiz)

        # Crear carpeta temporal con el nombre del sketch
        tmp_dir   = tempfile.mkdtemp(prefix="sketch_arduino_")
        sketch_dir = os.path.join(tmp_dir, "sketch")
        os.makedirs(sketch_dir, exist_ok=True)
        ino_path  = os.path.join(sketch_dir, "sketch.ino")
        out_dir   = os.path.join(tmp_dir, "out")
        os.makedirs(out_dir, exist_ok=True)

        # Escribir el .ino
        with open(ino_path, "w", encoding="utf-8") as f:
            f.write(sketch_codigo)

        # Llamar a arduino-cli
        cmd = [
            "arduino-cli", "compile",
            "--fqbn", self.fqbn,
            sketch_dir,
            "--output-dir", out_dir,
        ]
        resultado = subprocess.run(cmd, capture_output=True, text=True)

        if resultado.returncode != 0:
            raise RuntimeError(
                "Error al compilar el sketch con arduino-cli:\n"
                + resultado.stderr
            )

        # Buscar el .hex generado
        hex_generado = None
        for archivo in os.listdir(out_dir):
            if archivo.endswith(".hex"):
                hex_generado = os.path.join(out_dir, archivo)
                break

        if hex_generado is None:
            raise RuntimeError(
                "arduino-cli termino sin error pero no genero ningun .hex en: "
                + out_dir
            )

        # Copiar a la carpeta de salida deseada
        if ruta_salida is None:
            ruta_salida = os.getcwd()
        os.makedirs(ruta_salida, exist_ok=True)
        destino = os.path.join(ruta_salida, "codigo_objeto.hex")
        shutil.copy2(hex_generado, destino)

        # Limpiar temporales
        shutil.rmtree(tmp_dir, ignore_errors=True)

        return destino

    # ------------------------------------------------------------------
    # Reset interno
    # ------------------------------------------------------------------

    def _reset(self):
        self.lineas_globales  = []
        self.lineas_setup     = []
        self.lineas_loop      = []
        self.lineas_funciones = []
        self.nivel = 0
        self._dispositivos = {}
        self._usa_servo = False

    # ------------------------------------------------------------------
    # Ensamblado final del sketch .ino
    # ------------------------------------------------------------------

    def _ensamblar(self):
        lineas = []

        lineas += [
            "// ==========================================================================",
            "//  CODIGO OBJETO GENERADO AUTOMATICAMENTE",
            "//  Destino: Arduino (sketch .ino -> compilar a .hex con avr-gcc / IDE)",
            "//",
            "//  Para compilar directamente a .hex desde Python:",
            "//    gen = GeneradorCodigoObjeto()",
            "//    ruta_hex = gen.compilar_hex(ast)   # requiere arduino-cli en PATH",
            "//",
            "//  O con arduino-cli manualmente:",
            "//    arduino-cli compile --fqbn arduino:avr:uno sketch/ --output-dir out/",
            "// ==========================================================================",
            "",
        ]

        if self._usa_servo:
            lineas.append("#include <Servo.h>")
            lineas.append("")

        for nombre, info in self._dispositivos.items():
            if info["categoria"] == "servo":
                lineas.append(f"Servo {nombre}_servo;")
        if self._usa_servo:
            lineas.append("")

        if self.lineas_globales:
            lineas += self.lineas_globales
            lineas.append("")

        if self.lineas_funciones:
            lineas += self.lineas_funciones
            lineas.append("")

        lineas.append("void setup() {")
        lineas.append(self.INDENT + "Serial.begin(9600);")
        for nombre, info in self._dispositivos.items():
            cat = info["categoria"]
            pin = info.get("pin", "")
            if pin == "":
                continue
            if cat in ("salida_digital", "salida_pwm"):
                lineas.append(f"{self.INDENT}pinMode({pin}, OUTPUT);")
            elif cat in ("entrada_digital", "entrada_analogica"):
                lineas.append(f"{self.INDENT}pinMode({pin}, INPUT);")
            elif cat == "servo":
                lineas.append(f"{self.INDENT}{nombre}_servo.attach({pin});")
        for ln in self.lineas_setup:
            lineas.append(self.INDENT + ln)
        lineas.append("}")
        lineas.append("")

        lineas.append("void loop() {")
        for ln in self.lineas_loop:
            lineas.append(ln)
        lineas.append("}")
        lineas.append("")

        return "\n".join(lineas)

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
        sangria = self.INDENT * self.nivel
        linea   = (sangria + texto) if texto else ""
        if self._destino == "globales":
            self.lineas_globales.append(linea)
        elif self._destino == "setup":
            self.lineas_setup.append(linea)
        elif self._destino == "funcion":
            self.lineas_funciones.append(linea)
        else:
            self.lineas_loop.append(linea)

    def _bloque_programa(self, raiz):
        if raiz is None:
            return None
        if self._nl(raiz) == "programa":
            hijos = self._h(raiz)
            return hijos[0] if hijos else None
        return raiz

    # ------------------------------------------------------------------
    # Primera pasada: registro de dispositivos
    # ------------------------------------------------------------------

    def _registrar_dispositivo(self, nodo):
        hijos = self._h(nodo)
        tipo   = self._nl(hijos[0])
        nombre = self._n(hijos[1])
        atributos = hijos[2]
        info = {
            "categoria": self.CATEGORIA_DISPOSITIVO.get(tipo, "salida_digital"),
            "pin": "", "in1": "", "in2": "", "trigger": "", "echo": "",
        }
        for atr in self._h(atributos):
            if self._nl(atr) == "atributo":
                ah = self._h(atr)
                if len(ah) == 2:
                    info[self._n(ah[0]).lower()] = self._expr(ah[1])
        if tipo == "servo":
            self._usa_servo = True
        self._dispositivos[nombre] = info

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
            prev, self.nivel, self._destino = self._destino, 0, "funcion"
            self._g_funcion(nodo)
            self._destino = prev
        elif n == "llamada_funcion":
            self._l(self._expr_llamada(nodo) + ";")
        elif n == "imprimir":
            hijos = self._h(nodo)
            arg = self._expr(hijos[0]) if hijos else '""'
            self._l(f"Serial.println({arg});")
        elif n == "retraso":
            hijos = self._h(nodo)
            arg = self._expr(hijos[0]) if hijos else "0"
            self._l(f"delay({arg});")
        elif n == "si":
            self._g_si(nodo)
        elif n == "mientras":
            self._g_mientras(nodo)
        elif n == "para":
            self._g_para(nodo)
        elif n == "romper":
            self._l("break;")
        elif n == "dispositivo":
            self._g_dispositivo(nodo)
        elif n == "accion_dispositivo":
            self._l(self._g_accion(nodo) + ";")
        elif n in ("bloque", "bloque_incompleto"):
            for h in self._h(nodo):
                self._gen_sentencia(h)

    def _g_cuerpo(self, bloque):
        hijos = self._h(bloque)
        self.nivel += 1
        if hijos:
            for h in hijos:
                self._gen_sentencia(h)
        else:
            self._l("; // vacio")
        self.nivel -= 1

    def _g_declaracion(self, nodo):
        hijos = self._h(nodo)
        total = len(hijos)
        if total == 3:
            tipo, nombre = self._nl(hijos[0]), self._n(hijos[1])
            self._l(f"{self.TIPOS_CPP.get(tipo,'int')} {nombre} = {self._defecto_cpp(tipo)};")
        elif total == 5:
            tipo, nombre = self._nl(hijos[0]), self._n(hijos[1])
            self._l(f"{self.TIPOS_CPP.get(tipo,'int')} {nombre} = {self._expr(hijos[3])};")
        elif total == 6:
            tipo, nombre, tam = self._nl(hijos[0]), self._n(hijos[1]), self._n(hijos[3])
            self._l(f"{self.TIPOS_CPP.get(tipo,'int')} {nombre}[{tam}] = {{0}};")
        elif total == 7:
            self._l(f"{self._n(hijos[0])}[{self._n(hijos[2])}] = {self._expr(hijos[5])};")
        elif total >= 3:
            self._l(f"{self._n(hijos[0])} = {self._expr(hijos[total-2])};")

    @staticmethod
    def _defecto_cpp(tipo):
        return {"entero": "0", "real": "0.0", "booleano": "false", "cadena": '""'}.get(tipo, "0")

    def _g_funcion(self, nodo):
        hijos = self._h(nodo)
        nombre = self._n(hijos[0])
        params = []
        for p in self._h(hijos[1]):
            if self._nl(p) == "parametro":
                ph = self._h(p)
                if len(ph) == 2:
                    params.append(f"{self.TIPOS_CPP.get(self._nl(ph[0]),'int')} {self._n(ph[1])}")
        self._l("")
        self._l(f"void {nombre}({', '.join(params)}) {{")
        self._g_cuerpo(hijos[2])
        self._l("}")
        self._l("")

    def _g_si(self, nodo):
        hijos = self._h(nodo)
        self._l(f"if ({self._cond(hijos[0])}) {{")
        self._g_cuerpo(hijos[1])
        if len(hijos) >= 4:
            self._l("} else {")
            self._g_cuerpo(hijos[3])
        self._l("}")

    def _g_mientras(self, nodo):
        hijos = self._h(nodo)
        self._l(f"while ({self._cond(hijos[0])}) {{")
        self._g_cuerpo(hijos[1])
        self._l("}")

    def _g_para(self, nodo):
        hijos = self._h(nodo)
        init = self._init_para(hijos[0]) if len(hijos) >= 1 else ""
        cond = self._cond(hijos[1])      if len(hijos) >= 2 else "true"
        upd  = self._upd_para(hijos[2])  if len(hijos) >= 3 else ""
        self._l(f"for ({init}; {cond}; {upd}) {{")
        if len(hijos) >= 4:
            self._g_cuerpo(hijos[3])
        self._l("}")

    def _init_para(self, nodo):
        hijos = self._h(nodo)
        if len(hijos) == 4:
            return f"{self.TIPOS_CPP.get(self._nl(hijos[0]),'int')} {self._n(hijos[1])} = {self._expr(hijos[3])}"
        elif len(hijos) == 3:
            return f"{self._n(hijos[0])} = {self._expr(hijos[2])}"
        return ""

    def _upd_para(self, nodo):
        hijos = self._h(nodo)
        if len(hijos) == 2:
            op = self._n(hijos[1])
            return f"{self._n(hijos[0])}{'++' if op=='++' else '--'}"
        elif len(hijos) == 3:
            return f"{self._n(hijos[0])} = {self._expr(hijos[2])}"
        return ""

    def _g_dispositivo(self, nodo):
        hijos  = self._h(nodo)
        tipo   = self._nl(hijos[0])
        nombre = self._n(hijos[1])
        pin    = self._dispositivos.get(nombre, {}).get("pin", "?")
        self._l(f"// dispositivo {tipo} '{nombre}' -> pin {pin} (configurado en setup)")

    def _g_accion(self, nodo):
        hijos    = self._h(nodo)
        nombre   = self._n(hijos[0])
        accion   = self._nl(hijos[1])
        arg_nodo = hijos[2]
        info     = self._dispositivos.get(nombre, {})
        cat      = info.get("categoria", "salida_digital")
        pin      = info.get("pin", "0")

        if accion == "encender":
            return f"analogWrite({pin}, 255)" if cat == "salida_pwm" else f"digitalWrite({pin}, HIGH)"
        if accion == "apagar":
            return f"analogWrite({pin}, 0)"   if cat == "salida_pwm" else f"digitalWrite({pin}, LOW)"
        if accion == "girarservo":
            arg = self._expr(arg_nodo) if self._nl(arg_nodo) != "vacio" else "90"
            return f"{nombre}_servo.write({arg})"
        if accion == "girarmotor":
            arg = self._expr(arg_nodo) if self._nl(arg_nodo) != "vacio" else "0"
            return f"analogWrite({pin}, {arg})"
        if accion == "valor":
            return f"analogRead({pin})" if cat == "entrada_analogica" else f"digitalRead({pin})"
        arg = self._expr(arg_nodo) if self._nl(arg_nodo) != "vacio" else ""
        return f"/* accion desconocida: {nombre}.{accion}({arg}) */"

    # ------------------------------------------------------------------
    # Expresiones
    # ------------------------------------------------------------------

    def _cond(self, nodo):
        return self._expr(nodo)

    def _expr(self, nodo):
        if nodo is None:
            return "0"
        n = self._nl(nodo)
        if n == "constante":
            return self._expr_constante(nodo)
        if n == "arreglo":
            hijos = self._h(nodo)
            return f"{self._n(hijos[0])}[{self._n(hijos[1])}]"
        if n == "binop":
            hijos = self._h(nodo)
            return f"({self._expr(hijos[0])} {self._op(self._n(hijos[1]))} {self._expr(hijos[2])})"
        if n == "unop":
            hijos = self._h(nodo)
            op = self._n(hijos[0])
            val = self._expr(hijos[1])
            return f"(!{val})" if op == "!" else f"(-{val})"
        if n == "valor_dispositivo":
            hijos  = self._h(nodo)
            nombre = self._n(hijos[0])
            info   = self._dispositivos.get(nombre, {})
            pin    = info.get("pin", "0")
            return f"analogRead({pin})" if info.get("categoria") == "entrada_analogica" else f"digitalRead({pin})"
        if n == "llamada_funcion":
            return self._expr_llamada(nodo)
        if n == "vacio":
            return ""
        return self._n(nodo)

    @staticmethod
    def _op(op):
        return {"&&": "&&", "||": "||"}.get(op, op)

    def _expr_constante(self, nodo):
        hijos = self._h(nodo)
        if not hijos:
            return "0"
        texto = self._n(hijos[0])
        if re.fullmatch(r"-?\d+", texto):       return texto
        if re.fullmatch(r"-?\d+\.\d+", texto):  return texto
        if texto.lower() == "true":             return "true"
        if texto.lower() == "false":            return "false"
        if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", texto): return texto
        return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _expr_llamada(self, nodo):
        hijos  = self._h(nodo)
        nombre = self._n(hijos[0])
        args   = self._h(hijos[1]) if len(hijos) > 1 else []
        return f"{nombre}({', '.join(self._expr(a) for a in args)})"


# Compatibilidad con el estilo del proyecto
generador_codigo_objeto = GeneradorCodigoObjeto
