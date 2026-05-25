// ==================================================
//  CÓDIGO OBJETO OPTIMIZADO DESDE INTERMEDIO (TAC)
// ==================================================


void mover();


void mover() {
    v = param_v;
    auto txt = param_txt;
    if (v <= 0) goto L_sino1;
    Serial.println(txt);
    L_sino1:
}

void setup() {
    Serial.begin(9600);
}

void loop() {
    velocidad = 10;
    mensaje = hola mundo;
    // Parámetro cargado: velocidad
    // Parámetro cargado: mensaje
    auto t1 = mover();
    // Fin de la ejecución TAC
}