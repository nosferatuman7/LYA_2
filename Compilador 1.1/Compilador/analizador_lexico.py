from analizador_semantico import AnalizadorSemantico
from generador_codigo_intermedio import GeneradorCodigoIntermedio
from optimizador_codigo_intermedio import OptimizadorCodigoIntermedio
from interprete import Interprete
from generador_codigo_objeto import GeneradorCodigoObjeto
from generador_ensamblador import GeneradorEnsamblador
from exportador_resultados import ExportadorResultados

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

# guarda los ultimos resultados generados (para los botones de codigo objeto y exportar)
ultimo_codigo_objeto = ""
ruta_codigo_objeto = ""
ultimo_tac = ""
ultimo_tac_opt = ""

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

    # 1.5 tabla de palabras reservadas (conteo de uso)
    mostrar_tabla_palabras_reservadas(tokens_para_tabla)

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

    # 5.5 generacion de codigo intermedio (TAC) + optimizacion, solo si no hay errores
    if resultado and not errores_lexicos and not errores_sintacticos and not errores_semanticos:
        global ultimo_tac, ultimo_tac_opt
        try:
            gen = GeneradorCodigoIntermedio()
            gen.generar(resultado)
            codigo_tac = gen.obtener_codigo()
            ultimo_tac = codigo_tac
            salida_analizador.insert(tk.END, "\n--- codigo intermedio (TAC) ---\n")
            salida_analizador.insert(tk.END, codigo_tac + "\n")

            # optimizacion del codigo intermedio
            opt = OptimizadorCodigoIntermedio()
            instrucciones_opt = opt.optimizar(gen.obtener_instrucciones())
            codigo_tac_opt = opt.formatear(instrucciones_opt)
            ultimo_tac_opt = codigo_tac_opt
            salida_analizador.insert(tk.END, "\n--- codigo intermedio optimizado ---\n")
            salida_analizador.insert(tk.END, codigo_tac_opt + "\n")
            salida_analizador.insert(tk.END, "\n--- optimizaciones aplicadas ---\n")
            for r in opt.reporte:
                salida_analizador.insert(tk.END, f"{r}\n")
        except Exception as e:
            salida_analizador.insert(tk.END, f"\n--- codigo intermedio (TAC) --- x error al generar codigo intermedio: {e}\n")

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


# --------- tabla de palabras reservadas (conteo) ---------

def contar_palabras_reservadas(lista_de_tokens):
    """Devuelve una lista (palabra, cantidad) con el conteo de palabras reservadas usadas."""
    tipos_reservados = set(palabras_reservadas.values())
    conteo = {}
    for tok in lista_de_tokens:
        if tok.type in tipos_reservados:
            clave = str(tok.value)
            conteo[clave] = conteo.get(clave, 0) + 1
    return sorted(conteo.items(), key=lambda x: (-x[1], x[0]))


def mostrar_tabla_palabras_reservadas(lista_de_tokens):
    salida_analizador.insert(tk.END, "\n--- tabla de palabras reservadas ---\n")
    conteo = contar_palabras_reservadas(lista_de_tokens)
    if not conteo:
        salida_analizador.insert(tk.END, "(no se usaron palabras reservadas)\n")
        return
    for palabra, cantidad in conteo:
        salida_analizador.insert(tk.END, f"{palabra}: {cantidad}\n")


# --------- exportacion de resultados ---------

def exportar_resultados():
    """Exporta tokens, palabras reservadas, tabla de simbolos, codigo intermedio
    (y optimizado) y codigo objeto a un archivo Excel (o texto si no hay openpyxl)."""
    codigo = editor_text.get("1.0", tk.END).strip()
    if not codigo:
        salida_analizador.insert(tk.END, "\n[info] no hay codigo que exportar.\n")
        return

    toks = clonar_tokens(codigo)
    lista_tokens = []
    for tok in toks:
        col = encontrar_columna(lexer, tok)
        lista_tokens.append((tok.type, str(tok.value), tok.lineno, col))

    datos = {
        "tokens": lista_tokens,
        "palabras": contar_palabras_reservadas(toks),
        "simbolos": list(tabla_simbolos),
        "intermedio": ultimo_tac,
        "intermedio_opt": ultimo_tac_opt,
        "objeto": ultimo_codigo_objeto,
    }

    ruta_base = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "resultados_exportados"
    )
    try:
        ruta = ExportadorResultados().exportar(ruta_base, datos)
        salida_analizador.insert(tk.END, f"\n[resultados exportados en: {ruta}]\n")
        try:
            os.startfile(ruta)
        except Exception:
            pass
    except Exception as e:
        salida_analizador.insert(tk.END, f"\nx error al exportar resultados: {e}\n")


# --------- generacion de .exe (codigo objeto de bajo nivel) ---------

def _tac_a_opcodes_avr(lineas):
    """
    Traduce instrucciones TAC del compilador a opcodes AVR reales
    para ATmega328p (Arduino Uno/Nano).

    Instrucciones AVR usadas:
      LDI  Rd, K    : 1110 KKKK dddd KKKK  (cargar inmediato en registro)
      STS  addr, Rr : 1001 001r rrrr 0000 + addr16 (guardar en SRAM)
      LDS  Rd, addr : 1001 000d dddd 0000 + addr16 (cargar desde SRAM)
      CALL addr     : 1001 0101 000X XXXX + addr (llamada a subrutina)
      RET           : 1001 0101 0000 1000 (retorno)
      RJMP rel      : 1100 kkkk kkkk kkkk (salto relativo)
      NOP           : 0000 0000 0000 0000

    Registros usados:
      r24, r25 : argumentos de funciones (convencion AVR-GCC)
      r26-r27  : puntero X (datos de cadena)
      r16-r23  : variables temporales

    Mapa de memoria SRAM (ATmega328p, SRAM inicia en 0x0100):
      0x0100 : variable 0
      0x0102 : variable 1
      ...cada variable ocupa 2 bytes (word)

    Perifericos mapeados en I/O del ATmega328p:
      DDRB  = 0x24  : direccion puerto B
      PORTB = 0x25  : salida puerto B  (pin13 = bit5)
      DDRD  = 0x2A  : direccion puerto D
      PORTD = 0x2B  : salida puerto D
      UBRR0H= 0xC5  : baud rate Serial (high)
      UBRR0L= 0xC4  : baud rate Serial (low)  9600 baud @ 16MHz => 103
      UCSR0B= 0xC1  : control Serial
      UDR0  = 0xC6  : dato Serial

    El programa generado:
      1. Inicializa el stack pointer
      2. Inicializa Serial a 9600 baud
      3. Configura pines segun los dispositivos declarados
      4. Traduce cada instruccion TAC a opcodes
      5. Bucle infinito al final
    """
    import re
    import struct

    opcodes = []        # lista de bytes (int 0-255)
    variables = {}      # nombre -> direccion SRAM
    sram_ptr = 0x0100   # inicio SRAM ATmega328p
    etiquetas = {}      # nombre -> offset en opcodes (para saltos)
    parches_salto = []  # (offset_instruccion, nombre_etiqueta) para parchear despues

    # --- utilidades para emitir instrucciones AVR ---

    def emit(*bytes_):
        for b in bytes_:
            opcodes.append(b & 0xFF)

    def emit_word(w):
        emit(w & 0xFF, (w >> 8) & 0xFF)  # little-endian

    def ldi(rd, k):
        """LDI Rd, K  (rd: 16-31, k: 0-255)"""
        rd = rd & 0x0F  # solo bits bajos (r16=0, r17=1, ...)
        k = k & 0xFF
        hi = 0xE0 | (k >> 4 & 0x0F) | (rd << 4 & 0xF0) >> 4 << 4
        # formula correcta: 1110 KKKK dddd KKKK
        hi = 0xE0 | ((k >> 4) & 0x0F) | ((rd & 0x0F) << 4)
        lo = k & 0x0F | ((rd & 0x0F) << 4)
        # reescribir limpio:
        # opcode = 0xE000 | ((k & 0xF0) << 4) | ((rd & 0x0F) << 4) | (k & 0x0F)
        word = 0xE000 | ((k & 0xF0) << 4) | ((rd & 0x0F) << 4) | (k & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def sts(addr, rr):
        """STS addr, Rr — guarda registro en SRAM"""
        # opcode: 1001 001r rrrr 0000
        word = 0x9200 | ((rr & 0x1F) << 4)
        emit(word & 0xFF, (word >> 8) & 0xFF)
        emit_word(addr)

    def lds(rd, addr):
        """LDS Rd, addr — carga SRAM en registro"""
        word = 0x9000 | ((rd & 0x1F) << 4)
        emit(word & 0xFF, (word >> 8) & 0xFF)
        emit_word(addr)

    def nop():
        emit(0x00, 0x00)

    def rjmp(offset_relativo):
        """RJMP k  (offset en words, -2048..2047)"""
        k = offset_relativo & 0x0FFF
        word = 0xC000 | k
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def out_io(addr, rr):
        """OUT A, Rr — escribe en registro I/O (addr 0x00-0x3F)"""
        word = 0xB800 | ((addr & 0x30) << 5) | ((rr & 0x1F) << 4) | (addr & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def asignar_variable(nombre):
        nonlocal sram_ptr
        if nombre not in variables:
            variables[nombre] = sram_ptr
            sram_ptr += 2
        return variables[nombre]

    # --- 1. prologo: inicializar stack pointer (SPH:SPL = 0x08FF) ---
    # LDI r16, 0x08  ; SPH
    ldi(16, 0x08)
    # OUT SPH(0x3E), r16
    out_io(0x3E, 16)
    # LDI r16, 0xFF  ; SPL
    ldi(16, 0xFF)
    # OUT SPL(0x3D), r16
    out_io(0x3D, 16)

    # --- 2. inicializar Serial 9600 baud @ 16MHz (UBRR=103=0x67) ---
    # UBRR0H = 0x00
    ldi(24, 0x00)
    sts(0xC5, 24)
    # UBRR0L = 103
    ldi(24, 103)
    sts(0xC4, 24)
    # UCSR0B = 0x18 (RXEN0 | TXEN0)
    ldi(24, 0x18)
    sts(0xC1, 24)
    # UCSR0C = 0x06 (8 bits, 1 stop, sin paridad)
    ldi(24, 0x06)
    sts(0xC2, 24)

    # --- 3. configurar pin 13 (PB5) como salida para LED/senales ---
    # DDRB |= (1<<5)  -> LDI r16, 0x20 / OUT DDRB, r16
    ldi(16, 0x20)
    out_io(0x04, 16)   # DDRB = 0x04 en espacio I/O

    # --- 4. traducir instrucciones TAC ---
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue

        # eliminar numeracion "  1.  instruccion"
        linea_limpia = re.sub(r'^\s*\d+\.\s*', '', linea)

        # --- etiqueta ---
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*\s*:$', linea_limpia):
            nombre_et = linea_limpia.rstrip(':').strip()
            etiquetas[nombre_et] = len(opcodes)
            nop()
            continue

        # --- imprimir / print ---
        m = re.match(r'^(?:imprimir|print)\s+(.+)$', linea_limpia, re.IGNORECASE)
        if m:
            expr = m.group(1).strip().strip('"')
            # emitir cada caracter via UDR0 (sin esperar UDRE0 para simplificar)
            for ch in expr[:32]:  # max 32 chars
                ldi(24, ord(ch) & 0xFF)
                sts(0xC6, 24)   # UDR0
            # salto de linea \r\n
            ldi(24, 0x0D)
            sts(0xC6, 24)
            ldi(24, 0x0A)
            sts(0xC6, 24)
            continue

        # --- girarMotor / girarServo ---
        m = re.match(r'^(?:girarMotor|girarServo|GIRARMOTOR|GIRARSERVO)\s*\(?\s*(\w+)\s*,\s*(\w+)\s*\)?', linea_limpia, re.IGNORECASE)
        if m:
            # simular: cargar velocidad en r24, activar PORTB
            vel_str = m.group(2)
            vel = int(vel_str) if vel_str.isdigit() else 90
            vel = max(0, min(255, vel))
            ldi(24, vel)
            out_io(0x05, 24)   # PORTB
            nop(); nop()
            continue

        # --- encender LED ---
        m = re.match(r'^encender\s+(\w+)', linea_limpia, re.IGNORECASE)
        if m:
            ldi(16, 0x20)
            out_io(0x05, 16)   # PORTB pin13 HIGH
            nop()
            continue

        # --- apagar LED ---
        m = re.match(r'^apagar\s+(\w+)', linea_limpia, re.IGNORECASE)
        if m:
            ldi(16, 0x00)
            out_io(0x05, 16)   # PORTB pin13 LOW
            nop()
            continue

        # --- retraso / delay ---
        m = re.match(r'^retraso\s*\(?\s*(\d+)\s*\)?', linea_limpia, re.IGNORECASE)
        if m:
            ms = int(m.group(1)) & 0xFF
            # bucle de retardo simple: LDI r20, ms; DEC r20; BRNE -1
            ldi(20, ms)
            # DEC r20: 1001 010d dddd 1010  d=20 -> 0x940A ... simplificado:
            emit(0x4A, 0x95)   # DEC r20
            emit(0xFE, 0xCF)   # RJMP -1 (loop sobre DEC)
            nop()
            continue

        # --- asignacion: var = valor ---
        m = re.match(r'^(\w+)\s*=\s*(.+)$', linea_limpia)
        if m:
            dest = m.group(1).strip()
            src  = m.group(2).strip()
            addr = asignar_variable(dest)
            if src.lstrip('-').isdigit():
                val = int(src) & 0xFF
                ldi(24, val)
                sts(addr, 24)
            elif src.startswith('"'):
                # cadena: guardar primer caracter
                ch = src[1] if len(src) > 1 else 0
                ldi(24, ord(ch) & 0xFF)
                sts(addr, 24)
            else:
                # src es otra variable
                src_addr = asignar_variable(src)
                lds(24, src_addr)
                sts(addr, 24)
            continue

        # --- goto / salto ---
        m = re.match(r'^goto\s+(\w+)', linea_limpia, re.IGNORECASE)
        if m:
            etiqueta = m.group(1)
            parches_salto.append((len(opcodes), etiqueta))
            rjmp(0)   # se parchea despues
            continue

        # --- halt / fin ---
        if re.match(r'^halt$', linea_limpia, re.IGNORECASE):
            rjmp(-1)   # bucle infinito: RJMP $ (queda en este punto)
            continue

        # --- instruccion no reconocida: NOP ---
        nop()

    # --- 5. epilogo: bucle infinito ---
    rjmp(-1)

    # --- 6. parchear saltos hacia etiquetas ---
    for (off, etiqueta) in parches_salto:
        if etiqueta in etiquetas:
            destino = etiquetas[etiqueta]
            # offset en words desde la siguiente instruccion
            rel = ((destino - off) // 2) - 1
            rel = rel & 0x0FFF
            word = 0xC000 | rel
            opcodes[off]     = word & 0xFF
            opcodes[off + 1] = (word >> 8) & 0xFF

    return bytes(opcodes)


def _bytes_a_intel_hex(data, base_addr=0x0000):
    """
    Convierte un bytearray de opcodes AVR a formato Intel HEX correcto.
    Cada registro tiene maximo 16 bytes de datos.
    """
    registros = []
    offset = 0
    while offset < len(data):
        bloque = data[offset:offset + 16]
        longitud = len(bloque)
        direccion = base_addr + offset
        dir_hi = (direccion >> 8) & 0xFF
        dir_lo = direccion & 0xFF
        tipo = 0x00

        suma = longitud + dir_hi + dir_lo + tipo
        for b in bloque:
            suma += b
        checksum = ((~suma) + 1) & 0xFF

        hex_datos = "".join(f"{b:02X}" for b in bloque)
        registros.append(f":{longitud:02X}{dir_hi:02X}{dir_lo:02X}{tipo:02X}{hex_datos}{checksum:02X}")
        offset += longitud

    registros.append(":00000001FF")
    return "\n".join(registros)


def _generar_intel_hex(lineas):
    """
    Punto de entrada: traduce TAC -> opcodes AVR -> Intel HEX.
    Genera codigo real para ATmega328p (Arduino Uno/Nano).
    """
    opcodes = _tac_a_opcodes_avr(lineas)
    return _bytes_a_intel_hex(opcodes, base_addr=0x0000)


def generar_exe():
    """Genera el codigo objeto de BAJO NIVEL (ensamblador x86-64), guarda el
    archivo .hex en formato Intel HEX, e intenta compilar a .exe con NASM + gcc.
    Se basa en el codigo intermedio optimizado."""
    import subprocess

    fuente = ultimo_tac_opt or ultimo_tac
    if not fuente:
        salida_analizador.insert(tk.END, "\n[info] primero pulsa 'analizar' con un programa valido.\n")
        return

    lineas = [l for l in fuente.splitlines() if l.strip()]
    carpeta = os.path.dirname(os.path.abspath(__file__))

    # 1) generar el ensamblador (codigo objeto de bajo nivel)
    asm = GeneradorEnsamblador().generar(lineas, "Codigo objeto - bajo nivel")
    ruta_asm = os.path.join(carpeta, "codigo_objeto.asm")
    with open(ruta_asm, "w", encoding="utf-8") as f:
        f.write(asm)
    salida_analizador.insert(tk.END, "\n--- codigo objeto de bajo nivel (ensamblador x86-64) ---\n")
    salida_analizador.insert(tk.END, asm + "\n")
    salida_analizador.insert(tk.END, f"[guardado en: {ruta_asm}]\n")

    # 2) generar y guardar el archivo Intel HEX (.hex)
    try:
        contenido_hex = _generar_intel_hex(lineas)
        ruta_hex = os.path.join(carpeta, "codigo_objeto.hex")
        with open(ruta_hex, "w", encoding="utf-8") as f:
            f.write(contenido_hex)
        salida_analizador.insert(tk.END, "\n--- archivo Intel HEX generado ---\n")
        salida_analizador.insert(tk.END, contenido_hex + "\n")
        salida_analizador.insert(tk.END, f"[guardado en: {ruta_hex}]\n")
    except Exception as e:
        salida_analizador.insert(tk.END, f"\nx error al generar el archivo .hex: {e}\n")

    # 3) intentar ensamblar (NASM) y enlazar (gcc) para crear el .exe
    ruta_obj = os.path.join(carpeta, "codigo_objeto.obj")
    ruta_exe = os.path.join(carpeta, "codigo_objeto.exe")
    try:
        r1 = subprocess.run(
            ["nasm", "-f", "win64", ruta_asm, "-o", ruta_obj],
            capture_output=True, text=True
        )
        if r1.returncode != 0:
            salida_analizador.insert(tk.END, f"\nx NASM fallo:\n{r1.stderr}\n")
            return

        r2 = subprocess.run(
            ["gcc", ruta_obj, "-o", ruta_exe],
            capture_output=True, text=True
        )
        if r2.returncode != 0:
            salida_analizador.insert(tk.END, f"\nx gcc (enlazado) fallo:\n{r2.stderr}\n")
            return

        salida_analizador.insert(tk.END, f"\n[ejecutable generado: {ruta_exe}]\n")

        # 4) ejecutar el .exe y mostrar las instrucciones
        r3 = subprocess.run([ruta_exe], capture_output=True, text=True, timeout=20)
        salida_analizador.insert(tk.END, "\n--- salida del ejecutable (.exe) ---\n")
        salida_analizador.insert(tk.END, (r3.stdout or "") + "\n")
    except FileNotFoundError:
        salida_analizador.insert(
            tk.END,
            "\n[info] No se encontro NASM o gcc en el PATH.\n"
            "  - Se genero 'codigo_objeto.asm' (codigo objeto de bajo nivel).\n"
            "  - Se genero 'codigo_objeto.hex' (formato Intel HEX).\n"
            "  - Instala NASM (nasm.us) y MinGW-w64, y ejecuta 'compilar_exe.bat', o\n"
            "  - usa 'generar_exe_pyinstaller.bat' para crear el .exe desde el codigo Python.\n"
        )
    except Exception as e:
        salida_analizador.insert(tk.END, f"\nx error al compilar/ejecutar el .exe: {e}\n")


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

btn_exportar = tk.Button(
    frame_botones,
    text="exportar resultados",
    font=("arial", 12, "bold"),
    bg="#2196f3",
    fg="black",
    activebackground="#64b5f6",
    activeforeground="black",
    relief="raised",
    bd=4,
    padx=10,
    pady=5,
    command=exportar_resultados,
)
btn_exportar.pack(side="left", padx=5)

btn_exe = tk.Button(
    frame_botones,
    text="generar .exe (bajo nivel)",
    font=("arial", 12, "bold"),
    bg="#9c27b0",
    fg="white",
    activebackground="#ba68c8",
    activeforeground="white",
    relief="raised",
    bd=4,
    padx=10,
    pady=5,
    command=generar_exe,
)
btn_exe.pack(side="left", padx=5)

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