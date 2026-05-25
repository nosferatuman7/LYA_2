# -*- coding: utf-8 -*-
"""
generador_ensamblador.py
========================
GENERACION DE CODIGO OBJETO DE BAJO NIVEL.

Toma las instrucciones del programa (codigo intermedio / acciones) y genera un
programa en ENSAMBLADOR x86-64 (sintaxis NASM, formato Win64). Ese ensamblador,
al ensamblarse con NASM y enlazarse con GCC (MinGW-w64), produce un EJECUTABLE
NATIVO (.exe) que, al correr, MUESTRA LAS INSTRUCCIONES del programa compilado.

Esto convierte el codigo de alto nivel del lenguaje en codigo de BAJO NIVEL
(ensamblador) y finalmente en un ejecutable nativo, con lo que se comprueba el
funcionamiento del compilador.

Compilacion (en Windows, con NASM y MinGW-w64 instalados):
    nasm -f win64 codigo_objeto.asm -o codigo_objeto.obj
    gcc codigo_objeto.obj -o codigo_objeto.exe
    codigo_objeto.exe
"""


# Transliteracion de acentos/caracteres especiales a ASCII (el ensamblador
# y la consola de Windows trabajan mejor sin acentos).
_TRANSLIT = str.maketrans({
    "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n",
    "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N",
    "¿": "?", "¡": "!", "°": "o", "—": "-", "–": "-",
})


class GeneradorEnsamblador:
    """
    Uso:
        asm = GeneradorEnsamblador().generar(lineas, "Codigo objeto")
        # 'lineas' es una lista de cadenas (p. ej. el codigo intermedio optimizado)
    """

    def generar(self, lineas, titulo="Codigo objeto"):
        encabezado = self._sanitizar("=== " + titulo + " ===")
        separador = "-" * 50

        contenido = [encabezado, separador]
        contenido += [self._sanitizar(str(l)) for l in lineas if str(l).strip()]
        contenido += [separador, "Ejecucion del codigo objeto completada."]

        # seccion de datos: una cadena por instruccion (terminada en 0)
        data = []
        for i, texto in enumerate(contenido):
            data.append(f'    msg{i}: db "{texto}", 0')

        # seccion de codigo: imprime cada cadena con puts (puts agrega el salto
        # de linea y NO interpreta '%', por lo que es seguro para el operador modulo)
        cuerpo = []
        for i in range(len(contenido)):
            cuerpo.append(f"    lea     rcx, [msg{i}]")
            cuerpo.append(f"    call    puts")

        return self._plantilla("\n".join(data), "\n".join(cuerpo))

    # ------------------------------------------------------------------

    def _sanitizar(self, s):
        s = s.translate(_TRANSLIT)
        s = s.replace("\\", "/").replace('"', "'").replace("\t", " ")
        # dejar solo ASCII imprimible
        s = "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in s)
        return s

    def _plantilla(self, data, cuerpo):
        return (
            ";; ============================================================\n"
            ";;  CODIGO OBJETO DE BAJO NIVEL  (ensamblador x86-64 / NASM Win64)\n"
            ";;  Generado automaticamente por el compilador.\n"
            ";;\n"
            ";;  Compilar y ejecutar (Windows, con NASM y MinGW-w64):\n"
            ";;     nasm -f win64 codigo_objeto.asm -o codigo_objeto.obj\n"
            ";;     gcc codigo_objeto.obj -o codigo_objeto.exe\n"
            ";;     codigo_objeto.exe\n"
            ";; ============================================================\n"
            "\n"
            "default rel\n"
            "extern puts\n"
            "global main\n"
            "\n"
            "section .data\n"
            f"{data}\n"
            "\n"
            "section .text\n"
            "main:\n"
            "    push    rbp\n"
            "    mov     rbp, rsp\n"
            "    sub     rsp, 32          ; espacio de sombra (Win64 ABI)\n"
            "\n"
            f"{cuerpo}\n"
            "\n"
            "    xor     eax, eax\n"
            "    add     rsp, 32\n"
            "    pop     rbp\n"
            "    ret\n"
        )

    # ------------------------------------------------------------------
    # Scripts de compilacion (texto de los .bat)
    # ------------------------------------------------------------------

    @staticmethod
    def script_bat_nasm():
        return (
            "@echo off\r\n"
            "REM Compila el codigo objeto de bajo nivel (ensamblador) a un .exe nativo.\r\n"
            "REM Requiere NASM y MinGW-w64 (gcc) en el PATH.\r\n"
            "cd /d \"%~dp0\"\r\n"
            "echo Ensamblando con NASM...\r\n"
            "nasm -f win64 codigo_objeto.asm -o codigo_objeto.obj\r\n"
            "if errorlevel 1 ( echo [ERROR] Fallo NASM. Instala NASM. & pause & exit /b 1 )\r\n"
            "echo Enlazando con gcc...\r\n"
            "gcc codigo_objeto.obj -o codigo_objeto.exe\r\n"
            "if errorlevel 1 ( echo [ERROR] Fallo gcc. Instala MinGW-w64. & pause & exit /b 1 )\r\n"
            "echo.\r\n"
            "echo Compilacion exitosa: codigo_objeto.exe\r\n"
            "echo --------------------------------------------\r\n"
            "codigo_objeto.exe\r\n"
            "echo --------------------------------------------\r\n"
            "pause\r\n"
        )

    @staticmethod
    def script_bat_pyinstaller():
        return (
            "@echo off\r\n"
            "REM Alternativa: crea un .exe a partir del codigo objeto en Python.\r\n"
            "REM Requiere Python y pip.\r\n"
            "cd /d \"%~dp0\"\r\n"
            "echo Instalando PyInstaller (si hace falta)...\r\n"
            "pip install pyinstaller\r\n"
            "echo Generando el ejecutable...\r\n"
            "pyinstaller --onefile codigo_objeto_generado.py\r\n"
            "echo.\r\n"
            "echo El ejecutable quedo en dist\\codigo_objeto_generado.exe\r\n"
            "pause\r\n"
        )


# Compatibilidad con el estilo del proyecto
generador_ensamblador = GeneradorEnsamblador
