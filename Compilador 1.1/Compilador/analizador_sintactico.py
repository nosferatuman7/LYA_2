import difflib
import ply.yacc as yacc
from ply.lex import LexToken

from lexer import (
    tokens,
    lexer,
    errores_sintacticos,
    palabras_reservadas,
)

from arbol_ast import NodoAST, graficar_arbol


# ------------------------ config ------------------------

DEBUG = False
MAX_ERRORES_SINTACTICOS = 12

# para evitar cascadas (solo 1 error por línea)
_lineas_con_error = set()

# para contexto sin depender de lexdata
_codigo_actual = ""

# lexer proxy para poder "devolver" tokens (pushback)
_lexer_actual = None


# ------------------------ helpers (contexto/columna) ------------------------

def _columna_desde_lexpos(codigo: str, lexpos: int) -> int:
    if lexpos is None:
        return 1
    i = codigo.rfind("\n", 0, lexpos)
    return (lexpos + 1) if i < 0 else (lexpos - i)

def _obtener_linea(codigo: str, lineno: int) -> str:
    if lineno <= 0:
        return ""
    lineas = codigo.splitlines()
    if lineno > len(lineas):
        return ""
    return lineas[lineno - 1]

def _contexto_manual(codigo: str, lineno: int, col: int) -> str:
    linea = _obtener_linea(codigo, lineno)
    if not linea:
        return ""
    caret = " " * max(col - 1, 0) + "^"
    return f"        {linea}\n        {caret}"

def _char_anterior_no_espacio(codigo: str, lexpos: int) -> str:
    if lexpos is None:
        return ""
    i = lexpos - 1
    while i >= 0 and codigo[i] in " \t\r\n":
        i -= 1
    return codigo[i] if i >= 0 else ""


def _sugerencia_reservada(lexema: str):
    claves = sorted({k for k in palabras_reservadas.keys() if k.islower()})
    suger = difflib.get_close_matches(lexema, claves, n=1, cutoff=0.72)
    return suger[0] if suger else None


# ------------------------ prechequeo de delimitadores ------------------------

def prechecar_delimitadores(codigo: str):
    """
    Detecta errores estructurales (llaves faltantes) REPORTANDO TODOS los bloques abiertos.
    Si faltan 2 o 3 llaves, te avisará de cada una.
    """
    lexer.lineno = 1
    lexer.input(codigo)

    tokens_list = list(iter(lexer.token, None))
    stack = []  # (tipo, cierre_esperado, linea, col, CONTEXTO)

    aperturas = {"LLAVE_A": "LLAVE_C", "PARENTESIS_A": "PARENTESIS_B", "CORCHETE_A": "CORCHETE_B"}
    cierres = {v: k for k, v in aperturas.items()}
    vis = {"LLAVE_A": "{", "LLAVE_C": "}", "PARENTESIS_A": "(", "PARENTESIS_B": ")", "CORCHETE_A": "[", "CORCHETE_B": "]"}

    pending_context = 'BLOCK' 

    for i, tok in enumerate(tokens_list):
        col = _columna_desde_lexpos(codigo, tok.lexpos)

        # --- 0. DETECCIÓN DE CONTEXTO ---
        if tok.type == 'INICIO':
            pending_context = 'ROOT'
        elif tok.type == 'FUNC':
            pending_context = 'FUNC'
            # Validar anidamiento ilegal
            if stack and stack[-1][4] != 'ROOT':
                 top_line = stack[-1][2]
                 errores_sintacticos.append(
                    f"x error de sintaxis: falta '}}' antes de declarar nueva funcion (linea {tok.lineno}).\n"
                    f"  -> Bloque abierto en linea {top_line} sigue activo."
                 )
                 # No popeamos aquí para dejar que el stack siga sucio y ver si hay mas errores
        elif tok.type in ['SI', 'MIENTRAS', 'PARA']:
            pending_context = 'BLOCK'

        # --- 1. REGLA DE ORO: LOOKAHEAD '} FIN' MULTIPLE ---
        # Si vemos '} FIN', esta llave cierra el INICIO. 
        # Todo lo que esté en medio (Funciones, Ifs) se quedó abierto.
        if tok.type == 'LLAVE_C':
            siguiente = tokens_list[i+1] if i+1 < len(tokens_list) else None
            
            if siguiente and siguiente.type == 'FIN':
                # Revisamos la pila hacia atrás y reportamos TODO lo que no sea ROOT
                while stack and stack[-1][4] != 'ROOT':
                    top_open, top_close, top_line, top_col, top_ctx = stack.pop()
                    
                    simbolo = vis.get(top_open)
                    errores_sintacticos.append(
                        f"x error de sintaxis: falta '}}' para cerrar el bloque '{simbolo}' iniciado en linea {top_line}.\n"
                      #  f"  -> Se encontro '}} FIN', que cierra el programa, dejando este bloque interno abierto.\n"
                        #f"{_contexto_manual(codigo, tok.lineno, col)}"
                    )
                # Al terminar el while, el stack tiene [ROOT] (o está vacío),
                # así que el flujo normal cerrará el INICIO correctamente.

        # --- 2. REGLA DEL PUNTO Y COMA ---
        if tok.type == 'PUNTOCOMA':
            for idx in range(len(stack) - 1, -1, -1):
                if stack[idx][0] in ['PARENTESIS_A', 'CORCHETE_A']:
                    top_line = stack[idx][2]
                    simbolo = vis.get(stack[idx][0])
                    errores_sintacticos.append(
                        f"x error de sintaxis: falta cerrar '{vis.get(stack[idx][1])}' en esta linea.\n"
                        f"  -> Se encontro ';' pero sigue abierto un '{simbolo}' de linea {top_line}.\n"
                        f"{_contexto_manual(codigo, tok.lineno, col)}"
                    )
                    return

        # --- 3. APILADO ---
        if tok.type in aperturas:
            current_ctx = pending_context if tok.type == 'LLAVE_A' else 'NEUTRAL'
            stack.append((tok.type, aperturas[tok.type], tok.lineno, col, current_ctx))
            if tok.type == 'LLAVE_A': pending_context = 'BLOCK'
            continue

        # --- 4. DESAPILADO NORMAL ---
        if tok.type in cierres:
            if not stack:
                errores_sintacticos.append(
                    f"x error de sintaxis: '{vis.get(tok.type)}' inesperado sin apertura.\n"
                    f"{_contexto_manual(codigo, tok.lineno, col)}"
                )
                continue

            top_open, top_close, top_line, top_col, ctx = stack[-1]
            if tok.type != top_close:
                errores_sintacticos.append(
                    f"x error de sintaxis: se esperaba '{vis.get(top_close)}' pero se encontro '{vis.get(tok.type)}'.\n"
                    f"  -> Bloque abierto en linea {top_line}."
                )
                return
            stack.pop()

    # --- 5. CHECK FINAL (SI FALTAN LLAVES AL FINAL) ---
    # Si al acabar el archivo (llegar a FIN) todavía hay cosas en la pila...
    while stack:
        top_open, top_close, top_line, top_col, ctx = stack.pop()
        # Reportamos cada uno
        errores_sintacticos.append(
            f"x error de sintaxis: Bloque no cerrado al final del archivo.\n"
            f"  -> Falta '{vis.get(top_close)}' para cerrar bloque de linea {top_line}."
        )


# ------------------------ lexer proxy (pushback) ------------------------

class LexerProxy:
    def __init__(self, base_lexer):
        self.base = base_lexer
        self._buf = []

    def input(self, data):
        self._buf.clear()
        return self.base.input(data)

    @property
    def lineno(self):
        return self.base.lineno

    @lineno.setter
    def lineno(self, v):
        self.base.lineno = v

    def token(self):
        if self._buf:
            return self._buf.pop()
        return self.base.token()

    def push_token(self, tok):
        if tok is not None:
            self._buf.append(tok)

    def __getattr__(self, name):
        return getattr(self.base, name)


# ------------------------ reglas del parser ------------------------

def p_programa(p):
    "programa : INICIO bloque_codigo FIN"
    p[0] = NodoAST("programa", [p[2]])

# permite INICIO mal escrito (ej. INICI), reporta y sigue
def p_programa_inicio_mal(p):
    "programa : ID bloque_codigo FIN"
    if str(p[1]).lower() != "inicio":
        errores_sintacticos.append(
            f"x error de sintaxis: se esperaba 'inicio' pero se encontro '{p[1]}' (linea {p.lineno(1)})"
        )
    p[0] = NodoAST("programa", [p[2]])

def p_bloque_codigo(p):
    """bloque_codigo : LLAVE_A lista_declaraciones LLAVE_C
                     | LLAVE_A lista_declaraciones error"""
    if len(p) == 4 and p[3] == '}':
        # Caso correcto
        p[0] = NodoAST("bloque", p[2])
    else:
        # Caso de error (recuperación)
        mensaje = f"x error de sintaxis: Bloque no cerrado. Falta '}}' para cerrar el bloque iniciado en linea {p.lineno(1)}"
        errores_sintacticos.append(mensaje)
        p[0] = NodoAST("bloque_incompleto", p[2])
        parser.errok() # <--- IMPORTANTE: Resetea el estado de error para seguir analizando

def p_lista_declaraciones(p):
    """lista_declaraciones : lista_declaraciones declaracion
                           | lista_declaraciones control
                           | lista_declaraciones dispositivo
                           | lista_declaraciones funcion
                           | declaracion
                           | control
                           | dispositivo
                           | funcion"""
    if DEBUG:
        print(">> lista_declaraciones")
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[2]]

def p_imprimir(p):
    "declaracion : IMPRIMIR PARENTESIS_A expresion PARENTESIS_B PUNTOCOMA"
    p[0] = NodoAST("imprimir", [p[3]])

def p_retraso(p):
    "declaracion : RETRASO PARENTESIS_A expresion PARENTESIS_B PUNTOCOMA"
    p[0] = NodoAST("retraso", [p[3]])

def p_declaracion_variable(p):
    """declaracion : tipo ID PUNTOCOMA
                   | tipo ID ASIGNACION expresion PUNTOCOMA
                   | tipo ID CORCHETE_A NUMERO CORCHETE_B PUNTOCOMA
                   | ID CORCHETE_A NUMERO CORCHETE_B ASIGNACION expresion PUNTOCOMA"""
    nodo = NodoAST("declaracion")
    for elem in p[1:]:
        if isinstance(elem, NodoAST):
            nodo.agregar_hijo(elem)
        else:
            nodo.agregar_hijo(NodoAST(str(elem)))
    p[0] = nodo

# ✅ maneja: entero x = ;  (evita cascada)
def p_declaracion_asignacion_sin_expresion(p):
    "declaracion : tipo ID ASIGNACION error PUNTOCOMA"
    p[0] = NodoAST("declaracion_error")

def p_llamada_funcion(p):
    "declaracion : ID PARENTESIS_A argumentos PARENTESIS_B PUNTOCOMA"
    p[0] = NodoAST("llamada_funcion", [NodoAST(p[1]), NodoAST("argumentos", p[3])])

def p_tipo(p):
    """tipo : ENTERO
            | REAL_TIPO
            | BOOLEANO
            | CADENA_TIPO"""
    p[0] = NodoAST(p[1])

def p_control(p):
    """control : si
               | mientras
               | para
               | romper"""
    p[0] = p[1]

def p_si(p):
    """si : SI PARENTESIS_A expresion PARENTESIS_B bloque_codigo
          | SI PARENTESIS_A expresion PARENTESIS_B bloque_codigo ID bloque_codigo"""
    if len(p) == 6:
        p[0] = NodoAST("si", [p[3], p[5]])
    else:
        # aquí ID normalmente es "sino"
        if str(p[6]).lower() != "sino":
            errores_sintacticos.append(
                f"x error de sintaxis: se esperaba 'sino' pero se encontro '{p[6]}' (linea {p.lineno(6)})"
            )
        p[0] = NodoAST("si", [p[3], p[5], NodoAST("sino"), p[7]])

def p_mientras(p):
    "mientras : MIENTRAS PARENTESIS_A expresion PARENTESIS_B bloque_codigo"
    p[0] = NodoAST("mientras", [p[3], p[5]])

def p_para(p):
    "para : PARA PARENTESIS_A asignacion_para PUNTOCOMA expresion PUNTOCOMA actualizacion_para PARENTESIS_B bloque_codigo"
    p[0] = NodoAST("para", [p[3], p[5], p[7], p[9]])

def p_asignacion_para(p):
    """asignacion_para : tipo ID ASIGNACION expresion
                       | ID ASIGNACION expresion"""
    p[0] = NodoAST("asignacion_para", [NodoAST(str(e)) for e in p[1:]])

def p_actualizacion_para(p):
    """actualizacion_para : ID ASIGNACION expresion
                          | ID MASMAS
                          | ID MENOSMENOS"""
    p[0] = NodoAST("actualizacion_para", [NodoAST(str(e)) for e in p[1:]])

def p_funcion(p):
    "funcion : FUNC ID PARENTESIS_A parametros PARENTESIS_B bloque_codigo"
    p[0] = NodoAST("funcion", [NodoAST(p[2]), NodoAST("parametros", p[4]), p[6]])

def p_parametros(p):
    """parametros : parametro
                  | parametro COMA parametros
                  | empty"""
    if len(p) == 2:
        p[0] = [p[1]] if p[1] else []
    else:
        p[0] = [p[1]] + p[3]

def p_parametro(p):
    "parametro : tipo ID"
    p[0] = NodoAST("parametro", [p[1], NodoAST(p[2])])

def p_dispositivo(p):
    """dispositivo : definir_dispositivo
                   | accion_dispositivo"""
    p[0] = p[1]

def p_tipo_dispositivo(p):
    """tipo_dispositivo : SERVO
                        | LED
                        | MOTOR
                        | SENSOR
                        | BUZZER
                        | SENSOR_ULTRASONICO
                        | SENSOR_COLOR
                        | SENSOR_TOQUE
                        | SENSOR_GIRO
                        | RCX
                        | NXT
                        | EV3
                        | HUB_SPIKE_PRIME
                        | HUB_SPIKE_ESSENTIAL
                        | HUB_ROBOT_INVENTOR
                        | HUB_TECHNIC_LARGE
                        | HUB_POWERED_UP
                        | MOTOR_SERVO_GRANDE_EV3
                        | MOTOR_SERVO_MEDIANO_EV3
                        | SERVOMOTOR_NXT
                        | MOTOR_ANGULAR_GRANDE
                        | MOTOR_ANGULAR_MEDIANO
                        | MOTOR_POWERED_UP_BOOST
                        | MOTOR_POWERED_UP
                        | MOTOR_BOOST"""
    p[0] = NodoAST(p[1])

def p_definir_dispositivo(p):
    "definir_dispositivo : tipo_dispositivo ID ASIGNACION objeto_dispositivo PUNTOCOMA"
    p[0] = NodoAST("dispositivo", [p[1], NodoAST(p[2]), p[4]])

def p_objeto_dispositivo(p):
    "objeto_dispositivo : LLAVE_A lista_atributos LLAVE_C"
    p[0] = NodoAST("atributos", p[2])

def p_lista_atributos(p):
    """lista_atributos : lista_atributos COMA atributo
                       | atributo"""
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]

def p_atributo(p):
    "atributo : ID ASIGNACION expresion"
    p[0] = NodoAST("atributo", [NodoAST(p[1]), p[3]])

def p_accion_dispositivo(p):
    "accion_dispositivo : ID FLECHA accion PARENTESIS_A expresion_opt PARENTESIS_B PUNTOCOMA"
    p[0] = NodoAST("accion_dispositivo", [NodoAST(p[1]), NodoAST(p[3]), p[5] if p[5] else NodoAST("vacio")])

def p_accion(p):
    """accion : ENCENDER
              | APAGAR
              | VALOR
              | GIRARSERVO
              | GIRARMOTOR"""
    p[0] = p[1]

def p_expresion_opt(p):
    """expresion_opt : expresion
                     | empty"""
    p[0] = p[1]

def p_expresion_binaria(p):
    "expresion : expresion op_binario expresion"
    p[0] = NodoAST("binop", [p[1], NodoAST(p[2]), p[3]])

def p_expresion_unaria(p):
    "expresion : op_unario expresion"
    p[0] = NodoAST("unop", [NodoAST(p[1]), p[2]])

def p_expresion_grupo(p):
    "expresion : PARENTESIS_A expresion PARENTESIS_B"
    p[0] = p[2]

def p_expresion_valor_dispositivo(p):
    "expresion : ID FLECHA VALOR PARENTESIS_A expresion_opt PARENTESIS_B"
    arg = p[5] if p[5] else NodoAST("vacio")
    p[0] = NodoAST("valor_dispositivo", [NodoAST(p[1]), arg])

def p_expresion_termino(p):
    """expresion : ID
                 | ID CORCHETE_A NUMERO CORCHETE_B
                 | NUMERO
                 | REAL
                 | CADENA_TEXTO
                 | TRUE
                 | FALSE"""
    if len(p) == 2:
        p[0] = NodoAST("constante", [NodoAST(str(p[1]))])
    else:
        p[0] = NodoAST("arreglo", [NodoAST(p[1]), NodoAST(str(p[3]))])

def p_argumentos(p):
    """argumentos : expresion
                  | expresion COMA argumentos
                  | empty"""
    if len(p) == 2:
        p[0] = [p[1]] if p[1] else []
    else:
        p[0] = [p[1]] + p[3]

def p_op_binario(p):
    """op_binario : SUMA
                  | RESTA
                  | MULTIPLICACION
                  | DIVISION
                  | MODULO
                  | IGUAL
                  | DIFERENTE
                  | MENORQUE
                  | MAYORQUE
                  | MENORIGUAL
                  | MAYORIGUAL
                  | AND
                  | OR"""
    p[0] = p[1]

def p_op_unario(p):
    """op_unario : NOT
                 | RESTA"""
    p[0] = p[1]

def p_romper(p):
    "romper : ROMPER PUNTOCOMA"
    p[0] = NodoAST("romper")

def p_empty(p):
    "empty :"
    p[0] = None


# ------------------------ error handler (anti cascada + panico) ------------------------

def _token_fake(tipo: str, valor: str, lineno: int, lexpos: int):
    tok = LexToken()
    tok.type = tipo
    tok.value = valor
    tok.lineno = lineno
    tok.lexpos = lexpos
    return tok

def _panic_sync():
    """
    descarta tokens hasta uno de sincronización.
    """
    sync = {"PUNTOCOMA", "LLAVE_C", "FIN"}
    tok = parser.token()
    while tok and tok.type not in sync:
        tok = parser.token()
    parser.errok()

def p_error(t):
    global _codigo_actual, _lexer_actual

    if len(errores_sintacticos) >= MAX_ERRORES_SINTACTICOS:
        return

    if not t:
        errores_sintacticos.append(
            "x error de sintaxis: fin de archivo inesperado (posible falta de '}' o ')')"
        )
        return

    # 1 error por línea
    if t.lineno in _lineas_con_error:
        _panic_sync()
        return
    _lineas_con_error.add(t.lineno)

    col = _columna_desde_lexpos(_codigo_actual, t.lexpos)
    ctx = _contexto_manual(_codigo_actual, t.lineno, col)

    # caso: INICIO mal escrito al inicio (ej INICI)
    if t.lineno == 1 and t.type == "ID":
        sug = _sugerencia_reservada(str(t.value))
        if sug == "inicio":
            errores_sintacticos.append(
                f"x error de sintaxis: se esperaba 'inicio' pero se encontro '{t.value}' "
                f"(linea {t.lineno}, columna {col})\n{ctx}\n  -> ¿quisiste decir 'inicio'?"
            )
            # forzamos a continuar como si hubiera sido INICIO
            return _token_fake("INICIO", "inicio", t.lineno, t.lexpos)

    mensaje = (
        f"x error de sintaxis en '{t.value}' (token {t.type}) "
        f"(linea {t.lineno}, columna {col})\n{ctx}"
    )

    # sugerencia de reservadas si era ID
    if t.type == "ID":
        sug = _sugerencia_reservada(str(t.value))
        if sug:
            mensaje += f"\n  -> palabra reservada no reconocida. ¿quisiste decir '{sug}'?"

    # si el token actual es ';' y antes hay '=' => "entero x = ;"
    if t.type == "PUNTOCOMA":
        ch_prev = _char_anterior_no_espacio(_codigo_actual, t.lexpos)
        if ch_prev == "=":
            mensaje += "\n  -> falta una expresion despues de '=' (no puedes dejar la asignacion vacia)"
            errores_sintacticos.append(mensaje)

            # recupera: inventa un NUMERO 0 antes del ';'
            if _lexer_actual is not None:
                _lexer_actual.push_token(t)
            return _token_fake("NUMERO", 0, t.lineno, t.lexpos)

    # detecta posible falta de ';' antes de nueva sentencia (y lo inserta)
    inicios_sentencia = {
        "ENTERO", "REAL_TIPO", "BOOLEANO", "CADENA_TIPO",
        "FUNC", "SI", "MIENTRAS", "PARA", "IMPRIMIR", "RETRASO",
        "SERVO", "LED", "MOTOR", "SENSOR", "BUZZER",
        "ID",
        "LLAVE_C",
        "FIN",
    }

    if t.type in inicios_sentencia:
        mensaje += "\n  -> posible falta de ';' al final de la linea anterior"
        errores_sintacticos.append(mensaje)

        # inserta ';' y vuelve a procesar el token real
        if _lexer_actual is not None and t.type not in {"LLAVE_C", "FIN"}:
            _lexer_actual.push_token(t)
            return _token_fake("PUNTOCOMA", ";", t.lineno, t.lexpos)

        # si es cierre de bloque o fin, solo intenta sincronizar
        parser.errok()
        return

    errores_sintacticos.append(mensaje)
    
    if t and t.type == 'FIN':
        return
    _panic_sync()

# ------------------------ construir parser ------------------------

def construir_parser():
    # si te da broncas con parsetab viejo, bórralo y se regenera
    return yacc.yacc(write_tables=True, start="programa")

parser = construir_parser()


# ------------------------ API ------------------------
def _linea_de_error(msg: str):
    import re
    m = re.search(r"linea\s+(\d+)", msg)
    return int(m.group(1)) if m else None

def validar_aperturas_bloque(codigo: str):
    """
    Revisa que despues de FUNC, SI, MIENTRAS, PARA, exista una LLAVE_A '{'.
    Si no esta, marca error exactamente en esa linea.
    """
    lexer.lineno = 1
    lexer.input(codigo)
    
    # Obtenemos todos los tokens en una lista para poder "mirar adelante"
    tokens_list = list(iter(lexer.token, None))
    
    n = len(tokens_list)
    i = 0
    
    while i < n:
        tok = tokens_list[i]
        
        # Palabras clave que REQUIEREN bloque { ... }
        if tok.type in ['FUNC', 'SI', 'MIENTRAS', 'PARA']:
            
            # 1. Buscamos donde termina el parentesis de los parametros/condicion
            # Para FUNC es: FUNC -> ID -> ( ... ) -> {
            # Para SI/MIENTRAS es: SI -> ( ... ) -> {
            
            j = i + 1
            
            # Caso especial FUNC: saltamos el ID del nombre
            if tok.type == 'FUNC':
                if j < n and tokens_list[j].type == 'ID':
                    j += 1
            
            # Ahora deberiamos estar en el '('
            if j < n and tokens_list[j].type == 'PARENTESIS_A':
                balance = 1
                j += 1
                while j < n and balance > 0:
                    if tokens_list[j].type == 'PARENTESIS_A':
                        balance += 1
                    elif tokens_list[j].type == 'PARENTESIS_B':
                        balance -= 1
                    j += 1
                
                # Al salir del while, 'j' apunta al token DESPUES del cierre ')'
                # AQUI ES DONDE OCURRE LA MAGIA:
                if j < n:
                    siguiente = tokens_list[j]
                    if siguiente.type != 'LLAVE_A':
                        col = _columna_desde_lexpos(codigo, tok.lexpos) # Usamos la pos del inicio (FUNC/SI)
                        
                        # Reportamos el error CLARAMENTE
                        errores_sintacticos.append(
                            f"x error de sintaxis: falta abrir llave '{{' para el bloque de '{tok.value}'.\n"
                            f"  -> La declaracion termina en linea {tokens_list[j-1].lineno}, pero no abriste el bloque.\n"
                            f"{_contexto_manual(codigo, tokens_list[j-1].lineno, 1)}"
                        )
                        return True # Hubo error
            
        i += 1
        
    return False # No hubo errores de apertura


def parsear_codigo(codigo_fuente: str):
    global _codigo_actual, _lexer_actual

    _codigo_actual = codigo_fuente
    errores_sintacticos.clear()
    _lineas_con_error.clear()

    # --- PASO 0: Chequeo de aperturas obligatorias (NUEVO) ---
    # Esto detecta si pusiste 'funcion mover()' y olvidaste el '{'
    if validar_aperturas_bloque(codigo_fuente):
        return None

    # --- PASO 1: Prechequeo de cierres (El que ya teniamos) ---
    prechecar_delimitadores(codigo_fuente)
    if errores_sintacticos:
        return None

    # --- PASO 2: Parseo normal ---
    lx = LexerProxy(lexer)
    _lexer_actual = lx
    lx.lineno = 1
    lx.input(codigo_fuente)

    resultado = parser.parse(codigo_fuente, lexer=lx)

    if resultado:
        try:
            graficar_arbol(resultado, "arbol_sintactico")
        except Exception:
            pass

    return resultado