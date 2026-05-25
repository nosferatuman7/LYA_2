@echo off
REM ============================================================
REM  Compila el CODIGO OBJETO DE BAJO NIVEL (ensamblador) a un
REM  ejecutable nativo .exe que muestra las instrucciones.
REM
REM  Requisitos: NASM y MinGW-w64 (gcc) instalados y en el PATH.
REM     NASM:  https://www.nasm.us/
REM     MinGW: https://www.mingw-w64.org/  (o winlibs.com)
REM
REM  Primero genera 'codigo_objeto.asm' desde la interfaz del
REM  compilador (boton "generar .exe (bajo nivel)") o ejecutando
REM  el programa que crea ese archivo.
REM ============================================================
cd /d "%~dp0"

if not exist codigo_objeto.asm (
    echo [ERROR] No existe codigo_objeto.asm.
    echo Genera primero el codigo objeto de bajo nivel desde el compilador.
    pause
    exit /b 1
)

echo Ensamblando con NASM...
nasm -f win64 codigo_objeto.asm -o codigo_objeto.obj
if errorlevel 1 ( echo [ERROR] Fallo NASM. Verifica que NASM este instalado. & pause & exit /b 1 )

echo Enlazando con gcc (MinGW-w64)...
gcc codigo_objeto.obj -o codigo_objeto.exe
if errorlevel 1 ( echo [ERROR] Fallo gcc. Verifica que MinGW-w64 este instalado. & pause & exit /b 1 )

echo.
echo Compilacion exitosa: codigo_objeto.exe
echo --------------------------------------------
codigo_objeto.exe
echo --------------------------------------------
pause
