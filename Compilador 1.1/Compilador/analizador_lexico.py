# ── forzar recarga de modulos corregidos (eliminar .pyc desactualizados) ──
import os as _os, glob as _glob, importlib as _imp
_cache = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '__pycache__')
for _pyc_f in _glob.glob(_os.path.join(_cache, 'generador_codigo_objeto*.pyc')):
    try:
        _os.remove(_pyc_f)
    except OSError:
        pass
_imp.invalidate_caches()
del _os, _glob, _imp, _cache

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

    Instrucciones AVR emitidas:
      LDI  Rd, K    : 1110 KKKK dddd KKKK  (cargar inmediato)
      STS  addr, Rr : 1001 001r rrrr 0000 + addr16 (guardar en SRAM)
      LDS  Rd, addr : 1001 000d dddd 0000 + addr16 (cargar desde SRAM)
      CP   Rd, Rr   : 0001 01rd dddd rrrr  (comparar registros)
      CPI  Rd, K    : 0011 KKKK dddd KKKK  (comparar con inmediato, r16-r31)
      ADD  Rd, Rr   : 0000 11rd dddd rrrr  (sumar registros)
      SUB  Rd, Rr   : 0001 10rd dddd rrrr  (restar registros)
      SUBI Rd, K    : 0101 KKKK dddd KKKK  (restar inmediato, r16-r31)
      SBIW Rd, K    : 1001 0111 KKdd KKKK  (restar par de registros)
      RJMP rel      : 1100 kkkk kkkk kkkk  (salto relativo incondicional)
      BRNE/BREQ/BRLT/BRGE : saltos condicionales basados en flags
      OUT  A, Rr    : escribe en I/O
      RET           : 1001 0101 0000 1000  (retorno de funcion)
      NOP           : 0000 0000 0000 0000

    Registros usados:
      r16      : registro de trabajo general
      r22, r23 : operando derecho en comparaciones
      r24, r25 : operando principal / retorno de funciones
      r26, r27 : contador externo (delay variable)

    Instrucciones TAC reconocidas:
      Etiqueta:         L_foo:
      Imprimir:         print "texto"  /  imprimir variable
      Dispositivo:      x->encender()  /  x->apagar()
      Servo/Motor:      x->girarServo(k)  /  girarMotor pin, k
      Retraso:          delay N  /  delay variable    <- CORREGIDO
      Condicional:      if x op y goto L              <- NUEVO
      Goto:             goto L  (incluye __break__)   <- CORREGIDO
      Asignacion:       var = expr  (literales, vars, expr aritm.)
      Dispositivo decl: x = new tipo(...)  -> ignorado
      Funcion:          param x / call f, n / return  -> soporte basico
      Halt:             halt
    """
    import re

    opcodes = []        # lista de bytes (int 0-255)
    variables = {}      # nombre -> direccion SRAM
    sram_ptr = 0x0100   # inicio SRAM ATmega328p
    etiquetas = {}      # nombre -> offset en opcodes (para saltos)
    # parches_salto: (offset_del_RJMP, nombre_etiqueta)
    # siempre se parchea con RJMP (12-bit, rango +-2047 words)
    parches_salto = []

    # ── utilidades para emitir instrucciones AVR ──

    def emit(*bytes_):
        for b in bytes_:
            opcodes.append(b & 0xFF)

    def emit_word(w):
        emit(w & 0xFF, (w >> 8) & 0xFF)   # little-endian

    def ldi(rd, k):
        """LDI Rd, K  (rd: 16-31, k: 0-255) — 1110 KKKK dddd KKKK"""
        rd = rd & 0x0F
        k  = k  & 0xFF
        word = 0xE000 | ((k & 0xF0) << 4) | ((rd & 0x0F) << 4) | (k & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def sts(addr, rr):
        """STS addr, Rr — guarda registro en SRAM"""
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

    def dec(rd):
        """DEC Rd  — 1001 010d dddd 1010"""
        word = 0x9400 | ((rd & 0x1F) << 4) | 0x0A
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def sbiw(rd, k):
        """SBIW Rd, K — resta inmediato a par de registros (solo r24/26/28/30)."""
        dd = {24: 0, 26: 1, 28: 2, 30: 3}[rd]
        word = 0x9700 | (((k >> 4) & 0x03) << 6) | (dd << 4) | (k & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def sbrs(rr, b):
        """SBRS Rr, b — salta siguiente instruccion si bit b de Rr es 1."""
        word = 0xFE00 | ((rr & 0x1F) << 4) | (b & 0x07)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def brne(destino_byte):
        """BRNE k — salta a destino_byte si Z=0 (usado en bucles internos)."""
        aqui = len(opcodes)
        rel  = ((destino_byte - aqui) // 2) - 1
        word = 0xF401 | ((rel & 0x7F) << 3)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def sbi(a, b):
        """SBI A, b — activa bit b en registro I/O A (A: 0x00-0x1F).
        Opcode: 1001 1010 AAAA Abbb"""
        word = 0x9A00 | ((a & 0x1F) << 3) | (b & 0x07)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def cbi(a, b):
        """CBI A, b — limpia bit b en registro I/O A (A: 0x00-0x1F).
        Opcode: 1001 1000 AAAA Abbb"""
        word = 0x9800 | ((a & 0x1F) << 3) | (b & 0x07)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def mul_r(rd, rr):
        """MUL Rd, Rr — R1:R0 = Rd * Rr (8x8 sin signo). Resultado en R1:R0.
        Opcode: 1001 11rd dddd rrrr"""
        word = 0x9C00 | ((rr & 0x10) << 5) | ((rd & 0x1F) << 4) | (rr & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def mov(rd, rr):
        """MOV Rd, Rr — copia registro rr en rd.
        Opcode: 0010 11rd dddd rrrr"""
        word = 0x2C00 | ((rr & 0x10) << 5) | ((rd & 0x1F) << 4) | (rr & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def adc_r(rd, rr):
        """ADC Rd, Rr — Rd = Rd + Rr + C (suma con acarreo del flag C).
        Opcode: 0001 11rd dddd rrrr"""
        word = 0x1C00 | ((rr & 0x10) << 5) | ((rd & 0x1F) << 4) | (rr & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    # ── instrucciones aritmeticas y de comparacion ──

    def cp(rd, rr):
        """CP Rd, Rr — compara registros sin guardar resultado."""
        word = 0x1400 | ((rr & 0x10) << 5) | ((rd & 0x1F) << 4) | (rr & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def cpi(rd, k):
        """CPI Rd, K — compara registro con inmediato (solo r16-r31)."""
        rd_enc = (rd - 16) & 0x0F
        k = k & 0xFF
        word = 0x3000 | ((k & 0xF0) << 4) | (rd_enc << 4) | (k & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def add_regs(rd, rr):
        """ADD Rd, Rr — suma dos registros."""
        word = 0x0C00 | ((rr & 0x10) << 5) | ((rd & 0x1F) << 4) | (rr & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def sub_regs(rd, rr):
        """SUB Rd, Rr — resta dos registros."""
        word = 0x1800 | ((rr & 0x10) << 5) | ((rd & 0x1F) << 4) | (rr & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    def subi(rd, k):
        """SUBI Rd, K — resta inmediato (solo r16-r31). Para sumar: subi(rd, -k)."""
        rd_enc = (rd - 16) & 0x0F
        k = k & 0xFF
        word = 0x5000 | ((k & 0xF0) << 4) | (rd_enc << 4) | (k & 0x0F)
        emit(word & 0xFF, (word >> 8) & 0xFF)

    # ── serial ──

    def serial_envia_r24():
        """Envia r24 por UART esperando que UDRE0 este listo."""
        inicio_lds = len(opcodes)
        lds(25, 0xC0)           # LDS r25, UCSR0A
        sbrs(25, 5)             # SBRS r25, 5  -> salta si UDRE0=1
        aqui_rjmp = len(opcodes)
        rel = ((inicio_lds - aqui_rjmp) // 2) - 1
        rjmp(rel)               # RJMP atras: reintentar
        sts(0xC6, 24)           # STS UDR0, r24

    # ── retardos ──

    def delay_ms(ms):
        """Retardo por software ~ms milisegundos @16MHz. Termina correctamente."""
        ms = max(1, min(int(ms), 65535))
        INNER = 4800                        # ~1 ms calibrado para coincidir con delay() de Arduino
        ldi(26, ms & 0xFF)                  # r26:r27 = contador externo (ms)
        ldi(27, (ms >> 8) & 0xFF)
        externo = len(opcodes)
        ldi(24, INNER & 0xFF)               # r24:r25 = contador interno (~1 ms)
        ldi(25, (INNER >> 8) & 0xFF)
        interno = len(opcodes)
        sbiw(24, 1)                         # interno--
        brne(interno)                       # repetir hasta r24:r25 == 0
        sbiw(26, 1)                         # externo--
        brne(externo)                       # repetir hasta r26:r27 == 0

    def delay_variable_sram(addr):
        """Retardo usando valor de 16 bits almacenado en SRAM (addr=low, addr+1=high)."""
        lds(26, addr)           # r26 = byte bajo del contador
        lds(27, addr + 1)       # r27 = byte alto del contador
        INNER = 4000
        externo = len(opcodes)
        ldi(24, INNER & 0xFF)
        ldi(25, (INNER >> 8) & 0xFF)
        interno = len(opcodes)
        sbiw(24, 1)
        brne(interno)
        sbiw(26, 1)
        brne(externo)

    # ── helpers de variables y operandos ──

    def asignar_variable(nombre):
        nonlocal sram_ptr
        if nombre not in variables:
            variables[nombre] = sram_ptr
            sram_ptr += 2
        return variables[nombre]

    def cargar_en_r24(operando):
        """Carga 'operando' (literal numerico, booleano o nombre de variable) en r24."""
        op = str(operando).strip()
        if op.lstrip('-').isdigit():
            ldi(24, int(op) & 0xFF)
        elif op.lower() in ('true', '1'):
            ldi(24, 1)
        elif op.lower() in ('false', '0', '""', "''"):
            ldi(24, 0)
        elif op.startswith('"') or op.startswith("'"):
            ch = op[1] if len(op) > 1 else '\0'
            ldi(24, ord(ch) & 0xFF if isinstance(ch, str) else 0)
        else:
            addr = asignar_variable(op)
            lds(24, addr)

    # ── saltos condicionales ──

    def emitir_salto_condicional(op_str, etiqueta):
        """
        Emite el patron:
            BRXX_inverso  +1_word   (2 bytes: salta el RJMP si condicion es FALSA)
            RJMP          L         (2 bytes: se parchea; salta si condicion es VERDADERA)

        Esto garantiza rango completo de RJMP (+-2047 words) para cualquier programa.

        op_str es el operador TAC que indica cuando SI hay que saltar a L:
          '==' -> saltar si igual    (branch inverso = BRNE)
          '!=' -> saltar si distinto (branch inverso = BREQ)
          '<'  -> saltar si menor    (branch inverso = BRGE)
          '>=' -> saltar si >=       (branch inverso = BRLT)
          '>'  -> saltar si mayor    (branch inverso = BRLT, aprox)
          '<=' -> saltar si <=       (branch inverso = BRGE, aprox)
        """
        # Opcode de branch inverso con offset +1 word (salta sobre el RJMP que sigue)
        # Formato BRBS/BRBC: 1111 0x kk kkkk k bbb  con kk...k = 1 (offset +1 word)
        branch_inverso = {
            '==': 0xF409,  # BRNE +1: salta si Z=0 (no igual)  -> cae si igual
            '!=': 0xF009,  # BREQ +1: salta si Z=1 (igual)     -> cae si distinto
            '<' : 0xF40C,  # BRGE +1: salta si N^V=0 (>=)      -> cae si <
            '>=': 0xF00C,  # BRLT +1: salta si N^V=1 (<)       -> cae si >=
            '>' : 0xF00C,  # aprox: BRLT  (tratar > como >=)
            '<=': 0xF40C,  # aprox: BRGE  (tratar <= como <)
        }
        bword = branch_inverso.get(op_str, 0xF409)   # default: BRNE
        emit(bword & 0xFF, (bword >> 8) & 0xFF)       # 2 bytes: branch inverso
        parches_salto.append((len(opcodes), etiqueta)) # registrar RJMP para parchear
        rjmp(0)                                        # 2 bytes: placeholder RJMP

    # ── tabla de pines Arduino Uno: pin -> (ddr_io, port_io, bit) ──
    # DDRB=0x04, PORTB=0x05 (pines 8-13/PB0-PB5)
    # DDRD=0x0A, PORTD=0x0B (pines 0-7/PD0-PD7)
    _PIN_IO = {
        0:  (0x0A, 0x0B, 0),  1:  (0x0A, 0x0B, 1),
        2:  (0x0A, 0x0B, 2),  3:  (0x0A, 0x0B, 3),
        4:  (0x0A, 0x0B, 4),  5:  (0x0A, 0x0B, 5),
        6:  (0x0A, 0x0B, 6),  7:  (0x0A, 0x0B, 7),
        8:  (0x04, 0x05, 0),  9:  (0x04, 0x05, 1),   # pin 9  = OC1A (servo)
        10: (0x04, 0x05, 2),  11: (0x04, 0x05, 3),   # pin 10 = OC1B (servo2)
        12: (0x04, 0x05, 4),  13: (0x04, 0x05, 5),   # pin 13 = LED builtin
    }

    def _ddr_port_bit(pin):
        return _PIN_IO.get(int(pin), (0x04, 0x05, 5))  # default pin 13

    def _cfg_salida(pin):
        """Configura pin como OUTPUT mediante SBI sobre registro DDR."""
        ddr, _, bit = _ddr_port_bit(pin)
        sbi(ddr, bit)

    def _set_pin(pin):
        """digitalWrite(pin, HIGH) via SBI sobre registro PORT."""
        _, port, bit = _ddr_port_bit(pin)
        sbi(port, bit)

    def _clr_pin(pin):
        """digitalWrite(pin, LOW) via CBI sobre registro PORT."""
        _, port, bit = _ddr_port_bit(pin)
        cbi(port, bit)

    # ── 0. pre-escaneo: detectar dispositivos y sus pines ──
    # Busca lineas TAC del tipo: "nombre = new tipo(puerto=N, ...)"
    pines_dispositivos = {}   # nombre_dev -> {'tipo': str, 'pin': int}
    for _ls in lineas:
        _ls2 = re.sub(r'^\s*\d+\.\s*', '', _ls.strip())
        _m_d = re.match(r'^(\w+)\s*=\s*new\s+(\w+)\s*\((.+)\)', _ls2, re.IGNORECASE)
        if _m_d:
            _dn = _m_d.group(1)
            _dt = _m_d.group(2).lower()
            _at = _m_d.group(3)
            _mp = re.search(r'(?:puerto|pin)\s*=\s*(\d+)', _at, re.IGNORECASE)
            _pn = int(_mp.group(1)) if _mp else (9 if 'servo' in _dt else 13)
            pines_dispositivos[_dn] = {'tipo': _dt, 'pin': _pn}

    _TIPOS_SERVO = {
        'servo', 'motor_servo_grande_ev3', 'motor_servo_mediano_ev3',
        'servomotor_nxt', 'motor_angular_grande', 'motor_angular_mediano',
        'motor_powered_up', 'motor_powered_up_boost', 'motor_boost',
    }
    _TIPOS_MOTOR = {'motor'}
    _hay_servo = any(d['tipo'] in _TIPOS_SERVO for d in pines_dispositivos.values())
    _hay_motor = any(d['tipo'] in _TIPOS_MOTOR for d in pines_dispositivos.values())

    # ── 1. prologo: inicializar stack pointer (SPH:SPL = 0x08FF) ──
    ldi(16, 0x08);  out_io(0x3E, 16)   # SPH = 0x08
    ldi(16, 0xFF);  out_io(0x3D, 16)   # SPL = 0xFF

    # ── 2. inicializar Serial 9600 baud @ 16MHz (UBRR=103) ──
    ldi(24, 0x00);  sts(0xC5, 24)      # UBRR0H = 0
    ldi(24, 103);   sts(0xC4, 24)      # UBRR0L = 103
    ldi(24, 0x18);  sts(0xC1, 24)      # UCSR0B = RXEN|TXEN
    ldi(24, 0x06);  sts(0xC2, 24)      # UCSR0C = 8N1

    # ── 3. configurar pines de todos los dispositivos declarados como OUTPUT ──
    _pines_cfg = set()
    sbi(0x04, 5)           # DDRB bit5 = OUTPUT (pin 13, LED builtin siempre)
    _pines_cfg.add(13)
    for _di in pines_dispositivos.values():
        _pp = _di['pin']
        if _pp not in _pines_cfg:
            _cfg_salida(_pp)
            _pines_cfg.add(_pp)

    # ── 3b. inicializar Timer1 para servo PWM a 50 Hz (si hay servos) ──
    # Fast PWM modo 14: TOP = ICR1, prescaler 8 -> f_timer = 2 MHz
    # Periodo = 40 000 cuentas = 20 ms  -> ICR1 = 39 999 (0x9C3F)
    # Angulo:   0° -> OCR1x = 2000 (1 ms)
    #          90° -> OCR1x = 3000 (1.5 ms)
    #         180° -> OCR1x = 4000 (2 ms)
    if _hay_servo:
        # REGLA AVR: en registros de 16 bits siempre escribir HIGH primero, luego LOW.
        # Si se escribe LOW primero, el AVR hace la escritura atomica con TEMP=0x00
        # y el registro queda con el HIGH en 0, arruinando el valor.
        #
        # ICR1 = 39999 (0x9C3F)  -> periodo 20 ms a 2 MHz (prescaler 8)
        ldi(24, 0x9C);  sts(0x87, 24)   # ICR1H  = 0x9C  (HIGH primero!)
        ldi(24, 0x3F);  sts(0x86, 24)   # ICR1L  = 0x3F  (LOW despues)
        # OCR1A = 1088 (0x0440)  -> 544 us = 0 grados (igual que Arduino Servo.h MIN_PULSE)
        ldi(24, 0x04);  sts(0x89, 24)   # OCR1AH = 0x04  (HIGH primero!)
        ldi(24, 0x40);  sts(0x88, 24)   # OCR1AL = 0x40  (LOW despues)
        # OCR1B = 1088 (canal B, por si se usa pin 10)
        ldi(24, 0x04);  sts(0x8B, 24)   # OCR1BH = 0x04  (HIGH primero!)
        ldi(24, 0x40);  sts(0x8A, 24)   # OCR1BL = 0x40  (LOW despues)
        # TCCR1A = 0xA2: COM1A1|COM1B1|WGM11 (non-inverting, ambos canales, modo 14)
        ldi(24, 0xA2);  sts(0x80, 24)
        # TCCR1B = 0x1A: WGM13|WGM12|CS11 (prescaler /8, inicia el timer)
        ldi(24, 0x1A);  sts(0x81, 24)

    # ── 3c. inicializar Timer0 para motor PWM (si hay motores) ──
    # Fast PWM: TCCR0A = 0xA3 (COM0A1|COM0B1|WGM01|WGM00)
    # Prescaler 64 -> ~976 Hz: TCCR0B = 0x03
    if _hay_motor:
        ldi(24, 0xA3);  sts(0x44, 24)   # TCCR0A
        ldi(24, 0x03);  sts(0x45, 24)   # TCCR0B (prescaler 64)
        ldi(24, 0);     sts(0x47, 24)   # OCR0A = 0 (motor A parado)
        sts(0x48, 24)                   # OCR0B = 0 (motor B parado)

    # ── 4. traducir instrucciones TAC ──
    # Guardar el offset donde empieza el codigo de usuario (para loop automatico en halt)
    _inicio_codigo_usuario = len(opcodes)
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue

        # quitar numeracion "  1.  instruccion"
        linea_limpia = re.sub(r'^\s*\d+\.\s*', '', linea)

        # ── etiqueta: L_foo:  /  func_bar: ──
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*\s*:$', linea_limpia):
            nombre_et = linea_limpia.rstrip(':').strip()
            etiquetas[nombre_et] = len(opcodes)
            nop()
            continue

        # ── declaracion de dispositivo: x = new tipo(...) -> ignorar ──
        if re.match(r'^\w+\s*=\s*new\s+\w+', linea_limpia, re.IGNORECASE):
            nop(); continue

        # ── soporte basico de funciones: param / call / return ──
        if re.match(r'^param\s+', linea_limpia, re.IGNORECASE):
            nop(); continue
        if re.match(r'^(?:\w+\s*=\s*)?call\s+\w+', linea_limpia, re.IGNORECASE):
            nop(); continue
        if re.match(r'^return\b', linea_limpia, re.IGNORECASE):
            emit(0x08, 0x95)   # RET
            continue

        # ── imprimir / print ──
        m = re.match(r'^(?:imprimir|print)\s+(.+)$', linea_limpia, re.IGNORECASE)
        if m:
            expr = m.group(1).strip()
            if expr.startswith('"') and expr.endswith('"'):
                # literal de cadena
                texto = expr[1:-1]
                for ch in texto[:32]:
                    ldi(24, ord(ch) & 0xFF)
                    serial_envia_r24()
            else:
                # variable: enviar su byte desde SRAM
                varname = expr.strip('"\'')
                if varname:
                    addr = asignar_variable(varname)
                    lds(24, addr)
                    serial_envia_r24()
            ldi(24, 0x0D); serial_envia_r24()   # \r
            ldi(24, 0x0A); serial_envia_r24()   # \n
            continue

        # ── accion dispositivo: encender ──
        # TAC: "t1 = miLed->encender()"  o bien  "miLed->encender()"
        m_enc = re.match(
            r'^(?:\w+\s*=\s*)?(\w+)\s*->\s*encender\s*\(\)',
            linea_limpia, re.IGNORECASE
        )
        if m_enc:
            _dev_enc = m_enc.group(1)
            _pin_enc = pines_dispositivos.get(_dev_enc, {}).get('pin', 13)
            _set_pin(_pin_enc)   # SBI PORT, bit  (pin HIGH)
            continue

        # ── accion dispositivo: apagar ──
        m_ap = re.match(
            r'^(?:\w+\s*=\s*)?(\w+)\s*->\s*apagar\s*\(\)',
            linea_limpia, re.IGNORECASE
        )
        if m_ap:
            _dev_ap = m_ap.group(1)
            _pin_ap = pines_dispositivos.get(_dev_ap, {}).get('pin', 13)
            _clr_pin(_pin_ap)    # CBI PORT, bit  (pin LOW)
            continue

        # ── accion dispositivo: girarServo ──
        # TAC: "t1 = miServo->girarServo(90)"
        # Escribe angulo en OCR1A/OCR1B segun el pin del servo.
        # Formula: OCR1x = 1088 + grados * 3712/180  (cuentas a 2 MHz)
        # Igual que Arduino Servo.h: MIN_PULSE=544us MAX_PULSE=2400us
        #   0 grados  -> 1088  (pulso 544 us  = Arduino Servo write(0))
        #  90 grados  -> 2944  (pulso 1472 us = Arduino Servo write(90))
        # 180 grados  -> 4800  (pulso 2400 us = Arduino Servo write(180))
        m_gs = re.match(
            r'^(?:\w+\s*=\s*)?(\w+)\s*->\s*girarServo\s*\(\s*(-?\w+)\s*\)',
            linea_limpia, re.IGNORECASE
        )
        if m_gs:
            _dev_gs  = m_gs.group(1)
            _grd_s   = m_gs.group(2)
            _pin_gs  = pines_dispositivos.get(_dev_gs, {}).get('pin', 9)
            # Canal OC1A (pin 9) o OC1B (pin 10)
            _ocr_lo  = 0x88 if _pin_gs != 10 else 0x8A
            _ocr_hi  = 0x89 if _pin_gs != 10 else 0x8B
            if _grd_s.lstrip('-').isdigit():
                # Valor literal: OCR1x calculado en tiempo de compilacion
                # Formula Arduino Servo.h: 1088 + grados * 3712/180
                # REGLA AVR: HIGH primero, luego LOW (registro de 16 bits)
                _g   = max(0, min(180, int(_grd_s)))
                _tks = 1088 + (_g * 3712) // 180
                ldi(24, (_tks >> 8) & 0xFF); sts(_ocr_hi, 24)  # HIGH primero
                ldi(24, _tks & 0xFF);        sts(_ocr_lo, 24)  # LOW despues
            else:
                # Variable: r24:r25 = 1088 + grados * 21  (aprox 3712/180)
                # REGLA AVR: HIGH primero, luego LOW (registro de 16 bits)
                _adr_g = asignar_variable(_grd_s)
                lds(24, _adr_g)               # r24 = grados (0-180)
                ldi(22, 21)                   # r22 = 21  (aprox 3712/180)
                mul_r(24, 22)                 # R1:R0 = grados * 21
                mov(24, 0);  mov(25, 1)       # r24:r25 = producto (16 bits)
                ldi(22, 0x40); ldi(23, 0x04)  # r22:r23 = 1088 (0x0440)
                add_regs(24, 22)              # r24 += 0x40  (sets C)
                adc_r(25, 23)                 # r25 += 0x04 + C
                sts(_ocr_hi, 25)              # HIGH primero
                sts(_ocr_lo, 24)              # LOW despues
            continue

        # ── accion dispositivo: girarMotor ──
        # TAC: "t1 = miMotor->girarMotor(200)"
        # Escribe velocidad (0-255) en OCR0A (pin 6) o OCR0B (pin 5).
        m_gm = re.match(
            r'^(?:\w+\s*=\s*)?(\w+)\s*->\s*girarMotor\s*\(\s*(-?\w+)\s*\)',
            linea_limpia, re.IGNORECASE
        )
        if m_gm:
            _dev_gm = m_gm.group(1)
            _vel_s  = m_gm.group(2)
            _pin_gm = pines_dispositivos.get(_dev_gm, {}).get('pin', 6)
            _ocr_m  = 0x48 if _pin_gm == 5 else 0x47   # OCR0B o OCR0A
            if _vel_s.lstrip('-').isdigit():
                ldi(24, max(0, min(255, int(_vel_s))))
            else:
                _adr_v = asignar_variable(_vel_s)
                lds(24, _adr_v)
            sts(_ocr_m, 24)
            continue

        # ── retraso / delay ──
        # Soporta: delay 500  (literal)  Y  delay variable  (nombre en SRAM)
        m = re.match(r'^(?:delay|retraso)\s+(.+)', linea_limpia, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val.lstrip('-').isdigit():
                delay_ms(int(val))                   # retardo con literal numerico
            else:
                addr = asignar_variable(val)
                delay_variable_sram(addr)            # retardo con valor en SRAM
            continue

        # ── salto condicional: if x op y goto L ──
        # El TAC genera p.ej.: "if x >= 5 goto L_fin_mientras"
        m = re.match(
            r'^if\s+(\S+)\s*(==|!=|<=|>=|<|>)\s*(\S+)\s+goto\s+(\w+)',
            linea_limpia, re.IGNORECASE
        )
        if m:
            izq  = m.group(1).strip()
            op_s = m.group(2).strip()
            der  = m.group(3).strip()
            etiq = m.group(4).strip()

            # cargar operando izquierdo en r24
            cargar_en_r24(izq)

            # comparar con operando derecho (inmediato o variable)
            if der.lstrip('-').isdigit():
                cpi(24, int(der) & 0xFF)        # CPI r24, K
            elif der.lower() in ('true', '1'):
                cpi(24, 1)
            elif der.lower() in ('false', '0'):
                cpi(24, 0)
            else:
                addr_der = asignar_variable(der)
                lds(22, addr_der)
                cp(24, 22)                      # CP r24, r22

            # emitir branch inverso + RJMP parcheable
            emitir_salto_condicional(op_s, etiq)
            continue

        # ── goto / salto incondicional ──
        m = re.match(r'^goto\s+(\w+)', linea_limpia, re.IGNORECASE)
        if m:
            etiqueta = m.group(1)
            if etiqueta == '__break__':
                # romper sin etiqueta definida: emitir NOP para no crear bucle infinito
                nop()
            else:
                parches_salto.append((len(opcodes), etiqueta))
                rjmp(0)   # se parchea en el paso 6
            continue

        # ── halt / fin ──
        # En lugar de RJMP $ (bucle infinito en halt), saltamos al inicio del
        # codigo de usuario para que el programa haga loop automatico,
        # igual que void loop() en Arduino.
        if re.match(r'^halt$', linea_limpia, re.IGNORECASE):
            _aqui = len(opcodes)
            _rel  = ((_inicio_codigo_usuario - _aqui) // 2) - 1
            rjmp(_rel)   # RJMP -> inicio codigo usuario (loop automatico)
            continue

        # ── asignacion: var = expr ──
        m = re.match(r'^(\w+(?:\[\w+\])?)\s*=\s*(.+)$', linea_limpia)
        if m:
            dest = m.group(1).strip()
            src  = m.group(2).strip()

            # ignorar asignaciones complejas con call/new/->
            if re.search(r'\bcall\b|\bnew\b', src, re.IGNORECASE) or '->' in src:
                nop(); continue

            dest_base = re.sub(r'\[.*\]', '', dest)
            addr = asignar_variable(dest_base)

            if src.lstrip('-').isdigit():
                # valor numerico literal
                ldi(24, int(src) & 0xFF)
                sts(addr, 24)
            elif src.startswith('"') or src.startswith("'"):
                # cadena: guardar primer caracter ASCII
                ch = src[1] if len(src) > 1 else '\0'
                ldi(24, ord(ch) & 0xFF if isinstance(ch, str) else 0)
                sts(addr, 24)
            elif src.lower() in ('true', '1'):
                ldi(24, 1); sts(addr, 24)
            elif src.lower() in ('false', '0', '""', "''"):
                ldi(24, 0); sts(addr, 24)
            else:
                # expresion aritmetica simple:  a + b  /  a - b  /  a + K  /  a - K
                pm = re.match(r'^(-?[\w]+)\s*([\+\-])\s*(-?[\w]+)$', src)
                if pm:
                    l_s, op_c, r_s = pm.group(1), pm.group(2), pm.group(3)
                    cargar_en_r24(l_s)      # r24 = operando izquierdo
                    if op_c == '+':
                        if r_s.lstrip('-').isdigit():
                            # ADDI r24, k  ->  SUBI r24, (-k)
                            subi(24, (-int(r_s)) & 0xFF)
                        else:
                            addr_r = asignar_variable(r_s)
                            lds(22, addr_r)
                            add_regs(24, 22)    # r24 = r24 + r22
                    else:   # '-'
                        if r_s.lstrip('-').isdigit():
                            subi(24, int(r_s) & 0xFF)
                        else:
                            addr_r = asignar_variable(r_s)
                            lds(22, addr_r)
                            sub_regs(24, 22)    # r24 = r24 - r22
                    sts(addr, 24)
                else:
                    # copia simple de otra variable (o expresion no reconocida)
                    src_base = re.sub(r'\[.*\]', '', src.strip())
                    src_addr = asignar_variable(src_base)
                    lds(24, src_addr)
                    sts(addr, 24)
            continue

        # ── instruccion no reconocida: NOP ──
        nop()

    # ── 5. epilogo: loop de seguridad al inicio del codigo usuario ──
    _aqui_ep = len(opcodes)
    _rel_ep  = ((_inicio_codigo_usuario - _aqui_ep) // 2) - 1
    rjmp(_rel_ep)

    # ── 6. parchear saltos hacia etiquetas ──
    for (off, etiqueta) in parches_salto:
        if etiqueta not in etiquetas:
            # etiqueta no encontrada (p.ej. __break__ sin bloque): dejar como NOP
            opcodes[off]     = 0x00
            opcodes[off + 1] = 0x00
            continue
        destino = etiquetas[etiqueta]
        rel = ((destino - off) // 2) - 1
        rel = rel & 0x0FFF
        word = 0xC000 | rel
        opcodes[off]     = word & 0xFF
        opcodes[off + 1] = (word >> 8) & 0xFF

    return bytes(opcodes)


# Flash USABLE del ATmega328P (Arduino Uno/Nano): 32 KB menos el bootloader.
FLASH_ATMEGA328P = 32 * 1024 - 512   # 32256 bytes

def _intel_hex_checksum(byte_list):
    """Checksum Intel HEX: complemento a dos de la suma de los bytes."""
    return ((~sum(byte_list)) + 1) & 0xFF


def _bytes_a_intel_hex(data, base_addr=0x0000):
    """
    Convierte un bytearray de opcodes AVR a formato Intel HEX CORRECTO.

    Cada registro de datos tiene como maximo 16 bytes. El campo de direccion
    de un registro de datos es de SOLO 16 bits (0x0000-0xFFFF); para direccionar
    mas alla de 64 KB se emiten registros 'Extended Linear Address' (tipo 0x04)
    que fijan los 16 bits altos. Sin esto, la direccion se desbordaba y los datos
    a partir de 64 KB se escribian encima de los primeros (bug original).
    """
    registros = []
    upper = 0                       # parte alta de la direccion (bits 16+) ya seleccionada
    offset = 0
    n = len(data)
    while offset < n:
        direccion = base_addr + offset
        hi16 = (direccion >> 16) & 0xFFFF
        if hi16 != upper:
            # registro Extended Linear Address (tipo 04): fija los 16 bits altos
            ela = [0x02, 0x00, 0x00, 0x04, (hi16 >> 8) & 0xFF, hi16 & 0xFF]
            registros.append(":" + "".join(f"{b:02X}" for b in ela)
                             + f"{_intel_hex_checksum(ela):02X}")
            upper = hi16

        addr16 = direccion & 0xFFFF
        # un registro no debe cruzar el limite de 64 KB
        max_en_bloque = 0x10000 - addr16
        longitud = min(16, n - offset, max_en_bloque)
        bloque = data[offset:offset + longitud]

        dir_hi = (addr16 >> 8) & 0xFF
        dir_lo = addr16 & 0xFF
        cuerpo = [longitud, dir_hi, dir_lo, 0x00] + list(bloque)
        hex_datos = "".join(f"{b:02X}" for b in bloque)
        registros.append(
            f":{longitud:02X}{dir_hi:02X}{dir_lo:02X}00{hex_datos}"
            f"{_intel_hex_checksum(cuerpo):02X}"
        )
        offset += longitud

    registros.append(":00000001FF")     # registro de fin de archivo
    return "\n".join(registros)


def _generar_intel_hex(lineas, flash_max=FLASH_ATMEGA328P):
    """
    Punto de entrada: traduce TAC -> opcodes AVR -> Intel HEX.
    Genera codigo real para ATmega328p (Arduino Uno/Nano).

    Si 'flash_max' no es None y el programa no cabe en la flash, lanza
    ValueError con un mensaje claro (evita generar un .hex que la placa no
    puede almacenar entero: era la causa de 'solo sube una parte').
    """
    opcodes = _tac_a_opcodes_avr(lineas)
    if flash_max is not None and len(opcodes) > flash_max:
        raise ValueError(
            f"El programa ocupa {len(opcodes)} bytes de codigo, pero la flash "
            f"usable del ATmega328P (Arduino Uno/Nano) es de ~{flash_max} bytes "
            f"(32 KB menos el bootloader): NO CABE en la placa.\n"
            f"   Recuerda: el .hex es texto ASCII y pesa ~2.9x mas que el binario, "
            f"asi que un .hex de ~{len(opcodes)*29//10} bytes equivale a "
            f"{len(opcodes)} bytes reales de flash.\n"
            f"   Soluciones: reduce el programa, o usa una placa con mas flash "
            f"(p.ej. Arduino Mega 2560, 256 KB) llamando con flash_max mayor o None."
        )
    return _bytes_a_intel_hex(opcodes, base_addr=0x0000)


def _buscar_arduino_cli():
    """
    Busca el ejecutable arduino-cli en rutas tipicas de Windows y en el PATH.
    Retorna la ruta al ejecutable si se encuentra, o None si no.
    """
    import subprocess, shutil
    candidatos = ["arduino-cli"]          # primero buscar en PATH
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        prog  = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        prog86= os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
        home  = os.path.expanduser("~")
        candidatos += [
            # Arduino IDE 2.x (incluye arduino-cli integrado)
            os.path.join(local, "Programs", "Arduino IDE",
                         "resources", "app", "lib", "backend",
                         "resources", "arduino-cli.exe"),
            # arduino-cli standalone (instalacion tipica)
            os.path.join(local, "Arduino15", "arduino-cli.exe"),
            os.path.join(prog,  "Arduino CLI", "arduino-cli.exe"),
            os.path.join(prog86,"Arduino CLI", "arduino-cli.exe"),
            os.path.join(home,  "arduino-cli.exe"),
            os.path.join(home,  "bin", "arduino-cli.exe"),
            # Arduino IDE 1.8.x NO incluye arduino-cli; avr-gcc si
        ]
    for ruta in candidatos:
        try:
            r = subprocess.run([ruta, "version"],
                               capture_output=True, timeout=8, text=True)
            if r.returncode == 0:
                return ruta
        except Exception:
            continue
    return None


def _compilar_ino_a_hex(codigo_ino, cli, log_fn=None):
    """
    Compila un sketch Arduino (.ino) usando arduino-cli y retorna
    el contenido del archivo Intel HEX como string.

    - cli     : ruta al ejecutable arduino-cli
    - log_fn  : funcion opcional para mostrar mensajes de progreso
    """
    import subprocess, tempfile, shutil

    def log(msg):
        if log_fn:
            log_fn(msg)

    tmpdir = tempfile.mkdtemp(prefix="lya2_sketch_")
    nombre = "lya2_sketch"
    sketch_dir = os.path.join(tmpdir, nombre)
    out_dir    = os.path.join(tmpdir, "out")
    os.makedirs(sketch_dir)
    os.makedirs(out_dir)
    ino_path = os.path.join(sketch_dir, f"{nombre}.ino")

    try:
        # Escribir el sketch
        with open(ino_path, "w", encoding="utf-8") as f:
            f.write(codigo_ino)

        # Asegurar que el core arduino:avr esta instalado
        log("[arduino-cli] verificando core arduino:avr ...\n")
        r_core = subprocess.run(
            [cli, "core", "install", "arduino:avr"],
            capture_output=True, text=True, timeout=120
        )
        if r_core.returncode != 0 and "already installed" not in r_core.stdout.lower():
            log(f"[arduino-cli] advertencia al instalar core: {r_core.stderr[:200]}\n")

        # Compilar el sketch
        log("[arduino-cli] compilando sketch para arduino:avr:uno ...\n")
        cmd = [cli, "compile",
               "--fqbn", "arduino:avr:uno",
               "--output-dir", out_dir,
               sketch_dir]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        log(r.stdout)
        if r.returncode != 0:
            raise RuntimeError(
                f"arduino-cli fallo (codigo {r.returncode}):\n{r.stderr}\n{r.stdout}"
            )

        # Localizar el .hex generado
        hex_path = None
        for nombre_f in os.listdir(out_dir):
            if nombre_f.endswith(".hex"):
                hex_path = os.path.join(out_dir, nombre_f)
                break
        if not hex_path:
            raise FileNotFoundError(
                f"No se encontro archivo .hex en {out_dir}\n"
                f"Archivos presentes: {os.listdir(out_dir)}"
            )

        with open(hex_path, "r", encoding="utf-8") as f:
            return f.read()

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def abrir_codigo_objeto():
    """Abre el archivo de codigo objeto generado (.ino) con el editor del sistema."""
    import subprocess, sys
    if not ruta_codigo_objeto or not os.path.isfile(ruta_codigo_objeto):
        salida_analizador.insert(
            tk.END,
            "\n[info] primero pulsa 'analizar' para generar el codigo objeto.\n"
        )
        return
    try:
        if sys.platform == "win32":
            os.startfile(ruta_codigo_objeto)
        elif sys.platform == "darwin":
            subprocess.run(["open", ruta_codigo_objeto])
        else:
            subprocess.run(["xdg-open", ruta_codigo_objeto])
        salida_analizador.insert(
            tk.END,
            f"\n[abriendo] {ruta_codigo_objeto}\n"
        )
    except Exception as e:
        salida_analizador.insert(
            tk.END,
            f"\n[error] no se pudo abrir el archivo: {e}\n"
        )


def generar_exe():
    """
    Genera el archivo Intel HEX (.hex) para ATmega328P (Arduino Uno).

    Estrategia (en orden de prioridad):
      1. arduino-cli / Arduino IDE 2.x: compila el sketch .ino real con el
         toolchain AVR oficial → HEX identico al que produciria Arduino IDE.
         Esto garantiza que librerias como Servo.h funcionen correctamente.
      2. Fallback hand-crafted: si no se encuentra arduino-cli, genera un HEX
         aproximado directamente desde el TAC (metodo anterior).

    Tambien genera el ensamblador x86-64 (documentacion) e intenta compilarlo
    a .exe con NASM + gcc si estan instalados.
    """
    import subprocess

    fuente = ultimo_tac_opt or ultimo_tac
    if not fuente:
        salida_analizador.insert(tk.END,
            "\n[info] primero pulsa 'analizar' con un programa valido.\n")
        return

    lineas  = [l for l in fuente.splitlines() if l.strip()]
    carpeta = os.path.dirname(os.path.abspath(__file__))

    # ── 1. ensamblador x86-64 (documentacion/referencia) ──────────────────
    asm = GeneradorEnsamblador().generar(lineas, "Codigo objeto - bajo nivel")
    ruta_asm = os.path.join(carpeta, "codigo_objeto.asm")
    with open(ruta_asm, "w", encoding="utf-8") as f:
        f.write(asm)
    salida_analizador.insert(tk.END,
        "\n--- codigo objeto de bajo nivel (ensamblador x86-64) ---\n")
    salida_analizador.insert(tk.END, asm + "\n")
    salida_analizador.insert(tk.END, f"[guardado en: {ruta_asm}]\n")

    # ── 2. generar Intel HEX ───────────────────────────────────────────────
    ruta_hex = os.path.join(carpeta, "codigo_objeto.hex")
    contenido_hex = None
    metodo_hex    = "hand-crafted (fallback)"

    # Intento A: compilar el .ino real con arduino-cli
    if ultimo_codigo_objeto and ultimo_codigo_objeto.strip():
        cli = _buscar_arduino_cli()
        if cli:
            salida_analizador.insert(tk.END,
                f"\n[arduino-cli encontrado: {cli}]\n")
            try:
                contenido_hex = _compilar_ino_a_hex(
                    ultimo_codigo_objeto, cli,
                    log_fn=lambda m: salida_analizador.insert(tk.END, m)
                )
                metodo_hex = f"arduino-cli ({cli})"
                salida_analizador.insert(tk.END,
                    "\n[OK] HEX generado con arduino-cli "
                    "(identico al producido por Arduino IDE)\n")
            except Exception as e:
                salida_analizador.insert(tk.END,
                    f"\n[aviso] arduino-cli fallo, usando metodo fallback:\n{e}\n")
                contenido_hex = None
        else:
            salida_analizador.insert(tk.END,
                "\n[info] arduino-cli no encontrado. "
                "Se usara generacion hand-crafted como fallback.\n"
                "  Para obtener un HEX identico al .ino instala Arduino IDE 2.x\n"
                "  (https://www.arduino.cc/en/software) o arduino-cli\n"
                "  (https://arduino.github.io/arduino-cli/)\n")

    # Intento B: fallback hand-crafted desde TAC
    if contenido_hex is None:
        try:
            contenido_hex = _generar_intel_hex(lineas)
            salida_analizador.insert(tk.END,
                "\n[info] HEX generado con metodo hand-crafted "
                "(aproximacion, puede diferir de Arduino IDE)\n")
        except Exception as e:
            salida_analizador.insert(tk.END,
                f"\nx error al generar HEX (fallback): {e}\n")

    # Guardar y mostrar el HEX
    if contenido_hex:
        with open(ruta_hex, "w", encoding="utf-8") as f:
            f.write(contenido_hex)
        salida_analizador.insert(tk.END,
            "\n--- archivo Intel HEX ---\n")
        salida_analizador.insert(tk.END, contenido_hex + "\n")
        salida_analizador.insert(tk.END,
            f"[guardado en: {ruta_hex}] [metodo: {metodo_hex}]\n")

        n_lineas_hex = len([l for l in contenido_hex.splitlines() if l.startswith(":")])
        n_bin = len(_tac_a_opcodes_avr(lineas))
        pct   = 100.0 * n_bin / FLASH_ATMEGA328P
        salida_analizador.insert(tk.END,
            f"\n[tamano estimado del programa: {n_bin} bytes de flash "
            f"({pct:.1f}% del ATmega328P)]\n"
            f"[registros HEX: {n_lineas_hex} lineas]\n")

    # ── 3. intentar .exe con NASM + gcc (opcional, x86-64) ────────────────
    ruta_obj = os.path.join(carpeta, "codigo_objeto.obj")
    ruta_exe = os.path.join(carpeta, "codigo_objeto.exe")
    try:
        r1 = subprocess.run(
            ["nasm", "-f", "win64", ruta_asm, "-o", ruta_obj],
            capture_output=True, text=True
        )
        if r1.returncode != 0:
            salida_analizador.insert(tk.END,
                f"\n[info] NASM no disponible o fallo: {r1.stderr[:120]}\n")
            return
        r2 = subprocess.run(
            ["gcc", ruta_obj, "-o", ruta_exe],
            capture_output=True, text=True
        )
        if r2.returncode != 0:
            salida_analizador.insert(tk.END,
                f"\n[info] gcc fallo: {r2.stderr[:120]}\n")
            return
        salida_analizador.insert(tk.END, f"\n[ejecutable x86-64: {ruta_exe}]\n")
        r3 = subprocess.run([ruta_exe], capture_output=True, text=True, timeout=20)
        salida_analizador.insert(tk.END,
            "\n--- salida del ejecutable (.exe) ---\n")
        salida_analizador.insert(tk.END, (r3.stdout or "") + "\n")
    except FileNotFoundError:
        salida_analizador.insert(tk.END,
            "\n[info] NASM/gcc no encontrados. El .hex ya fue generado arriba.\n"
            "  Para compilar el .exe: instala NASM + MinGW-w64 y ejecuta compilar_exe.bat\n")
    except Exception as e:
        salida_analizador.insert(tk.END,
            f"\n[info] error opcional al compilar .exe: {e}\n")


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
        errores_lexicos.append(
            f"x variable '{nombre}' usada pero no declarada "
            f"(linea {tok.lineno}, col {col})"
        )


def ver_codigo_objeto():
    """Muestra el codigo objeto generado (Arduino .ino) en el panel de salida."""
    salida_analizador.delete("1.0", tk.END)
    if not ultimo_codigo_objeto:
        salida_analizador.insert(
            tk.END,
            "[info] primero pulsa 'analizar' para generar el codigo objeto.\n"
        )
        return
    salida_analizador.insert(tk.END, "--- codigo objeto (Arduino .ino / Python) ---\n")
    salida_analizador.insert(tk.END, ultimo_codigo_objeto + "\n")
    if ruta_codigo_objeto:
        salida_analizador.insert(tk.END, f"[guardado en: {ruta_codigo_objeto}]\n")


# ─────────────────────── GUI ────────────────────────────────────────────────

ventana = tk.Tk()
ventana.title("analizador de tu lenguaje")
ventana.configure(bg="#0d1117")
ventana.geometry("1280x800")

# ══════════════════════════════════════════════════════════════════
# Helper: panel de editor con numeros de linea
# ══════════════════════════════════════════════════════════════════

class EditorConLineas(tk.Frame):
    """
    Frame que combina un canvas con numeros de linea (estilo VS Code)
    y un ScrolledText sincronizados verticalmente.
    """
    # colores del gutter
    GUTTER_BG   = "#1c2128"
    GUTTER_FG   = "#6e7681"
    GUTTER_W    = 52          # ancho en pixeles de la columna de numeros
    EDITOR_BG   = "#0d1117"
    EDITOR_FG   = "#e6edf3"
    CURSOR_CLR  = "#58a6ff"

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=self.EDITOR_BG)

        font_editor = ("Consolas", 12)

        # ── gutter (Canvas con los numeros) ──
        self.gutter = tk.Canvas(
            self,
            width=self.GUTTER_W,
            bg=self.GUTTER_BG,
            highlightthickness=0,
            bd=0,
        )
        self.gutter.pack(side="left", fill="y")

        # ── area de texto ──
        self.text = tk.Text(
            self,
            font=font_editor,
            bg=self.EDITOR_BG,
            fg=self.EDITOR_FG,
            insertbackground=self.CURSOR_CLR,
            selectbackground="#264f78",
            selectforeground=self.EDITOR_FG,
            undo=True,
            wrap="none",
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=4,
        )

        # scrollbars
        vsb = tk.Scrollbar(self, orient="vertical",   command=self._scroll_ambos_v)
        hsb = tk.Scrollbar(self, orient="horizontal",  command=self.text.xview)
        self.text.configure(yscrollcommand=self._on_text_scroll, xscrollcommand=hsb.set)

        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        self.text.pack(side="left", fill="both", expand=True)

        self._vsb = vsb

        # bind para actualizar numeros
        self.text.bind("<KeyRelease>",      lambda e: self.after(30, self._actualizar_lineas))
        self.text.bind("<MouseWheel>",      lambda e: self.after(10, self._actualizar_lineas))
        self.text.bind("<Button-4>",        lambda e: self.after(10, self._actualizar_lineas))
        self.text.bind("<Button-5>",        lambda e: self.after(10, self._actualizar_lineas))
        self.text.bind("<<Paste>>",         lambda e: self.after(50, self._actualizar_lineas))
        self.text.bind("<Configure>",       lambda e: self._actualizar_lineas())

        self._actualizar_lineas()

    # ── scrolling sincronizado ──
    def _scroll_ambos_v(self, *args):
        self.text.yview(*args)
        self._actualizar_lineas()

    def _on_text_scroll(self, first, last):
        self._vsb.set(first, last)
        self._actualizar_lineas()

    def _actualizar_lineas(self):
        self.gutter.delete("all")

        widget_h = self.text.winfo_height()
        if widget_h <= 1:
            self.after(50, self._actualizar_lineas)
            return

        last_line = int(self.text.index("end-1c").split(".")[0])

        # Primera linea visible: usar coordenada @0,0 para no depender de linea 1
        try:
            first_visible = int(self.text.index("@0,0").split(".")[0])
        except Exception:
            first_visible = 1

        for linea_num in range(first_visible, last_line + 1):
            try:
                info = self.text.dlineinfo(f"{linea_num}.0")
            except Exception:
                break
            if info is None:
                # Linea fuera del area visible (debajo del borde inferior)
                break
            y_px  = info[1]
            line_h = info[3]
            if y_px > widget_h:
                break
            self.gutter.create_text(
                self.GUTTER_W - 8,
                y_px + (line_h // 2),
                text=str(linea_num),
                anchor="e",
                font=("Consolas", 11),
                fill=self.GUTTER_FG,
            )
    # ── API compatible con scrolledtext ──
    def get(self, *args, **kwargs):
        return self.text.get(*args, **kwargs)

    def insert(self, *args, **kwargs):
        self.text.insert(*args, **kwargs)
        self._actualizar_lineas()

    def delete(self, *args, **kwargs):
        self.text.delete(*args, **kwargs)
        self._actualizar_lineas()

    def see(self, *args, **kwargs):
        self.text.see(*args, **kwargs)

    def configure(self, **kwargs):
        self.text.configure(**kwargs)

    def tag_configure(self, *args, **kwargs):
        self.text.tag_configure(*args, **kwargs)

    def tag_add(self, *args, **kwargs):
        self.text.tag_add(*args, **kwargs)

    def tag_remove(self, *args, **kwargs):
        self.text.tag_remove(*args, **kwargs)

    def mark_set(self, *args, **kwargs):
        self.text.mark_set(*args, **kwargs)

    def index(self, *args, **kwargs):
        return self.text.index(*args, **kwargs)

    def bind(self, *args, **kwargs):
        self.text.bind(*args, **kwargs)


# ══════════════════════════════════════════════════════════════════
# Construccion de la ventana principal
# ══════════════════════════════════════════════════════════════════

# ── Editor de codigo fuente (arriba, grande) ──
frame_editor = tk.LabelFrame(
    ventana,
    text=" codigo fuente",
    bg="#0d1117", fg="#58a6ff",
    font=("Arial", 10, "bold"),
    bd=1, relief="flat",
    highlightbackground="#30363d",
    highlightthickness=1,
)
frame_editor.pack(fill="both", expand=True, padx=10, pady=(10, 0))

editor_text = EditorConLineas(frame_editor)
editor_text.pack(fill="both", expand=True, pady=5, padx=5)

# ── Barra de botones (debajo del editor) ──
frame_toolbar = tk.Frame(ventana, bg="#161b22", pady=8)
frame_toolbar.pack(fill="x", padx=10, pady=(4, 4))

# Paleta de colores de los botones (estilo GitHub dark)
_BTNS = [
    ("analizar",               "#238636", "#2ea043", analizar_codigo),
    ("ver codigo objeto (.py)","#1f6feb", "#388bfd", ver_codigo_objeto),
    ("exportar resultados",    "#6e40c9", "#8957e5", exportar_resultados),
    ("generar .exe (bajo nivel)","#b62324","#f85149", generar_exe),
]

_btn_widgets = []
for _txt, _bg, _abg, _cmd in _BTNS:
    _b = tk.Button(
        frame_toolbar, text=_txt,
        bg=_bg, fg="white",
        activebackground=_abg, activeforeground="white",
        relief="flat", bd=0, padx=16, pady=8,
        font=("Arial", 10, "bold"),
        cursor="hand2",
        command=_cmd,
    )
    _b.pack(side="left", padx=6)
    _btn_widgets.append(_b)

btn_analizar = _btn_widgets[0]
btn_ver_obj  = _btn_widgets[1]
btn_exportar = _btn_widgets[2]
btn_exe      = _btn_widgets[3]

# ── Paneles de salida (abajo) ──
frame_salidas = tk.Frame(ventana, bg="#0d1117")
frame_salidas.pack(fill="both", expand=True, padx=10, pady=(0, 10))

frame_analizador = tk.LabelFrame(
    frame_salidas,
    text=" salida del analizador (tokens, errores, tabla de simbolos)",
    bg="#1e1e2f", fg="#ffffff",
    font=("Arial", 10, "bold"),
    bd=1, relief="flat",
    highlightbackground="#30363d",
    highlightthickness=1,
)
frame_analizador.pack(side="left", fill="both", expand=True, padx=(0, 5))

salida_analizador = scrolledtext.ScrolledText(
    frame_analizador, width=60, height=18,
    font=("Consolas", 11),
    bg="#002b36", fg="#00ff00",
    insertbackground="white",
    bd=0, highlightthickness=0,
)
salida_analizador.pack(fill="both", expand=True, pady=5, padx=5)

frame_ejecucion = tk.LabelFrame(
    frame_salidas,
    text=" consola de ejecucion (salida de imprimir, etc.)",
    bg="#1e1e2f", fg="#ffffff",
    font=("Arial", 10, "bold"),
    bd=1, relief="flat",
    highlightbackground="#30363d",
    highlightthickness=1,
)
frame_ejecucion.pack(side="right", fill="both", expand=True, padx=(5, 0))

salida_ejecucion = scrolledtext.ScrolledText(
    frame_ejecucion, width=60, height=18,
    font=("Consolas", 11),
    bg="#000000", fg="#ffffff",
    insertbackground="white",
    bd=0, highlightthickness=0,
)
salida_ejecucion.pack(fill="both", expand=True, pady=5, padx=5)

try:
    ventana.mainloop()
except Exception as e:
    print(f"x error critico al iniciar la interfaz: {e}")