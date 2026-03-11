from graphviz import Digraph
import os

class NodoAST:
    def __init__(self, nombre, hijos=None):
        self.nombre = nombre
        self.hijos = []
        if hijos:
            for h in hijos:
                if isinstance(h, list):
                    self.hijos.extend(h)
                else:
                    self.hijos.append(h)

    def agregar_hijo(self, hijo):
        self.hijos.append(hijo)

    def __repr__(self):
        return f"NodoAST({self.nombre})"

def graficar_arbol(nodo_raiz, nombre_archivo='arbol_sintactico'):
    dot = Digraph(comment='Árbol Sintáctico')
    dot.attr(rankdir='TB')

    def agregar(dot, nodo, parent_id=None, contador=[0]):
        actual_id = f"n{contador[0]}"
        label = nodo.nombre
        dot.node(actual_id, label, shape='ellipse', style='filled', fillcolor='#D0E6FA')
        if parent_id:
            dot.edge(parent_id, actual_id)
        for hijo in nodo.hijos:
            contador[0] += 1
            agregar(dot, hijo, actual_id, contador)

    agregar(dot, nodo_raiz)

    output_path = os.path.abspath(nombre_archivo)
    dot.render(filename=output_path, format='png', cleanup=False)

    print(f"EXITOSO: Árbol generado en: {output_path}.png")

    try:
        os.startfile(output_path + ".png")
    except Exception as e:
        print("FALLO: No se pudo abrir automáticamente:", e)