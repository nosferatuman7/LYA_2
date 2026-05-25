# -*- coding: utf-8 -*-
"""
optimizador_codigo_intermedio.py
================================
OPTIMIZACION DE CODIGO (Unidad IV).

Recibe la lista de instrucciones de codigo intermedio (TAC) producida por
'generador_codigo_intermedio.py' y devuelve una version optimizada, aplicando
tecnicas clasicas de optimizacion local (peephole):

  1. Plegado de constantes (constant folding):
        t1 = 2 + 3     ->   t1 = 5
  2. Simplificacion algebraica:
        x = y + 0      ->   x = y
        x = y * 1      ->   x = y
        x = y * 0      ->   x = 0
        x = y / 1      ->   x = y
  3. Eliminacion de copias redundantes:
        x = x          ->   (se elimina)
  4. Eliminacion de instrucciones duplicadas consecutivas:
        (misma op, arg1, arg2 y resultado seguidas) -> se conserva solo una

El optimizador guarda en 'self.reporte' una lista con las optimizaciones
aplicadas, para poder mostrarlas en la interfaz.
"""

import re

from generador_codigo_intermedio import Instruccion


# Expresion del tipo  "NUMERO op NUMERO"  (para plegado de constantes)
_PAT_CONST = re.compile(r'^\s*(-?\d+(?:\.\d+)?)\s*([+\-*/%])\s*(-?\d+(?:\.\d+)?)\s*$')

# Expresion del tipo  "operando op operando"  (para simplificacion algebraica)
_PAT_BINARIA = re.compile(r'^\s*(\S+)\s*([+\-*/])\s*(\S+)\s*$')


class OptimizadorCodigoIntermedio:
    """
    Uso:
        opt = OptimizadorCodigoIntermedio()
        instrucciones_opt = opt.optimizar(generador.obtener_instrucciones())
        texto = opt.formatear(instrucciones_opt)
        for r in opt.reporte: print(r)
    """

    def __init__(self):
        self.reporte = []

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def optimizar(self, instrucciones):
        self.reporte = []
        paso = self._plegado_y_simplificacion(instrucciones)
        paso = self._eliminar_copias_redundantes(paso)
        paso = self._eliminar_duplicados_consecutivos(paso)
        if not self.reporte:
            self.reporte.append("(no se encontraron optimizaciones aplicables)")
        return paso

    def formatear(self, instrucciones):
        lineas = []
        for i, ins in enumerate(instrucciones):
            lineas.append(f"{i + 1:>3}.  {str(ins).lstrip()}")
        return "\n".join(lineas)

    # ------------------------------------------------------------------
    # 1 y 2: plegado de constantes + simplificacion algebraica
    # ------------------------------------------------------------------

    def _plegado_y_simplificacion(self, instrucciones):
        resultado = []
        for ins in instrucciones:
            if ins.op == "COPY" and isinstance(ins.arg1, str):
                expr = ins.arg1

                # plegado de constantes
                folded = self._plegar(expr)
                if folded is not None and folded != expr:
                    self.reporte.append(
                        f"plegado de constantes: '{ins.resultado} = {expr}' -> "
                        f"'{ins.resultado} = {folded}'"
                    )
                    resultado.append(Instruccion("COPY", arg1=folded, resultado=ins.resultado))
                    continue

                # simplificacion algebraica
                simpl = self._simplificar(expr)
                if simpl is not None and simpl != expr:
                    self.reporte.append(
                        f"simplificacion algebraica: '{ins.resultado} = {expr}' -> "
                        f"'{ins.resultado} = {simpl}'"
                    )
                    resultado.append(Instruccion("COPY", arg1=simpl, resultado=ins.resultado))
                    continue

            resultado.append(ins)
        return resultado

    def _plegar(self, expr):
        m = _PAT_CONST.match(expr)
        if not m:
            return None
        a_txt, op, b_txt = m.group(1), m.group(2), m.group(3)
        try:
            a = float(a_txt) if "." in a_txt else int(a_txt)
            b = float(b_txt) if "." in b_txt else int(b_txt)
            if op == "+":
                r = a + b
            elif op == "-":
                r = a - b
            elif op == "*":
                r = a * b
            elif op == "/":
                if b == 0:
                    return None
                r = a / b if (isinstance(a, float) or isinstance(b, float)) else int(a / b)
            elif op == "%":
                if b == 0:
                    return None
                r = a % b
            else:
                return None
            if isinstance(r, float) and r.is_integer() and "." not in a_txt and "." not in b_txt:
                r = int(r)
            return str(r)
        except Exception:
            return None

    def _simplificar(self, expr):
        if _PAT_CONST.match(expr):
            return None  # eso lo maneja el plegado
        m = _PAT_BINARIA.match(expr)
        if not m:
            return None
        a, op, b = m.group(1), m.group(2), m.group(3)
        if op == "+":
            if b == "0":
                return a
            if a == "0":
                return b
        elif op == "-":
            if b == "0":
                return a
        elif op == "*":
            if a == "0" or b == "0":
                return "0"
            if b == "1":
                return a
            if a == "1":
                return b
        elif op == "/":
            if b == "1":
                return a
        return None

    # ------------------------------------------------------------------
    # 3: eliminacion de copias redundantes (x = x)
    # ------------------------------------------------------------------

    def _eliminar_copias_redundantes(self, instrucciones):
        resultado = []
        for ins in instrucciones:
            if ins.op == "COPY" and ins.arg1 is not None and ins.resultado is not None \
                    and str(ins.arg1).strip() == str(ins.resultado).strip():
                self.reporte.append(f"copia redundante eliminada: '{ins.resultado} = {ins.arg1}'")
                continue
            resultado.append(ins)
        return resultado

    # ------------------------------------------------------------------
    # 4: eliminacion de instrucciones duplicadas consecutivas
    # ------------------------------------------------------------------

    def _eliminar_duplicados_consecutivos(self, instrucciones):
        # Solo se eliminan COPY duplicadas consecutivas (son idempotentes).
        # Las instrucciones con efectos (PRINT, DELAY, PARAM, CALL, DEV_ACTION,
        # RETURN, etc.) NUNCA se eliminan aunque se repitan, para no cambiar la
        # semantica del programa.
        resultado = []
        anterior = None
        for ins in instrucciones:
            clave = (ins.op, str(ins.arg1), str(ins.arg2), str(ins.resultado))
            if ins.op == "COPY" and clave == anterior:
                self.reporte.append(f"instruccion duplicada eliminada: '{str(ins).strip()}'")
                continue
            resultado.append(ins)
            anterior = clave
        return resultado


# Compatibilidad con el estilo del proyecto
optimizador_codigo_intermedio = OptimizadorCodigoIntermedio
