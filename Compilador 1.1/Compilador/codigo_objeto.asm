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
    msg2: db "  1.  velocidad = 10", 0
    msg3: db "  2.  mensaje = hola mundo", 0
    msg4: db "  3.  func_mover:", 0
    msg5: db "  4.  v = param_v", 0
    msg6: db "  5.  txt = param_txt", 0
    msg7: db "  6.  if v <= 0 goto L_sino1", 0
    msg8: db "  7.  print txt", 0
    msg9: db "  8.  L_sino1:", 0
    msg10: db "  9.  return", 0
    msg11: db " 10.  param velocidad", 0
    msg12: db " 11.  param mensaje", 0
    msg13: db " 12.  t1 = call mover, 2", 0
    msg14: db " 13.  halt", 0
    msg15: db "--------------------------------------------------", 0
    msg16: db "Ejecucion del codigo objeto completada.", 0

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

    xor     eax, eax
    add     rsp, 32
    pop     rbp
    ret
