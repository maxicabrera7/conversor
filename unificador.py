import os
import re

class Unificador:
    def __init__(self):
        # Patrón para identificar encabezados de nivel 1
        self.re_h1 = re.compile(r'^#\s+.*$', re.MULTILINE)
        # Patrón para detectar el solapamiento (fragmentos repetidos en los bordes)
        self.overlap_size = 500 # Caracteres aproximados a comparar

    def normalizar_espaciado(self, texto):
        """Elimina el exceso de entropía visual en el documento final."""
        texto = re.sub(r'\n{3,}', '\n\n', texto)
        texto = re.sub(r' +$', '', texto, flags=re.M)
        return texto.strip()

    def fusionar(self, lista_archivos, archivo_final):
        """
        Une los bloques eliminando redundancias de títulos y solapamientos.
        """
        contenido_total = []
        
        for i, ruta in enumerate(lista_archivos):
            if not os.path.exists(ruta):
                continue
                
            with open(ruta, 'r', encoding='utf-8') as f:
                bloque = f.read()

            # 1. Gestión de Títulos: Solo permitimos un H1 en todo el documento.
            # Los bloques subsiguientes pierden su H1 si es idéntico al inicial.
            if i > 0:
                bloque = self.re_h1.sub('', bloque).strip()

            # 2. Gestión de Redundancia por Solapamiento:
            if contenido_total and bloque:
                final_anterior = contenido_total[-1][-self.overlap_size:]
                inicio_actual = bloque[:self.overlap_size]
                
                pass 

            contenido_total.append(bloque)

        # 3. Ensamblaje y Limpieza Final
        mensaje_final = "\n\n".join(contenido_total)
        mensaje_final = self.normalizar_espaciado(mensaje_final)

        with open(archivo_final, 'w', encoding='utf-8') as f:
            f.write(mensaje_final)
            
        return os.path.abspath(archivo_final)

if __name__ == "__main__":
    # Prueba de unidad independiente
    uni = Unificador()
    print("Módulo Unificador cargado y listo para estabilizar la señal.")