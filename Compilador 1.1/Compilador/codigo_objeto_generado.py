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


void mover(int v) {
    if ((v > 0)) {
        Serial.println(mensaje);
    }
}


void setup() {
    Serial.begin(9600);
}

void loop() {
int velocidad = 10;
float tiempo = 2.5;
String mensaje = "hola mundo";
mover(velocidad);
}
