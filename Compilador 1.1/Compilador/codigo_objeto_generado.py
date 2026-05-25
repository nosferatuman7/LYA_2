# -*- coding: utf-8 -*-
# ==========================================================================
#  CODIGO OBJETO GENERADO AUTOMATICAMENTE
#  Destino: Raspberry Pi / Python 3
#
#  Este archivo es el "codigo objeto": el programa final, equivalente al
#  programa fuente, listo para ejecutarse sobre la plataforma destino.
#  Si la libreria gpiozero esta disponible (Raspberry Pi), controla el
#  hardware real; en caso contrario, SIMULA cada dispositivo por consola,
#  de modo que el programa siempre se puede ejecutar para demostrarlo.
# ==========================================================================
import time

try:
    import gpiozero
    _HAY_GPIO = True
except Exception:
    _HAY_GPIO = False


class Dispositivo:
    """Clase base de los dispositivos del lenguaje."""

    def __init__(self, nombre, **attrs):
        self.nombre = nombre
        self.attrs = attrs

    def _attr(self, *nombres, defecto=None):
        for n in nombres:
            if n in self.attrs:
                return self.attrs[n]
        return defecto

    def encender(self):
        print("[%s] encender()" % self.nombre)

    def apagar(self):
        print("[%s] apagar()" % self.nombre)

    def girarServo(self, grados):
        print("[%s] girarServo(%s)" % (self.nombre, grados))

    def girarMotor(self, velocidad):
        print("[%s] girarMotor(%s)" % (self.nombre, velocidad))

    def valor(self):
        v = 0
        print("[%s] valor() -> %s" % (self.nombre, v))
        return v


class Led(Dispositivo):
    def __init__(self, nombre, **attrs):
        super().__init__(nombre, **attrs)
        self._dev = None
        if _HAY_GPIO and self._attr("pin") is not None:
            try:
                self._dev = gpiozero.LED(self._attr("pin"))
            except Exception:
                self._dev = None

    def encender(self):
        if self._dev:
            self._dev.on()
        print("[led %s] encender()" % self.nombre)

    def apagar(self):
        if self._dev:
            self._dev.off()
        print("[led %s] apagar()" % self.nombre)


class Buzzer(Dispositivo):
    def __init__(self, nombre, **attrs):
        super().__init__(nombre, **attrs)
        self._dev = None
        if _HAY_GPIO and self._attr("pin") is not None:
            try:
                self._dev = gpiozero.Buzzer(self._attr("pin"))
            except Exception:
                self._dev = None

    def encender(self):
        if self._dev:
            self._dev.on()
        print("[buzzer %s] encender()" % self.nombre)

    def apagar(self):
        if self._dev:
            self._dev.off()
        print("[buzzer %s] apagar()" % self.nombre)


class Servomotor(Dispositivo):
    def __init__(self, nombre, **attrs):
        super().__init__(nombre, **attrs)
        self._dev = None
        if _HAY_GPIO and self._attr("pin") is not None:
            try:
                self._dev = gpiozero.AngularServo(self._attr("pin"))
            except Exception:
                self._dev = None

    def girarServo(self, grados):
        if self._dev:
            try:
                self._dev.angle = grados
            except Exception:
                pass
        print("[servo %s] girarServo(%s)" % (self.nombre, grados))


class MotorCC(Dispositivo):
    def __init__(self, nombre, **attrs):
        super().__init__(nombre, **attrs)
        self._dev = None
        if _HAY_GPIO and self._attr("in1") is not None and self._attr("in2") is not None:
            try:
                self._dev = gpiozero.Motor(forward=self._attr("in1"),
                                           backward=self._attr("in2"))
            except Exception:
                self._dev = None

    def girarMotor(self, velocidad):
        if self._dev:
            try:
                v = max(-1.0, min(1.0, velocidad / 255.0))
                if v >= 0:
                    self._dev.forward(v)
                else:
                    self._dev.backward(-v)
            except Exception:
                pass
        print("[motor %s] girarMotor(%s)" % (self.nombre, velocidad))

    def apagar(self):
        if self._dev:
            try:
                self._dev.stop()
            except Exception:
                pass
        print("[motor %s] apagar()" % self.nombre)


class Sensor(Dispositivo):
    def valor(self):
        if _HAY_GPIO and self._attr("pin") is not None:
            try:
                d = gpiozero.InputDevice(self._attr("pin"))
                v = int(d.value)
            except Exception:
                v = 0
        else:
            import random
            v = random.randint(0, 1023)
        print("[sensor %s] valor() -> %s" % (self.nombre, v))
        return v


class SensorUltrasonico(Sensor):
    pass


class SensorColor(Sensor):
    pass


class SensorToque(Sensor):
    pass


class SensorGiro(Sensor):
    pass


# --------------------------------------------------------------------------
#  Programa traducido desde el lenguaje fuente
# --------------------------------------------------------------------------
velocidad = 10
tiempo = 2.5
mensaje = "hola mundo"

def mover(v):
    if (v > 0):
        print(mensaje)

mover(velocidad)
