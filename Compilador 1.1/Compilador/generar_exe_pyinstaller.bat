@echo off
REM ============================================================
REM  ALTERNATIVA: crea un ejecutable .exe a partir del codigo
REM  objeto en Python (codigo_objeto_generado.py).
REM
REM  Util si no tienes NASM/MinGW. Requiere Python y pip.
REM  El .exe resultante EJECUTA el programa y muestra en consola
REM  cada accion de los dispositivos (prueba de funcionamiento).
REM ============================================================
cd /d "%~dp0"

if not exist codigo_objeto_generado.py (
    echo [ERROR] No existe codigo_objeto_generado.py.
    echo Analiza primero un programa valido en el compilador.
    pause
    exit /b 1
)

echo Instalando PyInstaller (si hace falta)...
pip install pyinstaller
if errorlevel 1 ( echo [ERROR] No se pudo instalar PyInstaller. & pause & exit /b 1 )

echo Generando el ejecutable...
pyinstaller --onefile codigo_objeto_generado.py
if errorlevel 1 ( echo [ERROR] Fallo PyInstaller. & pause & exit /b 1 )

echo.
echo Listo. El ejecutable quedo en:  dist\codigo_objeto_generado.exe
pause
