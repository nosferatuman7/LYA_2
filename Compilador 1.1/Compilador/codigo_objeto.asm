;; ============================================================
;;  CODIGO OBJETO DE BAJO NIVEL  (ensamblador x86-64 / NASM Win64)
;;  Generado automaticamente por el compilador.
;;
;;  Compilar y ejecutar (Windows, con NASM y MinGW-w64):
;;     nasm -f win64 codigo_objeto.asm -o codigo_objeto.obj
;;     gcc codigo_objeto.obj -o codigo_objeto.exe
;;     codigo_objeto.exe
;; ============================================================

default rel
extern puts
global main

section .data
    msg0: db "=== Codigo objeto - bajo nivel ===", 0
    msg1: db "--------------------------------------------------", 0
    msg2: db "  1.  miServo = new servo(pin=9)", 0
    msg3: db "  2.  miLed = new led(pin=13)", 0
    msg4: db "  3.  L_mientras1:", 0
    msg5: db "  4.  if true != true goto L_fin_mientras2", 0
    msg6: db "  5.  t1 = miLed->apagar()", 0
    msg7: db "  6.  t2 = miServo->girarServo(0)", 0
    msg8: db "  7.  delay 1000", 0
    msg9: db "  8.  t3 = miLed->encender()", 0
    msg10: db "  9.  delay 200", 0
    msg11: db " 10.  t4 = miLed->apagar()", 0
    msg12: db " 11.  t5 = miServo->girarServo(90)", 0
    msg13: db " 12.  delay 1000", 0
    msg14: db " 13.  t6 = miLed->encender()", 0
    msg15: db " 14.  delay 200", 0
    msg16: db " 15.  t7 = miLed->apagar()", 0
    msg17: db " 16.  t8 = miServo->girarServo(180)", 0
    msg18: db " 17.  delay 1000", 0
    msg19: db " 18.  t9 = miLed->encender()", 0
    msg20: db " 19.  delay 200", 0
    msg21: db " 20.  goto L_mientras1", 0
    msg22: db " 21.  L_fin_mientras2:", 0
    msg23: db " 22.  halt", 0
    msg24: db "--------------------------------------------------", 0
    msg25: db "Ejecucion del codigo objeto completada.", 0

section .text
main:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 32          ; espacio de sombra (Win64 ABI)

    lea     rcx, [msg0]
    call    puts
    lea     rcx, [msg1]
    call    puts
    lea     rcx, [msg2]
    call    puts
    lea     rcx, [msg3]
    call    puts
    lea     rcx, [msg4]
    call    puts
    lea     rcx, [msg5]
    call    puts
    lea     rcx, [msg6]
    call    puts
    lea     rcx, [msg7]
    call    puts
    lea     rcx, [msg8]
    call    puts
    lea     rcx, [msg9]
    call    puts
    lea     rcx, [msg10]
    call    puts
    lea     rcx, [msg11]
    call    puts
    lea     rcx, [msg12]
    call    puts
    lea     rcx, [msg13]
    call    puts
    lea     rcx, [msg14]
    call    puts
    lea     rcx, [msg15]
    call    puts
    lea     rcx, [msg16]
    call    puts
    lea     rcx, [msg17]
    call    puts
    lea     rcx, [msg18]
    call    puts
    lea     rcx, [msg19]
    call    puts
    lea     rcx, [msg20]
    call    puts
    lea     rcx, [msg21]
    call    puts
    lea     rcx, [msg22]
    call    puts
    lea     rcx, [msg23]
    call    puts
    lea     rcx, [msg24]
    call    puts
    lea     rcx, [msg25]
    call    puts

    xor     eax, eax
    add     rsp, 32
    pop     rbp
    ret
