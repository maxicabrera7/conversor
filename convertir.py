import pymupdf4llm
from markitdown import MarkItDown
from pptx import Presentation
import pandas as pd
import sys
import os
import re
import time
import logging
import argparse

# Intentar cargar tqdm para la barra de progreso
try:
    from tqdm import tqdm
    TQDM_DISPONIBLE = True
except ImportError:
    TQDM_DISPONIBLE = False

EXTENSIONES_VALIDAS = ['.pdf', '.pptx', '.docx', '.xlsx']
MAX_REINTENTOS = 2

# --- PROCESAMIENTO DE TEXTO Y LIMPIEZA ---

def limpiar_markdown(texto):
    """Elimina ruido visual y normaliza el espaciado para alimentar a la IA."""
    # Más de dos saltos de línea -> Solo dos
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    # Espacios al final de línea -> Fuera
    texto = re.sub(r' +$', '', texto, flags=re.M)
    # Caracteres nulos (comunes en PDFs basura) -> Fuera
    texto = texto.replace('\x00', '')
    return texto.strip()

# --- MOTORES ESPECÍFICOS POR FORMATO ---

def procesar_pptx_mejorado(ruta):
    """Estructura el PowerPoint por diapositivas e incluye notas del orador en blockquotes."""
    prs = Presentation(ruta)
    output = [f"# PRESENTACIÓN: {os.path.basename(ruta)}\n"]
    
    for i, slide in enumerate(prs.slides, 1):
        output.append(f"\n---\n## DIAPOSITIVA {i}\n")
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                output.append(shape.text.strip())
        
        if slide.has_notes_slide:
            notas = slide.notes_slide.notes_text_frame.text.strip()
            if notas:
                output.append(f"\n> **Notas del Orador:** {notas}")
                
    return "\n".join(output)

def procesar_xlsx_mejorado(ruta):
    """Convierte cada hoja de Excel en una tabla Markdown independiente con encabezados claros."""
    output = [f"# EXCEL: {os.path.basename(ruta)}\n"]
    
    with pd.ExcelFile(ruta) as xls:
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)
            output.append(f"\n## HOJA: {sheet_name}\n")
            if not df.empty:
                output.append(df.to_markdown(index=False))
            else:
                output.append("*Esta hoja está vacía*")
    return "\n".join(output)

# --- LÓGICA DE CONVERSIÓN ---

# --- REEMPLAZA ESTA FUNCIÓN EN convertir.py ---

def ejecutar_conversion(ruta_archivo, logger, sin_imagenes=False):
    """Maneja la conversión individual con parámetros sincronizados."""
    ext = os.path.splitext(ruta_archivo)[1].lower()
    nombre_base = os.path.splitext(os.path.basename(ruta_archivo))[0]
    carpeta_destino = os.path.join(os.path.dirname(ruta_archivo), f"MD_{nombre_base}")
    md_esperado = os.path.join(carpeta_destino, f"{nombre_base}.md")

    if os.path.isfile(md_esperado):
        return "omitido"

    os.makedirs(carpeta_destino, exist_ok=True)
    ultimo_error = None

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            if ext == '.pdf':
                dir_actual = os.getcwd()
                os.chdir(carpeta_destino)
                try:
                    md_text = pymupdf4llm.to_markdown(ruta_archivo, write_images=not sin_imagenes, margins=(50, 0, 50, 0))
                    
                finally:
                    os.chdir(dir_actual)
            
            elif ext == '.pptx':
                md_text = procesar_pptx_mejorado(ruta_archivo)
            
            elif ext == '.xlsx':
                md_text = procesar_xlsx_mejorado(ruta_archivo)
            
            else: # .docx
                md_engine = MarkItDown()
                md_text = md_engine.convert(ruta_archivo).text_content

            contenido_final = limpiar_markdown(md_text)
            with open(md_esperado, "w", encoding="utf-8") as f:
                f.write(contenido_final)
            
            return "ok"

        except Exception as e:
            ultimo_error = e
            time.sleep(0.5)

    # Protección de muelle: evita el AttributeError si el logger es None
    if logger:
        logger.error(f"FALLO en {nombre_base}: {ultimo_error}")
    else:
        print(f"[!] Error en {nombre_base}: {ultimo_error}")
        
    return "error"

# --- INTERFAZ Y EJECUCIÓN ---

def resolver_ruta_inteligente(entrada):
    """Resuelve la ruta si el usuario olvida la extensión."""
    if os.path.isfile(entrada): return os.path.abspath(entrada)
    for ext in EXTENSIONES_VALIDAS:
        candidato = entrada + ext
        if os.path.isfile(candidato): return os.path.abspath(candidato)
    return None

def main():
    parser = argparse.ArgumentParser(prog="cvt", description="Conversor Universidad Pro")
    parser.add_argument("entrada", help="Archivo o carpeta")
    parser.add_argument("--quiet", "-q", action="store_true", help="Modo silencioso")
    args = parser.parse_args()

    ruta_abs = os.path.abspath(args.entrada)
    log_dir = ruta_abs if os.path.isdir(ruta_abs) else os.path.dirname(ruta_abs)
    
    logging.basicConfig(
        filename=os.path.join(log_dir, "errores.log"),
        level=logging.ERROR,
        format="%(asctime)s - %(message)s"
    )
    logger = logging.getLogger()

    contadores = {"ok": 0, "omitido": 0, "error": 0}

    if os.path.isdir(ruta_abs):
        archivos = [os.path.join(ruta_abs, f) for f in os.listdir(ruta_abs) 
                   if os.path.splitext(f)[1].lower() in EXTENSIONES_VALIDAS]
        
        if not archivos:
            print("[!] No hay archivos compatibles.")
            return

        iterador = tqdm(archivos, desc="Convirtiendo biblioteca", unit="fich", ncols=80) if TQDM_DISPONIBLE and not args.quiet else archivos
        
        for r in iterador:
            res = ejecutar_conversion(r, logger, sin_imagenes=False)
            contadores[res] += 1
    else:
        ruta = resolver_ruta_inteligente(args.entrada)
        if not ruta:
            print(f"[!] Error: No se encontró '{args.entrada}'")
            return
        res = ejecutar_conversion(ruta, logger, sin_imagenes=False)
        contadores[res] += 1

    if not args.quiet:
        print("\n" + "═"*35)
        print(f" PROCESO COMPLETADO")
        print(f" 🗸 Convertidos: {contadores['ok']}")
        print(f" ↷ Ignorados:   {contadores['omitido']}")
        print(f" ✗ Fallidos:    {contadores['error']}")
        print("═"*35)
        if contadores['error'] > 0:
            print(f"Detalles en: {os.path.join(log_dir, 'errores.log')}")

if __name__ == "__main__":
    main()