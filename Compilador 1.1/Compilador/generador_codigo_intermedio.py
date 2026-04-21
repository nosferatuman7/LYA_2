"""
generador_codigo_intermedio.py
==============================
Genera Código Intermedio en formato TAC (Three Address Code / Código de Tres Direcciones)
a partir del AST producido por el analizador sintáctico.

Conceptos implementados (según la clase de Generación de Código Intermedio):
  - Instrucción de copia:          x = y
  - Asignación con operación:      x = y op z
  - Salto condicional:             if x relop y goto L
  - Salto incondicional:           goto L
  - Llamada a función:             call f, n   /   param x
  - Retorno:                       return x
  - Etiquetas:                     L:
  - Acciones de dispositivo:       x = dispositivo->accion(arg)
"""


class Instruccion:
    """Representa una instrucción TAC."""

    def __init__(self, op, arg1=None, arg2=None, resultado=None):
        self.op = op            # operación o tipo de instrucción
        self.arg1 = arg1        # primer operando
        self.arg2 = arg2        # segundo operando (opcional)
        self.resultado = resultado  # destino / etiqueta

    def __str__(self):
        op = self.op

        # etiqueta
        if op == "LABEL":
            return f"{self.resultado}:"

        # salto incondicional
        if op == "GOTO":
            return f"    goto {self.resultado}"

        # salto condicional:  if arg1 relop arg2 goto L
        if op == "IF":
            return f"    if {self.arg1} {self.arg2} goto {self.resultado}"

        # instrucción de copia:  resultado = arg1
        if op == "COPY":
            return f"    {self.resultado} = {self.arg1}"

        # operación binaria:  resultado = arg1 op arg2
        if op == "BINOP":
            return f"    {self.resultado} = {self.arg1} {self.arg2} {self.resultado.split('_')[0] if False else ''}"

        # asignación binaria:  resultado = arg1 op arg2
        if op == "ASSIGN":
            return f"    {self.resultado} = {self.arg1} {self.arg2} {self.resultado}"

        # op_binaria simplificada
        if op == "OP":
            return f"    {self.resultado} = {self.arg1} {self.arg2} {self.resultado}"

        # param para llamada a función
        if op == "PARAM":
            return f"    param {self.arg1}"

        # llamada a función
        if op == "CALL":
            if self.resultado:
                return f"    {self.resultado} = call {self.arg1}, {self.arg2}"
            return f"    call {self.arg1}, {self.arg2}"

        # return
        if op == "RETURN":
            if self.arg1 is not None:
                return f"    return {self.arg1}"
            return "    return"

        # imprimir
        if op == "PRINT":
            return f"    print {self.arg1}"

        # retraso
        if op == "DELAY":
            return f"    delay {self.arg1}"

        # acción de dispositivo
        if op == "DEV_ACTION":
            if self.resultado:
                return f"    {self.resultado} = {self.arg1}->{self.arg2}"
            return f"    {self.arg1}->{self.arg2}"

        # declaración de dispositivo
        if op == "DEV_DECL":
            return f"    {self.resultado} = new {self.arg1}({self.arg2})"

        # fin de programa
        if op == "HALT":
            return "    halt"

        # fallback genérico
        partes = [f"    {op}"]
        if self.arg1 is not None:
            partes.append(str(self.arg1))
        if self.arg2 is not None:
            partes.append(str(self.arg2))
        if self.resultado is not None:
            partes.append(f"-> {self.resultado}")
        return " ".join(partes)


class GeneradorCodigoIntermedio:
    """
    Recorre el AST y emite instrucciones TAC.

    Uso:
        gen = GeneradorCodigoIntermedio()
        instrucciones = gen.generar(ast_raiz)
        codigo = gen.obtener_codigo()   # str listo para imprimir
    """

    def __init__(self):
        self._instrucciones: list[Instruccion] = []
        self._temp_contador = 0
        self._etiqueta_contador = 0

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def generar(self, raiz):
        """Genera el TAC a partir del nodo raíz del AST."""
        self._instrucciones = []
        self._temp_contador = 0
        self._etiqueta_contador = 0

        if raiz is None:
            return self._instrucciones

        self._visitar(raiz)
        self._emitir(Instruccion("HALT"))
        return self._instrucciones

    def obtener_codigo(self) -> str:
        """Devuelve el código intermedio como texto formateado."""
        lineas = []
        for i, ins in enumerate(self._instrucciones):
            lineas.append(f"{i+1:>3}.  {str(ins).lstrip()}")
        return "\n".join(lineas)

    def obtener_instrucciones(self):
        return list(self._instrucciones)

    # ------------------------------------------------------------------
    # Generadores de temporales y etiquetas
    # ------------------------------------------------------------------

    def _nuevo_temp(self) -> str:
        self._temp_contador += 1
        return f"t{self._temp_contador}"

    def _nueva_etiqueta(self, prefijo="L") -> str:
        self._etiqueta_contador += 1
        return f"{prefijo}{self._etiqueta_contador}"

    def _emitir(self, ins: Instruccion):
        self._instrucciones.append(ins)

    def _emitir_etiqueta(self, etiqueta: str):
        self._emitir(Instruccion("LABEL", resultado=etiqueta))

    # ------------------------------------------------------------------
    # Helpers de nodo
    # ------------------------------------------------------------------

    @staticmethod
    def _nombre(nodo) -> str:
        return str(getattr(nodo, "nombre", "")).lower()

    @staticmethod
    def _texto(nodo) -> str:
        return str(getattr(nodo, "nombre", nodo))

    @staticmethod
    def _hijos(nodo) -> list:
        return getattr(nodo, "hijos", [])

    # ------------------------------------------------------------------
    # Recorrido principal
    # ------------------------------------------------------------------

    def _visitar(self, nodo):
        if nodo is None:
            return None

        nombre = self._nombre(nodo)

        dispatch = {
            "programa":         self._gen_programa,
            "bloque":           self._gen_bloque,
            "bloque_incompleto":self._gen_bloque,
            "declaracion":      self._gen_declaracion,
            "declaracion_error":lambda n: None,
            "funcion":          self._gen_funcion,
            "llamada_funcion":  self._gen_llamada_funcion,
            "imprimir":         self._gen_imprimir,
            "retraso":          self._gen_retraso,
            "si":               self._gen_si,
            "mientras":         self._gen_mientras,
            "para":             self._gen_para,
            "romper":           self._gen_romper,
            "dispositivo":      self._gen_dispositivo,
            "accion_dispositivo": self._gen_accion_dispositivo,
            "binop":            self._gen_expresion,
            "unop":             self._gen_expresion,
            "constante":        self._gen_expresion,
            "arreglo":          self._gen_expresion,
            "valor_dispositivo":self._gen_expresion,
        }

        handler = dispatch.get(nombre)
        if handler:
            return handler(nodo)

        # nodos de expresión no mapeados
        return self._gen_expresion(nodo)

    # ------------------------------------------------------------------
    # Programa y bloque
    # ------------------------------------------------------------------

    def _gen_programa(self, nodo):
        for hijo in self._hijos(nodo):
            self._visitar(hijo)

    def _gen_bloque(self, nodo):
        for hijo in self._hijos(nodo):
            self._visitar(hijo)

    # ------------------------------------------------------------------
    # Declaraciones de variables
    # ------------------------------------------------------------------

    def _gen_declaracion(self, nodo):
        hijos = self._hijos(nodo)
        total = len(hijos)

        # tipo id ;         (declaración sin valor)
        if total == 3:
            tipo  = self._texto(hijos[0])
            nombre = self._texto(hijos[1])
            # inicializamos a valor por defecto
            default = self._default_para_tipo(tipo)
            self._emitir(Instruccion("COPY", arg1=default, resultado=nombre))
            return

        # tipo id = expr ;
        if total == 5:
            nombre = self._texto(hijos[1])
            val = self._gen_expresion(hijos[3])
            self._emitir(Instruccion("COPY", arg1=val, resultado=nombre))
            return

        # tipo id [tam] ;
        if total == 6:
            nombre = self._texto(hijos[1])
            tam    = self._texto(hijos[3])
            self._emitir(Instruccion("DEV_DECL", arg1="array", arg2=tam, resultado=nombre))
            return

        # id [indice] = expr ;
        if total == 7:
            nombre  = self._texto(hijos[0])
            indice  = self._texto(hijos[2])
            val     = self._gen_expresion(hijos[5])
            self._emitir(Instruccion("COPY", arg1=val, resultado=f"{nombre}[{indice}]"))
            return

    @staticmethod
    def _default_para_tipo(tipo: str) -> str:
        tipo = tipo.lower()
        if tipo in ("entero", "real_tipo", "real"):
            return "0"
        if tipo == "booleano":
            return "false"
        if tipo in ("cadena", "cadena_tipo"):
            return '""'
        return "0"

    # ------------------------------------------------------------------
    # Funciones
    # ------------------------------------------------------------------

    def _gen_funcion(self, nodo):
        hijos = self._hijos(nodo)
        if len(hijos) < 3:
            return

        nombre = self._texto(hijos[0])
        params_nodo = hijos[1]
        bloque = hijos[2]

        # etiqueta de inicio de función
        self._emitir_etiqueta(f"func_{nombre}")

        # declarar parámetros (ya existen en la pila; solo los anotamos como comentario)
        for param in self._hijos(params_nodo):
            if self._nombre(param) == "parametro":
                ph = self._hijos(param)
                if len(ph) == 2:
                    p_nombre = self._texto(ph[1])
                    self._emitir(Instruccion("COPY", arg1=f"param_{p_nombre}", resultado=p_nombre))

        # cuerpo
        self._gen_bloque(bloque)

        # return implícito
        self._emitir(Instruccion("RETURN"))

    # ------------------------------------------------------------------
    # Llamada a función
    # ------------------------------------------------------------------

    def _gen_llamada_funcion(self, nodo):
        hijos = self._hijos(nodo)
        if len(hijos) < 2:
            return None

        nombre = self._texto(hijos[0])
        args_nodo = hijos[1]
        args = self._hijos(args_nodo)

        # emitir los parámetros
        vals = []
        for arg in args:
            v = self._gen_expresion(arg)
            vals.append(v)

        for v in vals:
            self._emitir(Instruccion("PARAM", arg1=v))

        resultado = self._nuevo_temp()
        self._emitir(Instruccion("CALL", arg1=nombre, arg2=len(args), resultado=resultado))
        return resultado

    # ------------------------------------------------------------------
    # imprimir / retraso
    # ------------------------------------------------------------------

    def _gen_imprimir(self, nodo):
        hijos = self._hijos(nodo)
        if hijos:
            val = self._gen_expresion(hijos[0])
            self._emitir(Instruccion("PRINT", arg1=val))

    def _gen_retraso(self, nodo):
        hijos = self._hijos(nodo)
        if hijos:
            val = self._gen_expresion(hijos[0])
            self._emitir(Instruccion("DELAY", arg1=val))

    # ------------------------------------------------------------------
    # Control: si / sino
    # ------------------------------------------------------------------

    def _gen_si(self, nodo):
        hijos = self._hijos(nodo)
        # hijos: [condicion, bloque_si, (sino), (bloque_sino)]
        cond = self._gen_condicion(hijos[0])

        tiene_sino = len(hijos) >= 4

        etiqueta_sino  = self._nueva_etiqueta("L_sino")
        etiqueta_fin   = self._nueva_etiqueta("L_fin_si")

        # if NOT cond goto sino/fin
        self._emitir_salto_condicional_negado(cond, etiqueta_sino)

        # bloque si
        self._gen_bloque(hijos[1])

        if tiene_sino:
            self._emitir(Instruccion("GOTO", resultado=etiqueta_fin))
            self._emitir_etiqueta(etiqueta_sino)
            self._gen_bloque(hijos[3])
            self._emitir_etiqueta(etiqueta_fin)
        else:
            self._emitir_etiqueta(etiqueta_sino)

    # ------------------------------------------------------------------
    # Control: mientras
    # ------------------------------------------------------------------

    def _gen_mientras(self, nodo):
        hijos = self._hijos(nodo)

        etiqueta_inicio = self._nueva_etiqueta("L_mientras")
        etiqueta_fin    = self._nueva_etiqueta("L_fin_mientras")

        self._emitir_etiqueta(etiqueta_inicio)

        cond = self._gen_condicion(hijos[0])
        self._emitir_salto_condicional_negado(cond, etiqueta_fin)

        self._gen_bloque(hijos[1])

        self._emitir(Instruccion("GOTO", resultado=etiqueta_inicio))
        self._emitir_etiqueta(etiqueta_fin)

    # ------------------------------------------------------------------
    # Control: para
    # ------------------------------------------------------------------

    def _gen_para(self, nodo):
        hijos = self._hijos(nodo)
        # hijos: [asignacion_para, condicion, actualizacion_para, bloque]

        etiqueta_inicio = self._nueva_etiqueta("L_para")
        etiqueta_fin    = self._nueva_etiqueta("L_fin_para")

        # inicialización
        if len(hijos) >= 1:
            self._gen_asignacion_para(hijos[0])

        self._emitir_etiqueta(etiqueta_inicio)

        # condición
        if len(hijos) >= 2:
            cond = self._gen_condicion(hijos[1])
            self._emitir_salto_condicional_negado(cond, etiqueta_fin)

        # cuerpo
        if len(hijos) >= 4:
            self._gen_bloque(hijos[3])

        # actualización
        if len(hijos) >= 3:
            self._gen_actualizacion_para(hijos[2])

        self._emitir(Instruccion("GOTO", resultado=etiqueta_inicio))
        self._emitir_etiqueta(etiqueta_fin)

    def _gen_asignacion_para(self, nodo):
        hijos = self._hijos(nodo)
        textos = [self._texto(h) for h in hijos]

        # tipo id = expr  (4 hijos)
        if len(hijos) == 4:
            nombre = textos[1]
            val = self._gen_expresion(hijos[3])
            self._emitir(Instruccion("COPY", arg1=val, resultado=nombre))
        # id = expr  (3 hijos)
        elif len(hijos) == 3:
            nombre = textos[0]
            val = self._gen_expresion(hijos[2])
            self._emitir(Instruccion("COPY", arg1=val, resultado=nombre))

    def _gen_actualizacion_para(self, nodo):
        hijos = self._hijos(nodo)
        textos = [self._texto(h) for h in hijos]

        if len(textos) == 2:
            nombre = textos[0]
            op = textos[1]
            if op == "++":
                t = self._nuevo_temp()
                self._emitir(Instruccion("COPY",
                    arg1=f"{nombre} + 1", resultado=t))
                self._emitir(Instruccion("COPY", arg1=t, resultado=nombre))
            elif op == "--":
                t = self._nuevo_temp()
                self._emitir(Instruccion("COPY",
                    arg1=f"{nombre} - 1", resultado=t))
                self._emitir(Instruccion("COPY", arg1=t, resultado=nombre))
        elif len(hijos) == 3:
            nombre = textos[0]
            val = self._gen_expresion(hijos[2])
            self._emitir(Instruccion("COPY", arg1=val, resultado=nombre))

    def _gen_romper(self, nodo):
        # En TAC real se usaría la etiqueta de fin del bucle actual.
        # Como simplificación, emitimos un goto especial.
        self._emitir(Instruccion("GOTO", resultado="__break__"))

    # ------------------------------------------------------------------
    # Dispositivos
    # ------------------------------------------------------------------

    def _gen_dispositivo(self, nodo):
        hijos = self._hijos(nodo)
        if len(hijos) < 3:
            return

        tipo_disp = self._texto(hijos[0])
        nombre    = self._texto(hijos[1])
        atributos = hijos[2]

        # Construir string de atributos
        attrs = []
        for atr in self._hijos(atributos):
            if self._nombre(atr) == "atributo":
                ah = self._hijos(atr)
                if len(ah) == 2:
                    k = self._texto(ah[0])
                    v = self._gen_expresion(ah[1])
                    attrs.append(f"{k}={v}")

        self._emitir(Instruccion("DEV_DECL",
            arg1=tipo_disp,
            arg2=", ".join(attrs),
            resultado=nombre))

    def _gen_accion_dispositivo(self, nodo):
        hijos = self._hijos(nodo)
        if len(hijos) < 3:
            return None

        nombre  = self._texto(hijos[0])
        accion  = self._texto(hijos[1])
        arg_nodo = hijos[2]

        if self._nombre(arg_nodo) == "vacio":
            call_str = f"{accion}()"
        else:
            val = self._gen_expresion(arg_nodo)
            call_str = f"{accion}({val})"

        t = self._nuevo_temp()
        self._emitir(Instruccion("DEV_ACTION", arg1=nombre, arg2=call_str, resultado=t))
        return t

    # ------------------------------------------------------------------
    # Expresiones → devuelven nombre de temporal o literal
    # ------------------------------------------------------------------

    def _gen_expresion(self, nodo) -> str:
        if nodo is None:
            return "0"

        nombre = self._nombre(nodo)

        # constante o identificador
        if nombre == "constante":
            hijos = self._hijos(nodo)
            if hijos:
                return self._texto(hijos[0])
            return "0"

        # arreglo: id[indice]
        if nombre == "arreglo":
            hijos = self._hijos(nodo)
            arr  = self._texto(hijos[0])
            idx  = self._texto(hijos[1])
            t = self._nuevo_temp()
            self._emitir(Instruccion("COPY", arg1=f"{arr}[{idx}]", resultado=t))
            return t

        # operación binaria: resultado = arg1 op arg2
        if nombre == "binop":
            hijos = self._hijos(nodo)
            izq = self._gen_expresion(hijos[0])
            op  = self._texto(hijos[1])
            der = self._gen_expresion(hijos[2])
            t = self._nuevo_temp()
            self._emitir(Instruccion("COPY",
                arg1=f"{izq} {op} {der}",
                resultado=t))
            return t

        # operación unaria: resultado = op arg
        if nombre == "unop":
            hijos = self._hijos(nodo)
            op  = self._texto(hijos[0])
            val = self._gen_expresion(hijos[1])
            t = self._nuevo_temp()
            self._emitir(Instruccion("COPY",
                arg1=f"{op}{val}",
                resultado=t))
            return t

        # valor de dispositivo: id->valor()
        if nombre == "valor_dispositivo":
            hijos = self._hijos(nodo)
            dev = self._texto(hijos[0])
            t = self._nuevo_temp()
            self._emitir(Instruccion("DEV_ACTION",
                arg1=dev, arg2="valor()", resultado=t))
            return t

        # llamada de función como expresión
        if nombre == "llamada_funcion":
            return self._gen_llamada_funcion(nodo) or "0"

        # fallback
        return self._texto(nodo)

    # ------------------------------------------------------------------
    # Generación de condiciones (para saltos condicionales)
    # ------------------------------------------------------------------

    def _gen_condicion(self, nodo) -> dict:
        """
        Devuelve un dict {izq, op, der} o {temp} para el nodo de condición.
        Si la condición ya es un binop relacional, extrae sus partes.
        """
        nombre = self._nombre(nodo)

        if nombre == "binop":
            hijos = self._hijos(nodo)
            op = self._texto(hijos[1])
            if op in ("<", ">", "<=", ">=", "==", "!=", "&&", "||"):
                izq = self._gen_expresion(hijos[0])
                der = self._gen_expresion(hijos[2])
                return {"izq": izq, "op": op, "der": der}

        # para condiciones no directamente relacionales, evaluamos a temp
        t = self._gen_expresion(nodo)
        return {"izq": t, "op": "==", "der": "true"}

    def _emitir_salto_condicional_negado(self, cond: dict, etiqueta: str):
        """
        Emite:  if izq NOT_op der goto etiqueta
        (salta cuando la condición es FALSA)
        """
        neg = {
            "<":  ">=", ">":  "<=",
            "<=": ">",  ">=": "<",
            "==": "!=", "!=": "==",
            "&&": "||_neg",  # simplificación
            "||": "&&_neg",
        }
        op_neg = neg.get(cond["op"], f"!{cond['op']}")
        self._emitir(Instruccion("IF",
            arg1=cond["izq"],
            arg2=f"{op_neg} {cond['der']}",
            resultado=etiqueta))
