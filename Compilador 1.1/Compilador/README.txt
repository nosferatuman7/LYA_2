GRAMATICA EN EBNF

programa           ::= "INICIO" bloque_codigo "FIN" ;
bloque_codigo      ::= "{" lista_declaraciones "}" ;
lista_declaraciones::= lista_declaraciones declaracion
                     | lista_declaraciones control
                     | lista_declaraciones dispositivo
                     | lista_declaraciones funcion
                     | declaracion
                     | control
                     | dispositivo
                     | funcion ;
declaracion        ::= tipo ID ";" 
                   | tipo ID ASIGNACION expresion ";" 
                   | tipo ID CORCHETE_A NUMERO CORCHETE_B ";" 
                   | ID CORCHETE_A NUMERO CORCHETE_B ASIGNACION expresion ";" 
                   | IMPRIMIR "(" expresion ")" ";" ;
tipo               ::= "ENTERO" 
                   | "REAL_TIPO" 
                   | "BOOLEANO" 
                   | "CADENA_TIPO" ;
tipo_dispositivo   ::= "SERVO" 
                   | "LED" 
                   | "MOTOR" 
                   | "SENSOR" 
                   | "BUZZER" 
                   | "SENSOR_ULTRASONICO" 
                   | "SENSOR_COLOR" 
                   | "SENSOR_TOQUE" 
                   | "SENSOR_GIRO" ;
control            ::= si
                   | mientras
                   | para
                   | romper ;
si                 ::= "SI" "(" expresion ")" bloque_codigo
                   | "SI" "(" expresion ")" bloque_codigo ID bloque_codigo ;
mientras           ::= "MIENTRAS" "(" expresion ")" bloque_codigo ;
para               ::= "PARA" "(" asignacion_para ";" expresion ";" actualizacion_para ")" bloque_codigo ;
asignacion_para    ::= tipo ID ASIGNACION expresion 
                   | ID ASIGNACION expresion ;
actualizacion_para ::= ID ASIGNACION expresion 
                   | ID "++" 
                   | ID "--" ;
funcion            ::= "FUNC" ID "(" parametros ")" bloque_codigo ;
parametros         ::= parametro 
                   | parametro "," parametros 
                   | empty ;
parametro          ::= tipo ID ;
dispositivo        ::= definir_dispositivo
                   | accion_dispositivo ;
definir_dispositivo::= tipo_dispositivo ID ASIGNACION objeto_dispositivo ";" ;
objeto_dispositivo ::= "{" lista_atributos "}" ;
lista_atributos    ::= lista_atributos "," atributo
                   | atributo ;
atributo           ::= ID ASIGNACION expresion ;
accion_dispositivo ::= ID "->" accion "(" expresion_opt ")" ";" ;
accion             ::= "ENCENDER"
                   | "APAGAR"
                   | "VALOR"
                   | "GIRARSERVO"
                   | "GIRARMOTOR" ;
expresion_opt      ::= expresion
                   | empty ;
expresion          ::= expresion op_binario expresion
                   | op_unario expresion
                   | "(" expresion ")"
                   | ID
                   | ID CORCHETE_A NUMERO CORCHETE_B
                   | NUMERO
                   | REAL
                   | CADENA_TEXTO
                   | TRUE
                   | FALSE ;
op_binario         ::= "SUMA" 
                   | "RESTA" 
                   | "MULTIPLICACION" 
                   | "DIVISION" 
                   | "MODULO" 
                   | "IGUAL" 
                   | "DIFERENTE" 
                   | "MENORQUE" 
                   | "MAYORQUE" 
                   | "MENORIGUAL" 
                   | "MAYORIGUAL" 
                   | "AND" 
                   | "OR" ;
op_unario          ::= "NOT" 
                   | "RESTA" ;
