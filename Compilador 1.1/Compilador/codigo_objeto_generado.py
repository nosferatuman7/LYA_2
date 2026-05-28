// ==========================================================================
//  CODIGO OBJETO GENERADO AUTOMATICAMENTE
//  Destino: Arduino (sketch .ino -> compilar a .hex con avr-gcc / IDE)
//
//  Para compilar directamente a .hex desde Python:
//    gen = GeneradorCodigoObjeto()
//    ruta_hex = gen.compilar_hex(ast)   # requiere arduino-cli en PATH
//
//  O con arduino-cli manualmente:
//    arduino-cli compile --fqbn arduino:avr:uno sketch/ --output-dir out/
// ==========================================================================

#include <Servo.h>

Servo miServo_servo;

void setup() {
    Serial.begin(9600);
    miServo_servo.attach(9);
    pinMode(13, OUTPUT);
}

void loop() {
// dispositivo servo 'miServo' -> pin 9 (configurado en setup)
// dispositivo led 'miLed' -> pin 13 (configurado en setup)
while (true) {
    digitalWrite(13, HIGH);
    miServo_servo.write(0);;
    delay(1000);
    digitalWrite(13, LOW);
    delay(200);
    digitalWrite(13, HIGH);
    miServo_servo.write(90);;
    delay(1000);
    digitalWrite(13, LOW);
    delay(200);
    digitalWrite(13, HIGH);
    miServo_servo.write(180);;
    delay(1000);
    digitalWrite(13, LOW);
    delay(200);
}
}
