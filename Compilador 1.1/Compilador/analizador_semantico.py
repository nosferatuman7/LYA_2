import re
from copy import deepcopy


class AnalizadorSemantico:
    """
    analizador semántico para minirobotcode

    valida:
    - variable no declarada
    - redeclaración
    - incompatibilidad de tipos
    - validación de funciones
    - validación de condiciones
    - tabla de símbolos
    - alcance de variables
    - validación de dispositivos
    """

    tipos_basicos = {"entero", "real", "booleano", "cadena"}

    acciones_por_dispositivo = {
        "encender": {
            "led", "buzzer", "motor", "hub_powered_up", "hub_spike_prime",
            "hub_spike_essential", "hub_robot_inventor", "hub_technic_large",
        },
        "apagar": {
            "led", "buzzer", "motor", "hub_powered_up", "hub_spike_prime",
            "hub_spike_essential", "hub_robot_inventor", "hub_technic_large",
        },
        "girarservo": {
            "servo", "motor_servo_grande_ev3", "motor_servo_mediano_ev3",
            "servomotor_nxt", "motor_angular_grande", "motor_angular_mediano",
        },
        "girarmotor": {
            "motor", "motor_powered_up_boost", "motor_powered_up", "motor_boost",
            "motor_angular_grande", "motor_angular_mediano",
            "motor_servo_grande_ev3", "motor_servo_mediano_ev3", "servomotor_nxt",
        },
        "valor": {
            "sensor", "sensor_ultrasonico", "sensor_color", "sensor_toque",
            "sensor_giro", "rcx", "nxt", "ev3", "hub_spike_prime",
            "hub_spike_essential", "hub_robot_inventor", "hub_technic_large",
            "hub_powered_up",
        },
    }

    def __init__(self):
        self.errores = []
        self.advertencias = []
        self.tabla_simbolos = []
        self.funciones = {}
        self.pila_ambitos = []
        self.nivel_bucle = 0
        self.contador_ambitos = 0

    # =========================================================
    # api pública
    # =========================================================
    def analizar(self, raiz):
        self.errores = []
        self.advertencias = []
        self.tabla_simbolos = []
        self.funciones = {}
        self.pila_ambitos = []
        self.nivel_bucle = 0
        self.contador_ambitos = 0

        self._entrar_ambito("global")

        if raiz is None:
            self._error("no se recibió un ast para analizar")
            return self.errores

        if self._nombre(raiz) != "programa":
            self._error("el nodo raíz no corresponde a un programa")
            return self.errores

        self._visitar(raiz)
        return self.errores

    def obtener_reporte(self):
        return {
            "errores": deepcopy(self.errores),
            "advertencias": deepcopy(self.advertencias),
            "tabla_simbolos": deepcopy(self.tabla_simbolos),
            "funciones": deepcopy(self.funciones),
        }

    # =========================================================
    # recorrido principal
    # =========================================================
    def _visitar(self, nodo):
        if nodo is None:
            return None

        nombre = self._nombre(nodo)

        if nombre == "programa":
            for hijo in getattr(nodo, "hijos", []):
                self._visitar(hijo)
            return None

        if nombre in ("bloque", "bloque_incompleto"):
            return self._analizar_bloque(nodo)

        if nombre == "declaracion":
            return self._analizar_declaracion(nodo)

        if nombre == "declaracion_error":
            return None

        if nombre == "funcion":
            return self._analizar_funcion(nodo, preregistrada=False)

        if nombre == "llamada_funcion":
            return self._analizar_llamada_funcion(nodo)

        if nombre == "imprimir":
            if nodo.hijos:
                self._inferir_tipo_expresion(nodo.hijos[0])
            return None

        if nombre == "retraso":
            if nodo.hijos:
                tipo = self._inferir_tipo_expresion(nodo.hijos[0])
                if not self._es_numerico(tipo):
                    self._error("retraso(...) solo acepta expresiones numéricas")
            return None

        if nombre == "si":
            return self._analizar_si(nodo)

        if nombre == "mientras":
            return self._analizar_mientras(nodo)

        if nombre == "para":
            return self._analizar_para(nodo)

        if nombre == "romper":
            if self.nivel_bucle <= 0:
                self._error("'romper' solo puede usarse dentro de 'mientras' o 'para'")
            return None

        if nombre == "dispositivo":
            return self._analizar_dispositivo(nodo)

        if nombre == "accion_dispositivo":
            return self._analizar_accion_dispositivo(nodo)

        return self._inferir_tipo_expresion(nodo)

    def _analizar_bloque(self, nodo, abrir_ambito=True, etiqueta="bloque"):
        if abrir_ambito:
            self._entrar_ambito(etiqueta)

        self._preregistrar_funciones_en_bloque(nodo)

        for hijo in getattr(nodo, "hijos", []):
            if self._nombre(hijo) == "funcion":
                self._analizar_funcion(hijo, preregistrada=True)
            else:
                self._visitar(hijo)

        if abrir_ambito:
            self._salir_ambito()

        return None

    # =========================================================
    # declaraciones
    # =========================================================
    def _analizar_declaracion(self, nodo):
        hijos = getattr(nodo, "hijos", [])
        total = len(hijos)

        # tipo id ;
        if total == 3:
            tipo = self._valor_normalizado(hijos[0])
            nombre = self._texto(hijos[1])
            self._declarar_simbolo(nombre, tipo, clase="variable")
            return None

        # tipo id = expr ;
        if total == 5:
            tipo = self._valor_normalizado(hijos[0])
            nombre = self._texto(hijos[1])
            tipo_expr = self._inferir_tipo_expresion(hijos[3])
            valor_expr = self._representacion_expr(hijos[3])

            self._declarar_simbolo(nombre, tipo, clase="variable", valor=valor_expr)

            if not self._tipos_compatibles(tipo, tipo_expr):
                self._error(
                    f"tipo incompatible en la asignación de '{nombre}': se declaró {tipo} y se asignó {tipo_expr}"
                )
            return None

        # tipo id [numero] ;
        if total == 6:
            tipo = self._valor_normalizado(hijos[0])
            nombre = self._texto(hijos[1])
            tam = self._entero_seguro(self._texto(hijos[3]))

            if tam is None or tam <= 0:
                self._error(f"el arreglo '{nombre}' debe tener un tamaño mayor que cero")

            self._declarar_simbolo(nombre, tipo, clase="arreglo", tam=tam)
            return None

        # id [numero] = expr ;
        if total == 7:
            nombre = self._texto(hijos[0])
            indice = self._entero_seguro(self._texto(hijos[2]))
            tipo_expr = self._inferir_tipo_expresion(hijos[5])
            simbolo = self._buscar_simbolo(nombre)

            if simbolo is None:
                self._error(f"el arreglo '{nombre}' no ha sido declarado")
                return None

            if simbolo.get("clase") != "arreglo":
                self._error(f"'{nombre}' no es un arreglo")
                return None

            tam = simbolo.get("tam")
            if indice is None:
                self._error(f"el índice usado en '{nombre}[...]' debe ser entero")
            elif tam is not None and (indice < 0 or indice >= tam):
                self._error(f"índice fuera de rango en '{nombre}[{indice}]'")

            if not self._tipos_compatibles(simbolo.get("tipo"), tipo_expr):
                self._error(
                    f"tipo incompatible en '{nombre}[{indice}]': el arreglo es {simbolo.get('tipo')} y se asignó {tipo_expr}"
                )
            return None

        return None

    # =========================================================
    # funciones
    # =========================================================
    def _analizar_funcion(self, nodo, preregistrada=False):
        hijos = getattr(nodo, "hijos", [])
        if len(hijos) < 3:
            return None

        nombre = self._texto(hijos[0])
        parametros_nodo = hijos[1]
        bloque = hijos[2]
        parametros = self._extraer_parametros(parametros_nodo)

        if not preregistrada:
            if nombre in self.funciones:
                self._error(f"la función '{nombre}' ya fue declarada anteriormente")
            else:
                self.funciones[nombre] = {
                    "nombre": nombre,
                    "parametros": parametros,
                    "retorno": "void",
                }
                self._declarar_simbolo(
                    nombre,
                    "funcion",
                    clase="funcion",
                    valor=self._firma_parametros(parametros)
                )
        else:
            if nombre not in self.funciones:
                self.funciones[nombre] = {
                    "nombre": nombre,
                    "parametros": parametros,
                    "retorno": "void",
                }
                self._declarar_simbolo(
                    nombre,
                    "funcion",
                    clase="funcion",
                    valor=self._firma_parametros(parametros)
                )

        self._entrar_ambito(f"funcion:{nombre}")

        nombres_param = set()
        for param in parametros:
            if param["nombre"] in nombres_param:
                self._error(f"el parámetro '{param['nombre']}' está repetido en la función '{nombre}'")
                continue
            nombres_param.add(param["nombre"])
            self._declarar_simbolo(param["nombre"], param["tipo"], clase="parametro")

        self._analizar_bloque(bloque, abrir_ambito=False, etiqueta=f"cuerpo:{nombre}")
        self._salir_ambito()
        return None

    def _analizar_llamada_funcion(self, nodo):
        hijos = getattr(nodo, "hijos", [])
        if len(hijos) < 2:
            return "error"

        nombre = self._texto(hijos[0])
        argumentos = getattr(hijos[1], "hijos", []) if hijos[1] is not None else []
        firma = self.funciones.get(nombre)

        if firma is None:
            self._error(f"la función '{nombre}' no ha sido declarada")
            for arg in argumentos:
                self._inferir_tipo_expresion(arg)
            return "error"

        esperados = firma.get("parametros", [])

        if len(argumentos) != len(esperados):
            self._error(
                f"la función '{nombre}' esperaba {len(esperados)} argumento(s) y recibió {len(argumentos)}"
            )

        for i, arg in enumerate(argumentos[:len(esperados)]):
            tipo_arg = self._inferir_tipo_expresion(arg)
            tipo_param = esperados[i]["tipo"]

            if not self._tipos_compatibles(tipo_param, tipo_arg):
                self._error(
                    f"argumento {i + 1} incompatible en '{nombre}': se esperaba {tipo_param} y llegó {tipo_arg}"
                )

        for arg in argumentos[len(esperados):]:
            self._inferir_tipo_expresion(arg)

        return firma.get("retorno", "void")

    # =========================================================
    # control
    # =========================================================
    def _analizar_si(self, nodo):
        hijos = getattr(nodo, "hijos", [])
        if not hijos:
            return None

        tipo_cond = self._inferir_tipo_expresion(hijos[0])
        if not self._es_booleano(tipo_cond):
            self._error("la condición de 'si' debe ser booleana")

        if len(hijos) >= 2:
            self._visitar(hijos[1])
        if len(hijos) >= 4:
            self._visitar(hijos[3])

        return None

    def _analizar_mientras(self, nodo):
        hijos = getattr(nodo, "hijos", [])
        if hijos:
            tipo_cond = self._inferir_tipo_expresion(hijos[0])
            if not self._es_booleano(tipo_cond):
                self._error("la condición de 'mientras' debe ser booleana")

        self.nivel_bucle += 1
        if len(hijos) >= 2:
            self._visitar(hijos[1])
        self.nivel_bucle -= 1
        return None

    def _analizar_para(self, nodo):
        hijos = getattr(nodo, "hijos", [])

        self._entrar_ambito("para")

        if len(hijos) >= 1:
            self._analizar_asignacion_para(hijos[0])

        if len(hijos) >= 2:
            tipo_cond = self._inferir_tipo_expresion(hijos[1])
            if not self._es_booleano(tipo_cond):
                self._error("la condición de 'para' debe ser booleana")

        self.nivel_bucle += 1
        if len(hijos) >= 3:
            self._analizar_actualizacion_para(hijos[2])
        if len(hijos) >= 4:
            self._visitar(hijos[3])
        self.nivel_bucle -= 1

        self._salir_ambito()
        return None

    def _analizar_asignacion_para(self, nodo):
        piezas = [self._texto(h) for h in getattr(nodo, "hijos", [])]

        if len(piezas) == 4:
            tipo = self._valor_normalizado(nodo.hijos[0])
            nombre = self._texto(nodo.hijos[1])
            tipo_expr = self._inferir_tipo_expresion(nodo.hijos[3])

            self._declarar_simbolo(nombre, tipo, clase="variable")

            if not self._tipos_compatibles(tipo, tipo_expr):
                self._error(
                    f"tipo incompatible en la inicialización de 'para' para '{nombre}': {tipo} <- {tipo_expr}"
                )
            return None

        if len(piezas) == 3:
            nombre = self._texto(nodo.hijos[0])
            simbolo = self._buscar_simbolo(nombre)

            if simbolo is None:
                self._error(f"la variable '{nombre}' no ha sido declarada en la inicialización del 'para'")
                return None

            tipo_expr = self._inferir_tipo_expresion(nodo.hijos[2])
            if not self._tipos_compatibles(simbolo.get("tipo"), tipo_expr):
                self._error(
                    f"tipo incompatible en la inicialización del 'para' para '{nombre}': {simbolo.get('tipo')} <- {tipo_expr}"
                )

    def _analizar_actualizacion_para(self, nodo):
        piezas = [self._texto(h) for h in getattr(nodo, "hijos", [])]
        if not piezas:
            return None

        nombre = piezas[0]
        simbolo = self._buscar_simbolo(nombre)

        if simbolo is None:
            self._error(f"la variable '{nombre}' no ha sido declarada en la actualización del 'para'")
            return None

        if len(piezas) == 3:
            tipo_expr = self._inferir_tipo_expresion(nodo.hijos[2])
            if not self._tipos_compatibles(simbolo.get("tipo"), tipo_expr):
                self._error(
                    f"tipo incompatible en la actualización del 'para' para '{nombre}': {simbolo.get('tipo')} <- {tipo_expr}"
                )
        elif len(piezas) == 2 and piezas[1] in ("++", "--"):
            if not self._es_numerico(simbolo.get("tipo")):
                self._error(
                    f"solo se puede usar '{piezas[1]}' sobre variables numéricas, no sobre '{nombre}'"
                )

    # =========================================================
    # dispositivos
    # =========================================================
    def _analizar_dispositivo(self, nodo):
        hijos = getattr(nodo, "hijos", [])
        if len(hijos) != 3:
            return None

        tipo_disp = self._valor_normalizado(hijos[0])
        nombre = self._texto(hijos[1])
        atributos = hijos[2]

        self._declarar_simbolo(nombre, tipo_disp, clase="dispositivo")

        if self._nombre(atributos) == "atributos":
            for atributo in getattr(atributos, "hijos", []):
                if self._nombre(atributo) != "atributo" or len(getattr(atributo, "hijos", [])) != 2:
                    continue

                llave = self._texto(atributo.hijos[0])
                tipo_valor = self._inferir_tipo_expresion(atributo.hijos[1])

                if llave in ("pin", "pwm", "in1", "in2", "puerto", "canal"):
                    if not self._es_numerico(tipo_valor):
                        self._error(
                            f"el atributo '{llave}' del dispositivo '{nombre}' debe ser numérico"
                        )
        return None

    def _analizar_accion_dispositivo(self, nodo):
        hijos = getattr(nodo, "hijos", [])
        if len(hijos) != 3:
            return None

        nombre = self._texto(hijos[0])
        accion = self._valor_normalizado(hijos[1])
        argumento = hijos[2]

        simbolo = self._buscar_simbolo(nombre)

        if simbolo is None:
            self._error(f"el dispositivo '{nombre}' no ha sido declarado")
            return None

        if simbolo.get("clase") != "dispositivo":
            self._error(f"'{nombre}' no es un dispositivo válido para usar '->'")
            return None

        tipo_disp = self._valor_normalizado(simbolo.get("tipo"))
        permitidos = self.acciones_por_dispositivo.get(accion, set())

        if accion not in self.acciones_por_dispositivo:
            self._error(f"la acción '{accion}' no existe en el lenguaje")
            return None

        if tipo_disp not in permitidos:
            self._error(
                f"la acción '{accion}' no es válida para el dispositivo '{nombre}' de tipo '{tipo_disp}'"
            )

        if accion in ("girarservo", "girarmotor"):
            tipo_arg = self._inferir_tipo_expresion(argumento)
            if not self._es_numerico(tipo_arg):
                self._error(f"la acción '{accion}' sobre '{nombre}' requiere un argumento numérico")

        if accion == "valor":
            if self._nombre(argumento) != "vacio":
                self._inferir_tipo_expresion(argumento)
                self.advertencias.append(f"'valor()' normalmente no requiere argumentos en '{nombre}'")
            return "dispositivo_valor"

        if accion in ("encender", "apagar"):
            if self._nombre(argumento) != "vacio":
                self._inferir_tipo_expresion(argumento)
                self.advertencias.append(
                    f"la acción '{accion}' normalmente no requiere argumentos en '{nombre}'"
                )

        return None

    # =========================================================
    # expresiones
    # =========================================================
    def _inferir_tipo_expresion(self, nodo):
        if nodo is None:
            return "void"

        nombre = self._nombre(nodo)

        if nombre == "constante":
            if not getattr(nodo, "hijos", []):
                return "error"
            return self._inferir_tipo_constante_o_id(self._texto(nodo.hijos[0]))

        if nombre == "arreglo":
            nombre_arr = self._texto(nodo.hijos[0])
            indice = self._entero_seguro(self._texto(nodo.hijos[1]))
            simbolo = self._buscar_simbolo(nombre_arr)

            if simbolo is None:
                self._error(f"el arreglo '{nombre_arr}' no ha sido declarado")
                return "error"

            if simbolo.get("clase") != "arreglo":
                self._error(f"'{nombre_arr}' no es un arreglo")
                return "error"

            tam = simbolo.get("tam")
            if indice is None:
                self._error(f"el índice usado en '{nombre_arr}[...]' debe ser entero")
            elif tam is not None and (indice < 0 or indice >= tam):
                self._error(f"índice fuera de rango en '{nombre_arr}[{indice}]'")

            return self._valor_normalizado(simbolo.get("tipo", "error"))

        if nombre == "binop":
            return self._inferir_tipo_binop(nodo)

        if nombre == "unop":
            return self._inferir_tipo_unop(nodo)

        if nombre == "valor_dispositivo":
            return self._inferir_tipo_valor_dispositivo(nodo)

        if nombre == "llamada_funcion":
            retorno = self._analizar_llamada_funcion(nodo)
            return retorno or "void"

        if nombre == "vacio":
            return "void"

        return "error"

    def _inferir_tipo_constante_o_id(self, valor):
        texto = str(valor)
        texto_min = texto.lower()

        if texto_min in ("true", "false"):
            return "booleano"

        if re.fullmatch(r"-?\d+", texto):
            return "entero"

        if re.fullmatch(r"-?\d+\.\d+", texto):
            return "real"

        if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", texto):
            simbolo = self._buscar_simbolo(texto)
            if simbolo is None:
                self._error(f"variable '{texto}' usada sin declaracion")
                return "error"
            return self._valor_normalizado(simbolo.get("tipo", "error"))

        return "cadena"

    def _inferir_tipo_binop(self, nodo):
        if len(getattr(nodo, "hijos", [])) != 3:
            return "error"

        tipo_izq = self._inferir_tipo_expresion(nodo.hijos[0])
        op = self._texto(nodo.hijos[1])
        tipo_der = self._inferir_tipo_expresion(nodo.hijos[2])

        if op in ("+", "-", "*", "/", "%"):
            if op == "+" and tipo_izq == "cadena" and tipo_der == "cadena":
                return "cadena"

            if self._es_numerico(tipo_izq) and self._es_numerico(tipo_der):
                return "real" if "real" in (tipo_izq, tipo_der) else "entero"

            self._error(f"operación inválida: no se puede aplicar '{op}' entre {tipo_izq} y {tipo_der}")
            return "error"

        if op in ("<", ">", "<=", ">="):
            if self._es_numerico(tipo_izq) and self._es_numerico(tipo_der):
                return "booleano"

            self._error(f"comparación inválida: no se puede aplicar '{op}' entre {tipo_izq} y {tipo_der}")
            return "error"

        if op in ("==", "!="):
            if self._comparables_igualdad(tipo_izq, tipo_der):
                return "booleano"

            self._error(f"comparación inválida: no se puede aplicar '{op}' entre {tipo_izq} y {tipo_der}")
            return "error"

        if op in ("&&", "||"):
            if self._es_booleano(tipo_izq) and self._es_booleano(tipo_der):
                return "booleano"

            self._error(f"operación lógica inválida: '{op}' requiere booleanos, no {tipo_izq} y {tipo_der}")
            return "error"

        return "error"

    def _inferir_tipo_unop(self, nodo):
        if len(getattr(nodo, "hijos", [])) != 2:
            return "error"

        op = self._texto(nodo.hijos[0])
        tipo = self._inferir_tipo_expresion(nodo.hijos[1])

        if op == "!":
            if self._es_booleano(tipo):
                return "booleano"
            self._error(f"el operador '!' requiere un booleano, no {tipo}")
            return "error"

        if op == "-":
            if self._es_numerico(tipo):
                return "real" if tipo == "real" else "entero"
            self._error(f"el operador unario '-' requiere un número, no {tipo}")
            return "error"

        return "error"

    def _inferir_tipo_valor_dispositivo(self, nodo):
        if len(getattr(nodo, "hijos", [])) != 2:
            return "error"

        nombre = self._texto(nodo.hijos[0])
        simbolo = self._buscar_simbolo(nombre)

        if simbolo is None:
            self._error(f"el dispositivo '{nombre}' no ha sido declarado")
            return "error"

        if simbolo.get("clase") != "dispositivo":
            self._error(f"'{nombre}' no es un dispositivo válido para leer con 'valor()'")
            return "error"

        if self._valor_normalizado(simbolo.get("tipo")) not in self.acciones_por_dispositivo["valor"]:
            self._error(
                f"el dispositivo '{nombre}' de tipo '{simbolo.get('tipo')}' no soporta 'valor()'"
            )
            return "error"

        argumento = nodo.hijos[1]
        if self._nombre(argumento) != "vacio":
            self._inferir_tipo_expresion(argumento)
            self.advertencias.append(f"'valor()' normalmente no requiere argumentos en '{nombre}'")

        return "dispositivo_valor"

    # =========================================================
    # helpers
    # =========================================================
    def _preregistrar_funciones_en_bloque(self, bloque):
        if bloque is None or self._nombre(bloque) not in ("bloque", "bloque_incompleto"):
            return

        ambito_actual = self.pila_ambitos[-1]["simbolos"]

        for hijo in getattr(bloque, "hijos", []):
            if self._nombre(hijo) != "funcion":
                continue

            nombre = self._texto(hijo.hijos[0]) if getattr(hijo, "hijos", []) else ""
            parametros = self._extraer_parametros(hijo.hijos[1] if len(hijo.hijos) > 1 else None)

            if nombre in ambito_actual or nombre in self.funciones:
                self._error(f"la función '{nombre}' ya fue declarada anteriormente")
                continue

            self.funciones[nombre] = {
                "nombre": nombre,
                "parametros": parametros,
                "retorno": "void",
            }

            self._declarar_simbolo(
                nombre,
                "funcion",
                clase="funcion",
                valor=self._firma_parametros(parametros)
            )

    def _extraer_parametros(self, nodo_parametros):
        params = []
        if nodo_parametros is None:
            return params

        for nodo in getattr(nodo_parametros, "hijos", []):
            if self._nombre(nodo) != "parametro" or len(getattr(nodo, "hijos", [])) != 2:
                continue

            params.append({
                "tipo": self._valor_normalizado(nodo.hijos[0]),
                "nombre": self._texto(nodo.hijos[1]),
            })

        return params

    def _declarar_simbolo(self, nombre, tipo, clase="variable", tam=None, valor=None, linea=None, columna=None):
        if not nombre:
            return False

        tipo = self._valor_normalizado(tipo)
        ambito = self.pila_ambitos[-1]
        simbolos = ambito["simbolos"]

        if nombre in simbolos:
            self._error(f"el identificador '{nombre}' ya fue declarado en este ámbito")
            return False

        simbolo = {
            "nombre": nombre,
            "tipo": tipo,
            "clase": clase,
            "tam": tam,
            "valor": valor,
            "linea": linea,
            "columna": columna,
            "ambito": ambito["nombre"],
        }

        simbolos[nombre] = simbolo
        self.tabla_simbolos.append(deepcopy(simbolo))
        return True

    def _buscar_simbolo(self, nombre):
        for ambito in reversed(self.pila_ambitos):
            if nombre in ambito["simbolos"]:
                return ambito["simbolos"][nombre]
        return None

    def _entrar_ambito(self, nombre="bloque"):
        ambito_nombre = f"{nombre}_{self.contador_ambitos}"
        self.contador_ambitos += 1
        self.pila_ambitos.append({
            "nombre": ambito_nombre,
            "simbolos": {}
        })

    def _salir_ambito(self):
        if len(self.pila_ambitos) > 1:
            self.pila_ambitos.pop()

    def _tipos_compatibles(self, esperado, recibido):
        esperado = self._valor_normalizado(esperado)
        recibido = self._valor_normalizado(recibido)

        if esperado == recibido:
            return True

        if esperado == "real" and recibido == "entero":
            return True

        if recibido == "dispositivo_valor" and esperado in ("entero", "real", "booleano"):
            return True

        return False

    def _comparables_igualdad(self, a, b):
        a = self._valor_normalizado(a)
        b = self._valor_normalizado(b)

        if a == b:
            return True

        if self._es_numerico(a) and self._es_numerico(b):
            return True

        if a == "dispositivo_valor" and b in ("entero", "real", "booleano"):
            return True

        if b == "dispositivo_valor" and a in ("entero", "real", "booleano"):
            return True

        return False

    def _es_numerico(self, tipo):
        return self._valor_normalizado(tipo) in ("entero", "real", "dispositivo_valor")

    def _es_booleano(self, tipo):
        return self._valor_normalizado(tipo) in ("booleano", "dispositivo_valor")

    def _valor_normalizado(self, valor):
        if valor is None:
            return ""

        if hasattr(valor, "nombre"):
            valor = valor.nombre

        texto = str(valor).strip()

        mapa = {
            "ENTERO": "entero",
            "REAL_TIPO": "real",
            "BOOLEANO": "booleano",
            "CADENA_TIPO": "cadena",
            "FUNCION": "funcion",
            "FUNC": "funcion",
            "TRUE": "booleano",
            "FALSE": "booleano",
            "GIRARSERVO": "girarservo",
            "GIRARMOTOR": "girarmotor",
            "ENCENDER": "encender",
            "APAGAR": "apagar",
            "VALOR": "valor",
        }

        return mapa.get(texto, mapa.get(texto.upper(), texto.lower()))

    def _nombre(self, nodo):
        return self._valor_normalizado(getattr(nodo, "nombre", ""))

    def _texto(self, nodo):
        return getattr(nodo, "nombre", str(nodo))

    def _entero_seguro(self, valor):
        try:
            return int(valor)
        except Exception:
            return None

    def _representacion_expr(self, nodo):
        nombre = self._nombre(nodo)

        if nombre == "constante" and getattr(nodo, "hijos", []):
            return self._texto(nodo.hijos[0])

        if nombre == "valor_dispositivo" and len(getattr(nodo, "hijos", [])) >= 1:
            return f"{self._texto(nodo.hijos[0])}->valor()"

        return None

    def _firma_parametros(self, parametros):
        return [f"{p['tipo']} {p['nombre']}" for p in parametros]

    def _error(self, mensaje):
        texto = f"x error semantico: {mensaje}"
        if texto not in self.errores:
            self.errores.append(texto)


analizador_semantico = AnalizadorSemantico