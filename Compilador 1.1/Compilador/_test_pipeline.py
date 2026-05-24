# -*- coding: utf-8 -*-
"""
_test_pipeline.py
Prueba headless (sin GUI) del compilador completo:
  lexer -> parser -> semantico -> codigo intermedio (TAC)
        -> interprete (ejecucion) -> codigo objeto (Python)

Uso:  python3 _test_pipeline.py
"""
import io
import sys
import py_compile
import tempfile
import os

import lexer
from lexer import errores_lexicos
from analizador_sintactico import parsear_codigo, errores_sintacticos
from analizador_semantico import AnalizadorSemantico
from generador_codigo_intermedio import GeneradorCodigoIntermedio
from interprete import Interprete
from generador_codigo_objeto import GeneradorCodigoObjeto


PROGRAMAS = {
    "1_funcion_si_imprimir": '''INICIO {
    entero velocidad = 10;
    real tiempo = 2.5;
    cadena mensaje = "hola mundo";

    funcion mover(entero v) {
        si (v > 0) {
            imprimir(mensaje);
        }
    }

    mover(velocidad);
} FIN''',

    "2_bucle_para": '''INICIO {
    para (entero i = 0; i < 5; i++) {
        imprimir(i);
    }
} FIN''',

    "3_arreglo": '''INICIO {
    entero datos [3];
    datos[0] = 7;
    datos[1] = 8;
    imprimir(datos[0]);
    imprimir(datos[1]);
} FIN''',

    "4_dispositivos_led": '''INICIO {
    entero p = 13;
    led foco = { pin = p };
    foco->encender();
    retraso(500);
    foco->apagar();
} FIN''',

    "5_seguidor_linea": '''inicio {
    entero pi_pin = 17;
    entero pd_pin = 16;
    entero blanco = 55;

    sensor pi = { pin = pi_pin };
    sensor pd = { pin = pd_pin };
    motor m_izq = { pwm = 5, in1 = 9, in2 = 4 };
    motor m_der = { pwm = 6, in1 = 7, in2 = 8 };

    func avanzar(entero pwmd, entero pwmi) {
        m_izq->girarmotor(pwmi);
        m_der->girarmotor(pwmd);
        retraso(20);
    }

    mientras (true) {
        entero a = pi->valor();
        entero b = pd->valor();
        si ((a < blanco) || (b < blanco)) {
            avanzar(125, 125);
        } sino {
            avanzar(200, 200);
        }
    }
} fin''',
}


def analizar(nombre, codigo):
    print("=" * 70)
    print("PROGRAMA:", nombre)
    print("=" * 70)

    errores_lexicos.clear()
    errores_sintacticos.clear()

    lexer.lexer.lineno = 1
    ast = parsear_codigo(codigo)

    if errores_lexicos:
        print("ERRORES LEXICOS:", errores_lexicos)
    if errores_sintacticos:
        print("ERRORES SINTACTICOS:", errores_sintacticos)
    if ast is None:
        print(">> No se construyo AST. Se omite el resto.")
        return False

    sem = AnalizadorSemantico()
    errores_sem = sem.analizar(ast)
    if errores_sem:
        print("ERRORES SEMANTICOS:")
        for e in errores_sem:
            print("   ", e)
    else:
        print("Semantico: OK (sin errores)")

    # Codigo intermedio
    try:
        gen = GeneradorCodigoIntermedio()
        gen.generar(ast)
        print("\n-- TAC (primeras 12 lineas) --")
        print("\n".join(gen.obtener_codigo().splitlines()[:12]))
    except Exception as e:
        print("Error TAC:", e)

    # Ejecucion (interprete)
    print("\n-- EJECUCION (interprete, max 30 iteraciones) --")
    salida = []
    interp = Interprete(salida=salida.append, max_iteraciones=30)
    interp.ejecutar(ast)
    for linea in salida[:40]:
        print("   ", linea)
    if len(salida) > 40:
        print("    ... (%d lineas mas)" % (len(salida) - 40))

    # Codigo objeto (Python) + verificacion de que compila
    print("\n-- CODIGO OBJETO (Python) --")
    cod = GeneradorCodigoObjeto().generar(ast)
    cuerpo = cod.split("Programa traducido desde el lenguaje fuente")[-1]
    print(cuerpo.strip()[:600])

    tmp = os.path.join(tempfile.gettempdir(), "obj_%s.py" % nombre)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(cod)
    try:
        py_compile.compile(tmp, doraise=True)
        print("\n>> El codigo objeto COMPILA correctamente en Python. OK")
    except py_compile.PyCompileError as e:
        print("\n>> ERROR: el codigo objeto NO compila:")
        print(e)
        return False
    return True


if __name__ == "__main__":
    ok = True
    for nombre, codigo in PROGRAMAS.items():
        try:
            if not analizar(nombre, codigo):
                ok = False
        except Exception as e:
            import traceback
            print("EXCEPCION en", nombre, ":", e)
            traceback.print_exc()
            ok = False
        print("\n")
    print("=" * 70)
    print("RESULTADO GLOBAL:", "TODO OK" if ok else "HAY FALLOS")
    print("=" * 70)
    sys.exit(0 if ok else 1)
