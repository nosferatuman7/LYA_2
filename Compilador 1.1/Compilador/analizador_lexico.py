from analizador_semantico import AnalizadorSemantico
from generador_codigo_intermedio import GeneradorCodigoIntermedio
from interprete import Interprete
from generador_codigo_objeto import GeneradorCodigoObjeto

from lexer import (
    tokens,
    lexer,
    errores_lexicos,
    palabras_reservadas,
    tabla_simbolos,
    agregar_a_tabla_simbolos,
    encontrar_columna,
)

from analizador_sintactico import (
    parser,
    parsear_codigo,
    errores_sintacticos,
)

import tkinter as tk
from tkinter import scrolledtext
import re
import os
import difflib
from ply.lex import LexToken

# guarda el ultimo codigo objeto generado (para el boton "ver codigo objeto")
ultimo_codigo_objeto = ""
ruta_codigo_objeto = ""

# ------------------------ listas de errores ------------------------

errores_semanticos = []
avisos_lexicos = []

# ------------------------ helpers de salida ------------------------

def imprimir_en_lenguaje(texto):
    """
    escribe en la 'consola de ejecucion' de tu lenguaje.
    """
    salida_ejecucion.insert(tk.END, str(texto) + "\n")
    salida_ejecucion.see(tk.END)


# ------------------------ interfaz y procesamiento ------------------------

def extraer_contenido(codigo):
    patron = re.compile(r'^\s*inicio\s*\{\s*(.*?)\s*\}\s*fin\s*$', re.DOTALL | re.IGNORECASE)
    match = patron.match(codigo)
    return match.group(1).strip() if match else None


def analizar_codigo():
    codigo = editor_text.get("1.0", tk.END).strip()

    # limpiamos ambas salidas
    salida_analizador.delete("1.0", tk.END)
    salida_ejecucion.delete("1.0", tk.END)

    # limpiar estructuras globales
    errores_lexicos.clear()
    errores_sintacticos.clear()
    errores_semanticos.clear()
    avisos_lexicos.clear()
    tabla_simbolos.clear()

    contenido = codigo

    # 1. analisis lexico
    salida_analizador.insert(tk.END, "--- tokens ---\n")
    procesar_funciones(contenido)
    tokens_para_tabla = clonar_tokens(contenido)
    procesar_tokens(tokens_para_tabla)

    # 2. analisis sintactico
    resultado = None
    salida_analizador.insert(tk.END, "\n--- arbol sintactico ---\n")
    try:
        lexer.lineno = 1
        lexer.input(contenido)
        resultado = parsear_codigo(contenido)
        if resultado:
            salida_analizador.insert(tk.END, f"{resultado}\n")
        else:
            salida_analizador.insert(tk.END, "no se pudo construir el arbol sintactico debido a errores\n")
    except Exception as e:
        # no agregamos mensajes extra: p_error ya registró el error principal
        salida_analizador.insert(tk.END, f"x error durante el analisis sintactico: {e}\n")

    # 3. errores sintacticos
    if errores_sintacticos:
        salida_analizador.insert(tk.END, "\n--- errores sintacticos ---\n")
        for error in errores_sintacticos:
            salida_analizador.insert(tk.END, f"{error}\n")

    # 4. verificacion semantica real sobre el ast
    if resultado and not errores_lexicos and not errores_sintacticos:
        try:
            sem = AnalizadorSemantico()
            errores_semanticos.extend(sem.analizar(resultado))

            # reemplazamos la tabla generada de forma aproximada por la tabla semantica real
            tabla_simbolos.clear()
            for simbolo in sem.tabla_simbolos:
                tabla_simbolos.append({
                    "nombre": simbolo.get("nombre"),
                    "tipo": simbolo.get("tipo"),
                    "valor": simbolo.get("valor"),
                    "linea": simbolo.get("linea"),
                    "columna": simbolo.get("columna"),
                    "clase": simbolo.get("clase"),
                    "ambito": simbolo.get("ambito"),
                    "tam": simbolo.get("tam"),
                })
        except Exception as e:
            errores_semanticos.append(f"x error semantico: fallo interno al ejecutar el analizador semantico: {e}")

    # 5. mostrar errores + tabla de simbolos
    mostrar_resultados()

    # 5.5 generacion de codigo intermedio (TAC) solo si no hay errores
    if resultado and not errores_lexicos and not errores_sintacticos and not errores_semanticos:
        try:
            gen = GeneradorCodigoIntermedio()
            gen.generar(resultado)
            codigo_tac = gen.obtener_codigo()
            salida_analizador.insert(tk.END, "--- codigo intermedio (TAC) ---")
            salida_analizador.insert(tk.END, codigo_tac + "")
        except Exception as e:
            salida_analizador.insert(tk.END, f"--- codigo intermedio (TAC) --- x error al generar codigo intermedio: {e}")

    # 6. ejecutar el programa con el INTERPRETE real (sobre el AST)
    if resultado and not errores_lexicos and not errores_sintacticos and not errores_semanticos:
        try:
            salida_ejecucion.insert(tk.END, "=== ejecucion del programa ===\n")
            interprete = Interprete(salida=imprimir_en_lenguaje, max_iteraciones=1000)
            interprete.ejecutar(resultado)
            salida_ejecucion.insert(tk.END, "=== fin de la ejecucion ===\n")
        except Exception as e:
            salida_ejecucion.insert(tk.END, f"x error al ejecutar el programa: {e}\n")

    # 7. GENERACION DE CODIGO OBJETO (Python / Raspberry Pi)
    if resultado and not errores_lexicos and not errores_sintacticos and not errores_semanticos:
        global ultimo_codigo_objeto, ruta_codigo_objeto
        try:
            gen_obj = GeneradorCodigoObjeto()
            ultimo_codigo_objeto = gen_obj.generar(resultado)

            ruta_codigo_objeto = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "codigo_objeto_generado.py"
            )
            with open(ruta_codigo_objeto, "w", encoding="utf-8") as f:
                f.write(ultimo_codigo_objeto)

            salida_analizador.insert(tk.END, "\n--- codigo objeto (Python / Raspberry Pi) ---\n")
            salida_analizador.insert(tk.END, ultimo_codigo_objeto + "\n")
            salida_analizador.insert(tk.END, f"[guardado en: {ruta_codigo_objeto}]\n")
        except Exception as e:
            salida_analizador.insert(tk.END, f"\n--- codigo objeto --- x error al generar: {e}\n")


# --------- logica de tokens / tabla de simbolos ---------

def procesar_funciones(contenido):
    patron_funcion = re.compile(r'(?:funcion|func)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)')
    for match in patron_funcion.finditer(contenido):
        nombre = match.group(1)
        params = match.group(2).strip()
        lista_params = [p.strip() for p in params.split(',')] if params else []
        linea = contenido[:match.start()].count('\n') + 1
        columna = match.start() - contenido.rfind('\n', 0, match.start())
        agregar_a_tabla_simbolos(nombre, 'funcion', lista_params, linea, columna)


def clonar_tokens(codigo):
    lexer.lineno = 1
    lexer.input(codigo)
    return list(iter(lexer.token, None))


def procesar_tokens(lista_de_tokens):

    tipos_declaracion = {
        'ENTERO', 'REAL_TIPO', 'BOOLEANO', 'CADENA_TIPO',
        'SERVO', 'LED', 'MOTOR', 'SENSOR',
        'BUZZER', 'SENSOR_ULTRASONICO', 'SENSOR_COLOR',
        'SENSOR_TOQUE', 'SENSOR_GIRO',
        'RCX','NXT','EV3',
        'HUB_SPIKE_PRIME','HUB_SPIKE_ESSENTIAL','HUB_ROBOT_INVENTOR','HUB_TECHNIC_LARGE','HUB_POWERED_UP',
        'MOTOR_SERVO_GRANDE_EV3','MOTOR_SERVO_MEDIANO_EV3','SERVOMOTOR_NXT',
        'MOTOR_ANGULAR_GRANDE','MOTOR_ANGULAR_MEDIANO',
        'MOTOR_POWERED_UP_BOOST','MOTOR_POWERED_UP','MOTOR_BOOST'
    }

    tokens_en_espera = []

    for tok in lista_de_tokens:
        columna = encontrar_columna(lexer, tok)
        salida_analizador.insert(
            tk.END,
            f"{tok.type} -> {tok.value} (linea {tok.lineno}, columna {columna})\n"
        )
        print(f"token: {tok.type} - {tok.value}")

        # sugerencia si el id se parece a una palabra reservada
        # sugerencias (avisos) si el id se parece a una palabra reservada
        if tok.type == 'ID':
            # 1) si este id es el nombre de una declaracion (ej: entero blanco = 55;)
            #    no sugerimos nada (porque es valido)
            en_declaracion = (
                bool(tokens_en_espera)
                and len(tokens_en_espera) == 1
                and tokens_en_espera[0][0].type in tipos_declaracion
            )

            # 2) si ya existe en la tabla de simbolos, tampoco sugerimos nada
            ya_declarado = any(s['nombre'] == tok.value for s in tabla_simbolos)

            if not en_declaracion and not ya_declarado:
                sugerencia = difflib.get_close_matches(
                    tok.value, palabras_reservadas.keys(), n=1, cutoff=0.7
                )
                if sugerencia:
                    avisos_lexicos.append(
                        f"~ aviso: identificador '{tok.value}' "
                        f"(linea {tok.lineno}, columna {columna}). "
                        f"¿quisiste decir '{sugerencia[0]}'?"
                    )

        # detectar inicio de declaracion
        if tok.type in tipos_declaracion:
            tokens_en_espera = [(tok, columna)]
 
        elif tokens_en_espera:
            tokens_en_espera.append((tok, columna))

        # al encontrar ';' procesamos la declaracion
        if tok.type == 'PUNTOCOMA' and tokens_en_espera:
            print(">>> tokens en espera:", [(t[0].type, t[0].value) for t in tokens_en_espera])
            manejar_declaracion(tokens_en_espera.copy())
            tokens_en_espera.clear()


def manejar_declaracion(tokens_en_espera):
    if len(tokens_en_espera) < 3:
        return

    t1, c1 = tokens_en_espera[0]
    t2, c2 = tokens_en_espera[1]

    tipos_validos = [
        'ENTERO', 'REAL_TIPO', 'BOOLEANO', 'CADENA_TIPO',
        'SERVO', 'LED', 'MOTOR', 'SENSOR',
        'BUZZER', 'SENSOR_ULTRASONICO', 'SENSOR_COLOR',
        'SENSOR_TOQUE', 'SENSOR_GIRO',
        'RCX','NXT','EV3',
        'HUB_SPIKE_PRIME','HUB_SPIKE_ESSENTIAL','HUB_ROBOT_INVENTOR','HUB_TECHNIC_LARGE','HUB_POWERED_UP',
        'MOTOR_SERVO_GRANDE_EV3','MOTOR_SERVO_MEDIANO_EV3','SERVOMOTOR_NXT',
        'MOTOR_ANGULAR_GRANDE','MOTOR_ANGULAR_MEDIANO',
        'MOTOR_POWERED_UP_BOOST','MOTOR_POWERED_UP','MOTOR_BOOST'

    ]

    if t1.type not in tipos_validos or t2.type != 'ID':
        return

    tipo = t1.type
    nombre = t2.value
    valor = None

    # si hay asignacion, tomamos el valor y validamos tipo de dato
    if len(tokens_en_espera) >= 5 and tokens_en_espera[2][0].type == 'ASIGNACION':
        valor_token = tokens_en_espera[3][0]
        valor_col = tokens_en_espera[3][1]
        valor = valor_token.value

        # validacion basica de tipos (para tu error: "tipo de dato incorrecto")
        esperados = {
            'ENTERO': {'NUMERO'},
            'REAL_TIPO': {'REAL', 'NUMERO'},
            'CADENA_TIPO': {'CADENA_TEXTO'},
            'BOOLEANO': {'TRUE', 'FALSE'},
        }

        # caso especial: lectura de dispositivo dentro de una asignacion, ej: entero a = pi->valor();
        es_valor_dispositivo = (
            valor_token.type == 'ID'
            and len(tokens_en_espera) >= 6
            and tokens_en_espera[4][0].type == 'FLECHA'
            and tokens_en_espera[5][0].type == 'VALOR'
        )

        if tipo in esperados:
            if es_valor_dispositivo:
                # permitimos asignar valor() a entero/real/booleano (tu lenguaje define el valor real)
                if tipo == 'CADENA_TIPO':
                    errores_semanticos.append(
                        f"x error semantico: tipo de dato incorrecto en '{nombre}'. "
                        f"se declaro {tipo.lower()} y se asigno lectura de dispositivo "
                        f"(linea {valor_token.lineno}, columna {valor_col})"
                    )
                    valor = None
                else:
                    valor = f"{valor_token.value}->valor()"
            else:
                if valor_token.type not in esperados[tipo]:
                    errores_semanticos.append(
                        f"x error semantico: tipo de dato incorrecto en '{nombre}'. "
                        f"se declaro {tipo.lower()} y se asigno {valor_token.type.lower()} "
                        f"(linea {valor_token.lineno}, columna {valor_col})"
                    )
                    # opcional: no guardamos el valor si esta mal
                    valor = None


    agregar_a_tabla_simbolos(nombre, tipo, valor, t2.lineno, c2)


def mostrar_resultados():
    # errores lexicos
    if errores_lexicos:
        salida_analizador.insert(tk.END, "\n--- errores lexicos ---\n")
        for error in errores_lexicos:
            salida_analizador.insert(tk.END, f"{error}\n")

    # avisos lexicos (no bloquean)
    if avisos_lexicos:
        salida_analizador.insert(tk.END, "\n--- avisos lexicos ---\n")
        for aviso in avisos_lexicos:
            salida_analizador.insert(tk.END, f"{aviso}\n")

    # errores semanticos
    if errores_semanticos:
        salida_analizador.insert(tk.END, "\n--- errores semanticos ---\n")
        for error in errores_semanticos:
            salida_analizador.insert(tk.END, f"{error}\n")

    # tabla de simbolos
    salida_analizador.insert(tk.END, "\n--- tabla de simbolos ---\n")
    for simbolo in tabla_simbolos:
        salida_analizador.insert(
            tk.END,
            f"nombre: {simbolo.get('nombre')}, tipo: {simbolo.get('tipo')}, "
            f"valor: {simbolo.get('valor')}, linea: {simbolo.get('linea')}, "
            f"columna: {simbolo.get('columna')}, clase: {simbolo.get('clase')}\n"
        )


# --------- mini interprete: ejecutar imprimir(...) ---------

def ejecutar_codigo(codigo):
    """
    mini interprete muy simple:
    - busca lineas con imprimir(expr);
    - si expr es "texto", imprime el literal;
    - si expr es numero, lo imprime;
    - si expr es identificador, busca su valor en la tabla de simbolos.
    """
    lineas = codigo.splitlines()

    for linea in lineas:
        m = re.search(r'imprimir\s*\(\s*(.+?)\s*\)\s*;', linea)
        if not m:
            continue

        expr = m.group(1).strip()

        # caso 1: literal de cadena "texto"
        if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
            texto = expr[1:-1]
            imprimir_en_lenguaje(texto)
            continue

        # caso 2: numero literal
        if re.fullmatch(r'\d+(\.\d+)?', expr):
            imprimir_en_lenguaje(expr)
            continue

        # caso 3: identificador -> buscar en tabla de simbolos
        nombre_var = expr
        valor = None

        for simbolo in tabla_simbolos:
            if simbolo["nombre"] == nombre_var:
                valor = simbolo["valor"]
                break

        if valor is None:
            # aviso en consola de ejecucion
            imprimir_en_lenguaje(f"[aviso] {nombre_var} no tiene valor asignado")
        else:
            imprimir_en_lenguaje(valor)


# --------- verificacion semantica: variables usadas sin declaracion ---------

def verificar_variables_usadas(lista_de_tokens, codigo):
    """
    revisa todos los ID:
    - si no aparecen en la tabla de simbolos
      ni como parametros de funciones,
      se reportan como 'variable usada sin declaracion'.
    """
    # construir conjunto de identificadores declarados
    declarados = set()

    # nombres declarados en la tabla de simbolos (variables, funciones, etc.)
    for simbolo in tabla_simbolos:
        declarados.add(simbolo["nombre"])

    # parametros de funciones: vienen en simbolo['valor'] como lista de strings tipo 'entero v'
    for simbolo in tabla_simbolos:
        if simbolo["tipo"] == "funcion" and isinstance(simbolo["valor"], list):
            for p in simbolo["valor"]:
                p = p.strip()
                if not p:
                    continue
                partes = p.split()
                nombre_param = partes[-1]
                declarados.add(nombre_param)

    # aseguramos que lexer tenga el codigo actual
    lexer.input(codigo)

    # para ignorar atributos dentro de:  tipo id = {  puerto = 1, ... };
    en_atributos = False
    nivel_llaves = 0

    for i, tok in enumerate(lista_de_tokens):
        # entrar/salir del bloque { } de atributos despues de '='
        if tok.type == "LLAVE_A":
            if i > 0 and lista_de_tokens[i - 1].type == "ASIGNACION":
                en_atributos = True
                nivel_llaves = 1
            elif en_atributos:
                nivel_llaves += 1
            continue

        if tok.type == "LLAVE_C" and en_atributos:
            nivel_llaves -= 1
            if nivel_llaves <= 0:
                en_atributos = False
                nivel_llaves = 0
            continue

        # solo checamos IDs
        if tok.type != "ID":
            continue

        # si es una "llave" dentro del { } (id seguido de '='), ignorarla
        if en_atributos and (i + 1 < len(lista_de_tokens)) and lista_de_tokens[i + 1].type == "ASIGNACION":
            continue

        nombre = tok.value

        # si ya fue declarado, ok
        if nombre in declarados:
            continue

        # si es palabra reservada, ignorar
        if nombre in palabras_reservadas:
            continue

        col = encontrar_columna(lexer, tok)
        errores_semanticos.append(
            f"x error semantico: variable '{nombre}' usada sin declaracion (linea {tok.lineno}, columna {col})"
        )


# ------------------------ interfaz tk ------------------------

ventana = tk.Tk()
ventana.title("analizador de tu lenguaje")
ventana.geometry("1100x750")
ventana.configure(bg="#1e1e2f")

# ---------- editor con contador de lineas ----------

frame_editor = tk.Frame(ventana, bg="#1e1e2f")
frame_editor.pack(fill="x", padx=10, pady=10)

label_editor = tk.Label(
    frame_editor,
    text="codigo fuente",
    bg="#1e1e2f",
    fg="#ffffff",
    font=("arial", 12, "bold")
)
label_editor.pack(anchor="w")

# contenedor horizontal para gutter + editor + scrollbar
frame_textos = tk.Frame(frame_editor, bg="#1e1e2f")
frame_textos.pack(fill="x")

# widget de numeros de linea
line_numbers = tk.Text(
    frame_textos,
    width=4,
    padx=4,
    takefocus=0,
    border=0,
    background="#252526",
    foreground="#858585",
    state="disabled",
    font=("consolas", 12),
)
line_numbers.pack(side="left", fill="y")

# scrollbar vertical compartida
scrollbar_editor = tk.Scrollbar(frame_textos, orient="vertical")
scrollbar_editor.pack(side="right", fill="y")

# editor de codigo
editor_text = tk.Text(
    frame_textos,
    width=120,
    height=12,
    font=("consolas", 14),
    bg="#1c1c1c",
    fg="#ffffff",
    insertbackground="white",
    undo=True,
    wrap="none",
)
editor_text.pack(side="left", fill="both", expand=True)

# funciones para sincronizar scroll y numeros de linea

def actualizar_numeros_linea(event=None):
    line_numbers.config(state="normal")
    line_numbers.delete("1.0", tk.END)

    # obtener cantidad de lineas
    total_lineas = int(editor_text.index("end-1c").split(".")[0])  # asegurarse que 'end-1c' no corte la última línea
    for i in range(1, total_lineas + 1):
        line_numbers.insert(tk.END, f"{i}\n")

    line_numbers.config(state="disabled")

def on_scrollbar(*args):
    editor_text.yview(*args)
    line_numbers.yview(*args)

def on_textscroll(first, last):
    scrollbar_editor.set(first, last)
    line_numbers.yview_moveto(first)

editor_text.configure(yscrollcommand=on_textscroll)
scrollbar_editor.configure(command=on_scrollbar)

# actualizar numeros de linea cuando se escribe o se mueve el cursor
editor_text.bind("<KeyRelease>", actualizar_numeros_linea)
editor_text.bind("<MouseWheel>", lambda e: actualizar_numeros_linea())

# inicializar al arranque
actualizar_numeros_linea()

# ---------- boton analizar ----------

def abrir_codigo_objeto():
    """Abre el archivo de codigo objeto (.py) generado en la ultima ejecucion."""
    if ruta_codigo_objeto and os.path.exists(ruta_codigo_objeto):
        try:
            os.startfile(ruta_codigo_objeto)
        except Exception as e:
            salida_analizador.insert(tk.END, f"\nx no se pudo abrir el codigo objeto: {e}\n")
    else:
        salida_analizador.insert(
            tk.END,
            "\n[info] aun no hay codigo objeto generado. Pulsa 'analizar' con un programa valido.\n"
        )


frame_botones = tk.Frame(ventana, bg="#1e1e2f")
frame_botones.pack(pady=5)

btn = tk.Button(
    frame_botones,
    text="analizar",
    font=("arial", 12, "bold"),
    bg="#ff9800",
    fg="black",
    activebackground="#ffc107",
    activeforeground="black",
    relief="raised",
    bd=4,
    padx=10,
    pady=5,
    command=analizar_codigo,
)
btn.pack(side="left", padx=5)

btn_codigo_objeto = tk.Button(
    frame_botones,
    text="ver codigo objeto (.py)",
    font=("arial", 12, "bold"),
    bg="#4caf50",
    fg="black",
    activebackground="#81c784",
    activeforeground="black",
    relief="raised",
    bd=4,
    padx=10,
    pady=5,
    command=abrir_codigo_objeto,
)
btn_codigo_objeto.pack(side="left", padx=5)

# ---------- frame de salidas (dos columnas) ----------

frame_salidas = tk.Frame(ventana, bg="#1e1e2f")
frame_salidas.pack(fill="both", expand=True, padx=10, pady=10)

# salida del analizador
frame_analizador = tk.LabelFrame(
    frame_salidas,
    text="salida del analizador (tokens, errores, tabla de simbolos)",
    bg="#1e1e2f",
    fg="#ffffff",
    font=("arial", 10, "bold")
)
frame_analizador.pack(side="left", fill="both", expand=True, padx=(0, 5))

salida_analizador = scrolledtext.ScrolledText(
    frame_analizador,
    width=60,
    height=20,
    font=("consolas", 11),
    bg="#002b36",
    fg="#00ff00",
    insertbackground="white",
)
salida_analizador.pack(fill="both", expand=True, pady=5, padx=5)

# consola de ejecucion del lenguaje
frame_ejecucion = tk.LabelFrame(
    frame_salidas,
    text="consola de ejecucion (salida de imprimir, etc.)",
    bg="#1e1e2f",
    fg="#ffffff",
    font=("arial", 10, "bold")
)
frame_ejecucion.pack(side="right", fill="both", expand=True, padx=(5, 0))

salida_ejecucion = scrolledtext.ScrolledText(
    frame_ejecucion,
    width=60,
    height=20,
    font=("consolas", 11),
    bg="#000000",
    fg="#ffffff",
    insertbackground="white",
)
salida_ejecucion.pack(fill="both", expand=True, pady=5, padx=5)

try:
    ventana.mainloop()
except Exception as e:
    print(f"x error critico al iniciar la interfaz: {e}")
