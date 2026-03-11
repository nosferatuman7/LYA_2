import ply.lex as lex
import re

# ------------------------ LÉXICO ------------------------

palabras_reservadas = {
    'INICIO': 'INICIO',
    'inicio': 'INICIO',
    'FIN': 'FIN',
    'fin': 'FIN',

    'entero': 'ENTERO',
    'real': 'REAL_TIPO',
    'booleano': 'BOOLEANO',
    'cadena': 'CADENA_TIPO',
    'si': 'SI',
    'mientras': 'MIENTRAS',
    'para': 'PARA',
    'funcion': 'FUNC',
    'retornar': 'RETORNAR',

    # dispositivos base
    'servo': 'SERVO',
    'led': 'LED',
    'motor': 'MOTOR',
    'sensor': 'SENSOR',

    # lego robotics
    'buzzer': 'BUZZER',
    'sensor_ultrasonico': 'SENSOR_ULTRASONICO',
    'sensor_color': 'SENSOR_COLOR',
    'sensor_toque': 'SENSOR_TOQUE',
    'sensor_giro': 'SENSOR_GIRO',

    # acciones / otros
    'encender': 'ENCENDER',
    'apagar': 'APAGAR',
    'valor': 'VALOR',
    'girarServo': 'GIRARSERVO',
    'girarMotor': 'GIRARMOTOR',
    'imprimir': 'IMPRIMIR',
    'retraso': 'RETRASO',
    'romper': 'ROMPER',
    'True': 'TRUE',
    'False': 'FALSE',

    # hubs / unidades de control (lego robotics)
    'rcx': 'RCX',
    'nxt': 'NXT',
    'ev3': 'EV3',
    'hub_spike_prime': 'HUB_SPIKE_PRIME',
    'hub_spike_essential': 'HUB_SPIKE_ESSENTIAL',
    'hub_robot_inventor': 'HUB_ROBOT_INVENTOR',
    'hub_technic_large': 'HUB_TECHNIC_LARGE',
    'hub_powered_up': 'HUB_POWERED_UP',

    # motores (lego robotics)
    'motor_servo_grande_ev3': 'MOTOR_SERVO_GRANDE_EV3',
    'motor_servo_mediano_ev3': 'MOTOR_SERVO_MEDIANO_EV3',
    'servomotor_nxt': 'SERVOMOTOR_NXT',
    'motor_angular_grande': 'MOTOR_ANGULAR_GRANDE',
    'motor_angular_mediano': 'MOTOR_ANGULAR_MEDIANO',
    'motor_powered_up_boost': 'MOTOR_POWERED_UP_BOOST',
    'motor_powered_up': 'MOTOR_POWERED_UP',
    'motor_boost': 'MOTOR_BOOST',
    'func': 'FUNC',
    'sino': 'SINO',
    'true': 'TRUE',
    'false': 'FALSE',
    'girarmotor': 'GIRARMOTOR',
    'girarservo': 'GIRARSERVO',
    'and': 'AND',
    'or': 'OR',
    'not': 'NOT',
}

tokens = [
    'ID', 'NUMERO', 'REAL', 'CADENA_TEXTO', 'LLAVE_A', 'LLAVE_C',
    'PARENTESIS_A', 'PARENTESIS_B',
    'CORCHETE_A', 'CORCHETE_B', 'PUNTOCOMA', 'COMA', 'FLECHA',
    'ASIGNACION', 'SUMA', 'RESTA', 'MULTIPLICACION', 'DIVISION',
    'MODULO', 'IGUAL', 'DIFERENTE', 'MENORQUE', 'MAYORQUE',
    'MENORIGUAL', 'MAYORIGUAL', 'AND', 'OR', 'NOT', 'MASMAS', 'MENOSMENOS'
] + list(set(palabras_reservadas.values()))
# usamos set(...) para que INICIO y FIN no se repitan y desaparezca el warning

# Tokens simples
t_MASMAS = r'\+\+'
t_MENOSMENOS = r'--'
t_IGUAL = r'=='
t_DIFERENTE = r'!='
t_MENORIGUAL = r'<='
t_MAYORIGUAL = r'>='
t_AND = r'&&'
t_OR = r'\|\|'
t_FLECHA = r'->'
t_SUMA = r'\+'
t_RESTA = r'-'
t_MULTIPLICACION = r'\*'
t_DIVISION = r'/'
t_MODULO = r'%'
t_ASIGNACION = r'='
t_MENORQUE = r'<'
t_MAYORQUE = r'>'
t_NOT = r'!'
t_LLAVE_A = r'\{'
t_LLAVE_C = r'\}'
t_PARENTESIS_A = r'\('
t_PARENTESIS_B = r'\)'
t_CORCHETE_A = r'\['
t_CORCHETE_B = r'\]'
t_PUNTOCOMA = r';'
t_COMA = r','
t_ignore = ' \t'

# comentarios de una sola linea
def t_comentario_linea(t):
    r'//[^\n]*'
    pass

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# ------------------------ helpers de errores lexicos ------------------------

errores_lexicos = []

def encontrar_columna(lexer, token):
    linea_inicio = lexer.lexdata.rfind('\n', 0, token.lexpos)
    if linea_inicio < 0:
        linea_inicio = -1
    return token.lexpos - linea_inicio

def obtener_linea(lexer, lexpos):
    data = lexer.lexdata
    ini = data.rfind('\n', 0, lexpos)
    ini = 0 if ini < 0 else ini + 1
    fin = data.find('\n', lexpos)
    fin = len(data) if fin < 0 else fin
    return data[ini:fin]

def puntero(columna):
    return (' ' * max(columna - 1, 0)) + '^'

def registrar_error_lexico(token, mensaje, lexema=None):
    col = encontrar_columna(token.lexer, token)
    linea = obtener_linea(token.lexer, token.lexpos)
    frag = token.value if lexema is None else lexema
    errores_lexicos.append(
        "x error lexico: " + mensaje +
        f" (linea {token.lineno}, columna {col})" +
        (f" [lexema: {frag!r}]" if frag is not None else "") +
        "\n    " + linea +
        "\n    " + puntero(col)
    )

def formatear_contexto(lexer, token):
    """
    Devuelve el contexto donde ocurrió el error (línea y columna).
    """
    linea = obtener_linea(lexer, token.lexpos)
    columna = encontrar_columna(lexer, token)
    caret = " " * max(columna - 1, 0) + "^"
    return f"    {linea}\n    {caret}"


# ------------------------ tokens compuestos ------------------------

def t_CADENA_TEXTO(t):
    r'"([^"\\\n]|\\.)*"'
    # quitamos las comillas
    t.value = t.value[1:-1]
    return t

def t_REAL(t):
    r'\d+(?:\.\d+)+'
    # si trae mas de un punto: 12.3.4 => error lexico (no lo partimos en 3 tokens)
    if t.value.count('.') != 1:
        registrar_error_lexico(t, "numero real mal formado: demasiados puntos decimales", lexema=t.value)
        return None
    t.value = float(t.value)
    return t

def t_NUMERO(t):
    r'\d+'
    # si despues del numero viene una letra/_, es un identificador invalido (ej: 10abc)
    data = t.lexer.lexdata
    pos_sig = t.lexpos + len(t.value)
    if pos_sig < len(data) and re.match(r'[a-zA-Z_]', data[pos_sig]):
        j = pos_sig
        while j < len(data) and re.match(r'[a-zA-Z0-9_]', data[j]):
            j += 1
        lexema = data[t.lexpos:j]
        registrar_error_lexico(t, "identificador invalido: no puede iniciar con numero", lexema=lexema)
        t.lexer.lexpos = j
        return None

    t.value = int(t.value)
    return t

def t_ID(t):
    # capturamos un bloque "tipo identificador" hasta un delimitador
    r'[a-zA-Z_][^\s;,\=\+\-\*\/%<>\!\{\}\(\)\[\]\.:\"\\\']*'

    # valido: letras, numeros y '_' (y no iniciar con numero)
    if re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', t.value):
        t.type = palabras_reservadas.get(t.value, palabras_reservadas.get(t.value.lower(), 'ID'))
        return t

    # invalido: trae caracteres raros (ej: servo$1, pin#, motor-1)
    registrar_error_lexico(
        t,
        "identificador invalido: contiene caracteres no permitidos (usa solo letras, numeros y '_')",
        lexema=t.value
    )
    return None

def t_error(t):
    # cadena no cerrada: empieza con " pero no hay cierre antes de salto de linea / eof
    if t.value and t.value[0] == '"':
        data = t.lexer.lexdata
        ini = t.lexpos
        fin = data.find('\n', ini)
        if fin == -1:
            fin = len(data)
        lexema = data[ini:fin]
        registrar_error_lexico(t, "cadena no cerrada: falta comilla doble de cierre (\")", lexema=lexema)
        t.lexer.skip(len(lexema))
        return

    # cualquier otro caracter ilegal
    registrar_error_lexico(t, "caracter no reconocido", lexema=t.value[0])
    t.lexer.skip(1)

# ------------------------ lexer ------------------------

lexer = lex.lex()

# ------------------------ tabla de simbolos (se usa en el main/gui) ------------------------

tabla_simbolos = []

def agregar_a_tabla_simbolos(nombre, tipo, valor, linea, columna):
    for simbolo in tabla_simbolos:
        if simbolo['nombre'] == nombre:
            return
    tabla_simbolos.append({
        'nombre': nombre,
        'tipo': tipo,
        'valor': valor,
        'linea': linea,
        'columna': columna
    })

# (se mantiene por compatibilidad con tu proyecto)
errores_sintacticos = []
