import os
import argparse
import time
import logging
import sys
from convertir import ejecutar_conversion
from api import AgenteLimpiador
from unificador import Unificador

class Orquestador:
    def __init__(self, chunk_words=3250, overlap_words=500):
        self.agente = AgenteLimpiador()
        self.unificador = Unificador()
        self.chunk_words = chunk_words
        self.overlap_words = overlap_words
        self.logger = self._configurar_logger()

    def _configurar_logger(self):
        """Configura un canal de log para evitar errores de NoneType."""
        logger = logging.getLogger("OrquestadorPro")
        logger.setLevel(logging.ERROR)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def fragmentar_texto(self, texto):
        """
        Implementa una Ventana de Solapamiento (Sliding Window).
        Reduce el ruido semántico al no cortar conceptos a la mitad.
        """
        palabras = texto.split()
        bloques = []
        paso = self.chunk_words - self.overlap_words
        
        for i in range(0, len(palabras), paso):
            bloque = " ".join(palabras[i:i + self.chunk_words])
            bloques.append(bloque)
            if i + self.chunk_words >= len(palabras):
                break
        return bloques

    def procesar_archivo(self, ruta_pdf, sin_imagenes=False):
        nombre_base = os.path.splitext(os.path.basename(ruta_pdf))[0]
        temp_dir = f"temp_{nombre_base}"
        os.makedirs(temp_dir, exist_ok=True)

        # 1. EXTRACCIÓN BRUTA
        print(f"[*] Fase 1: Extrayendo señal original de '{nombre_base}'...")
        resultado = ejecutar_conversion(ruta_pdf, self.logger, sin_imagenes)
        
        if resultado == "error":
            print("[!] La extracción falló. Abortando misión.")
            return

        # Buscamos el MD generado por el conversor
        ruta_raw_md = os.path.join(f"MD_{nombre_base}", f"{nombre_base}.md")
        if not os.path.exists(ruta_raw_md):
            print(f"[!] No se encontró el archivo crudo en {ruta_raw_md}")
            return

        with open(ruta_raw_md, 'r', encoding='utf-8') as f:
            texto_crudo = f.read()

        # 2. SEGMENTACIÓN LÓGICA
        bloques = self.fragmentar_texto(texto_crudo)
        archivos_limpios = []

        # 3. LIMPIEZA POR BLOQUES (IA)
        print(f"[*] Fase 2: Decodificando {len(bloques)} bloques (Gratis Tier)...")
        for i, contenido in enumerate(bloques):
            ruta_chunk = os.path.join(temp_dir, f"bloque_{i:02d}_clean.md")
            
            if os.path.exists(ruta_chunk):
                print(f"  [>] Bloque {i} ya procesado. Recuperando de caché.")
                archivos_limpios.append(ruta_chunk)
                continue

            print(f"  [>] Procesando bloque {i}...")
            texto_limpio = self.agente.procesar_bloque(contenido)
            
            with open(ruta_chunk, 'w', encoding='utf-8') as f:
                f.write(texto_limpio)
            
            archivos_limpios.append(ruta_chunk)
            # Estabilizador de canal para evitar el Error 429
            time.sleep(65)

        # 4. UNIFICACIÓN Y SALIDA FINAL
        print("[*] Fase 3: Estabilizando mensaje y eliminando redundancias...")
        salida_final = f"{nombre_base}_LIMPIO.md"
        self.unificador.fusionar(archivos_limpios, salida_final)
        
        print(f"\n{'═'*40}")
        print(f" OPTIMIZACIÓN COMPLETADA")
        print(f" Archivo listo para estudio: {salida_final}")
        print(f"{'═'*40}")

def main():
    parser = argparse.ArgumentParser(description="Auditor de Documentos Pro")
    parser.add_argument("entrada", help="Ruta del archivo PDF")
    parser.add_argument("--no-img", action="store_true", help="Omitir imágenes")
    parser.add_argument("--size", type=int, default=3250, help="Palabras por bloque")
    args = parser.parse_args()

    # Resolver ruta para evitar errores de comillas/espacios
    ruta_abs = os.path.abspath(args.entrada)
    if not os.path.exists(ruta_abs):
        print(f"[!] Error: La fuente '{args.entrada}' no existe.")
        return

    orquestador = Orquestador(chunk_words=args.size)
    orquestador.procesar_archivo(ruta_abs, sin_imagenes=args.no_img)

if __name__ == "__main__":
    main()