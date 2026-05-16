"""
main.py — Orquestador principal del pipeline de limpieza de documentos.
"""

import os
import re
import argparse
import time
import logging
import sys
from collections import Counter

from convertir import ejecutar_conversion
from api import AgenteLimpiador
from unificador import Unificador
from utils import limpiar_ruido_estatico, necesita_limpieza_ia


def _ratio_parrafos(texto: str) -> float:
    palabras = len(texto.split())
    if palabras == 0:
        return 0.0
    separadores = len(re.findall(r'\n\n', texto))
    return (separadores / palabras) * 100


def _bloque_es_valido(original: str, procesado: str, umbral_ratio: float = 0.3) -> bool:
    if procesado.startswith("ERROR"):
        return False
    palabras_orig = len(original.split())
    palabras_proc = len(procesado.split())
    if palabras_orig > 50 and palabras_proc < palabras_orig * 0.60:
        return False
    ratio_orig = _ratio_parrafos(original)
    ratio_proc = _ratio_parrafos(procesado)
    if ratio_orig > 0.5 and ratio_proc < umbral_ratio:
        return False
    return True


# ---------------------------------------------------------------------------
# MODO INTERACTIVO
# ---------------------------------------------------------------------------

def _preguntar(pregunta: str, default: bool = True) -> bool:
    """Pregunta s/n en terminal. Enter solo acepta el default."""
    opciones = "[S/n]" if default else "[s/N]"
    while True:
        resp = input(f"  {pregunta} {opciones}: ").strip().lower()
        if resp == "":
            return default
        if resp in ("s", "si", "y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print("  Respuesta no válida. Ingresá s o n.")


def _detectar_y_preguntar(texto: str) -> dict:
    """
    Escanea el MD extraído, muestra lo que encontró y pregunta qué limpiar.
    Devuelve un dict con las opciones elegidas por el usuario.
    """
    print("\n" + "═" * 50)
    print(" ANÁLISIS DEL DOCUMENTO")
    print("═" * 50)

    opciones = {}

    # ── Imágenes ──────────────────────────────────────────────────────────
    imagenes = re.findall(r'!\[.*?\]\([^)]*\)', texto)
    if imagenes:
        print(f"\n  Se encontraron {len(imagenes)} referencia(s) a imágenes.")
        print(f"  Ejemplo: {imagenes[0][:60]}")
        opciones["quitar_imagenes"] = _preguntar("¿Eliminar referencias a imágenes?")
    else:
        opciones["quitar_imagenes"] = False

    # ── Líneas repetidas (headers/footers) ────────────────────────────────
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]
    conteo = Counter(lineas)
    repetidas = [(l, c) for l, c in conteo.items() if c >= 3]
    if repetidas:
        print(f"\n  Se encontraron {len(repetidas)} línea(s) repetidas 3+ veces "
              f"(probables encabezados/pies de página):")
        for linea, veces in repetidas[:3]:
            print(f"    ({veces}x) {linea[:70]}")
        opciones["quitar_repetidas"] = _preguntar("¿Eliminar estas líneas repetidas?")
    else:
        opciones["quitar_repetidas"] = False

    # ── Números de página ─────────────────────────────────────────────────
    nros_pagina = re.findall(r'^\s*\d{1,3}\s*$', texto, flags=re.MULTILINE)
    if nros_pagina:
        print(f"\n  Se encontraron {len(nros_pagina)} número(s) de página sueltos.")
        opciones["quitar_nros_pagina"] = _preguntar("¿Eliminar números de página?")
    else:
        opciones["quitar_nros_pagina"] = False

    print("\n" + "═" * 50)
    return opciones


def _aplicar_opciones(texto: str, opciones: dict) -> str:
    """Aplica las opciones elegidas por el usuario al texto."""
    if opciones.get("quitar_imagenes"):
        texto = re.sub(r'!\[.*?\]\([^)]*\)', '', texto)

    if opciones.get("quitar_repetidas"):
        lineas_todas = texto.split('\n')
        conteo = Counter(l.strip() for l in lineas_todas if l.strip())
        repetidas = {l for l, c in conteo.items() if c >= 3}
        lineas_todas = [l for l in lineas_todas if l.strip() not in repetidas]
        texto = '\n'.join(lineas_todas)

    if opciones.get("quitar_nros_pagina"):
        texto = re.sub(r'^\s*\d{1,3}\s*$', '', texto, flags=re.MULTILINE)

    # Colapsar saltos excesivos que puedan quedar tras la limpieza
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


# ---------------------------------------------------------------------------
# ORQUESTADOR
# ---------------------------------------------------------------------------

class Orquestador:
    def __init__(self, chunk_words: int = 3000, overlap_words: int = 600):
        self.agente = AgenteLimpiador()
        self.unificador = Unificador()
        self.chunk_words = chunk_words
        self.overlap_words = overlap_words
        self.logger = self._configurar_logger()

    def _configurar_logger(self) -> logging.Logger:
        logger = logging.getLogger("OrquestadorPro")
        logger.setLevel(logging.ERROR)
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            logger.addHandler(handler)
        return logger

    def fragmentar_texto(self, texto: str) -> list[str]:
        matches = list(re.finditer(r'\S+', texto))
        if not matches:
            return [texto]
        bloques = []
        total_palabras = len(matches)
        paso = self.chunk_words - self.overlap_words
        for i in range(0, total_palabras, paso):
            fin_palabra = min(i + self.chunk_words, total_palabras)
            idx_inicio = matches[i].start()
            idx_fin = matches[fin_palabra - 1].end()
            bloques.append(texto[idx_inicio:idx_fin])
            if i + self.chunk_words >= total_palabras:
                break
        return bloques

    def procesar_archivo(self, ruta_pdf: str) -> None:
        nombre_base = os.path.splitext(os.path.basename(ruta_pdf))[0]
        temp_dir = f"temp_{nombre_base}"
        os.makedirs(temp_dir, exist_ok=True)

        # ── FASE 1: EXTRACCIÓN BRUTA ──────────────────────────────────────
        print(f"[*] Fase 1: Extrayendo señal original de '{nombre_base}'...")
        resultado = ejecutar_conversion(ruta_pdf, self.logger, sin_imagenes=False)
        if resultado == "error":
            print("[!] La extracción falló. Abortando.")
            return

        ruta_raw_md = os.path.join(f"MD_{nombre_base}", f"{nombre_base}.md")
        if not os.path.exists(ruta_raw_md):
            print(f"[!] No se encontró el MD crudo en '{ruta_raw_md}'.")
            return

        with open(ruta_raw_md, 'r', encoding='utf-8') as f:
            texto_crudo = f.read()

        # ── FASE 1.5: INTERACTIVO — qué querés limpiar ───────────────────
        opciones = _detectar_y_preguntar(texto_crudo)
        texto_crudo = _aplicar_opciones(texto_crudo, opciones)

        # ── FASE 2: SEGMENTACIÓN Y LIMPIEZA IA ───────────────────────────
        bloques = self.fragmentar_texto(texto_crudo)
        archivos_limpios: list[str] = []
        calls_api = 0
        calls_saltadas = 0
        calls_revertidas = 0

        print(f"\n[*] Fase 2: Procesando {len(bloques)} bloques "
              f"(~{self.chunk_words} palabras/bloque, overlap={self.overlap_words})...")

        for i, contenido in enumerate(bloques):
            ruta_chunk = os.path.join(temp_dir, f"bloque_{i:02d}_clean.md")

            if os.path.exists(ruta_chunk):
                print(f"  [>] Bloque {i:02d}: en caché — saltando.")
                archivos_limpios.append(ruta_chunk)
                continue

            if necesita_limpieza_ia(contenido):
                print(f"  [>] Bloque {i:02d}: enviando a IA...")
                texto_limpio = self.agente.procesar_bloque(contenido)
                calls_api += 1
                if not _bloque_es_valido(contenido, texto_limpio):
                    print(f"  [!] Bloque {i:02d}: salida IA rechazada. Usando original.")
                    texto_limpio = contenido
                    calls_revertidas += 1
                if i < len(bloques) - 1:
                    time.sleep(65)
            else:
                print(f"  [>] Bloque {i:02d}: limpio — sin API.")
                texto_limpio = contenido
                calls_saltadas += 1

            with open(ruta_chunk, 'w', encoding='utf-8') as f:
                f.write(texto_limpio)
            archivos_limpios.append(ruta_chunk)

        # ── FASE 3: UNIFICACIÓN ───────────────────────────────────────────
        print("[*] Fase 3: Ensamblando documento final...")
        salida_final = f"{nombre_base}_LIMPIO.md"
        self.unificador.fusionar(archivos_limpios, salida_final)

        print(f"\n{'═' * 45}")
        print(f" OPTIMIZACIÓN COMPLETADA")
        print(f" Calls API usadas:    {calls_api}")
        print(f" Bloques sin API:     {calls_saltadas}")
        print(f" Bloques revertidos:  {calls_revertidas}")
        print(f" Archivo final:       {salida_final}")
        print(f"{'═' * 45}")


# ---------------------------------------------------------------------------
# INTERFAZ CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="main",
        description="Auditor de Documentos Pro — Pipeline OCR → Markdown limpio",
    )
    parser.add_argument("entrada", help="Ruta del archivo (PDF, PPTX, DOCX, XLSX)")
    parser.add_argument("--size", type=int, default=3000,
                        help="Palabras por bloque (default: 3000)")
    parser.add_argument("--overlap", type=int, default=600,
                        help="Palabras de solapamiento entre bloques (default: 600)")
    args = parser.parse_args()

    ruta_abs = os.path.abspath(args.entrada)
    if not os.path.exists(ruta_abs):
        print(f"[!] Error: '{args.entrada}' no existe.")
        return

    orquestador = Orquestador(chunk_words=args.size, overlap_words=args.overlap)
    orquestador.procesar_archivo(ruta_abs)


if __name__ == "__main__":
    main()