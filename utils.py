"""
utils.py — Fuente única de verdad para limpieza de texto.
Centraliza las funciones que antes vivían duplicadas en convertir.py y main.py.

Cambios respecto a la versión anterior:
  - limpiar_ruido_estatico: preservación explícita de saltos de párrafo
    garantizada. Se documenta por qué el regex de números de página NO
    afecta los \n\n (opera línea a línea, no sobre bloques).
  - necesita_limpieza_ia: sin cambios de lógica; se amplía la documentación
    de la heurística para facilitar calibración futura.
  - limpiar_markdown: sin cambios.
"""
import re


def limpiar_ruido_estatico(texto: str) -> str:
    """
    Elimina ruido OCR conocido y predecible con regex puro.
    Sin API, sin costo. Corre siempre antes de cualquier decisión de IA.

    Qué elimina:
    - Números de página sueltos (líneas con solo 1-3 dígitos).
    - Headers repetitivos de PDFs universitarios (CARRERA:, Cátedra:, T.U.I.).
    - Exceso de saltos de línea consecutivos (colapsa a máximo dos).

    Qué NO toca:
    - Los saltos de párrafo (\n\n) entre bloques de contenido real.
      NOTA: el regex de números de página usa re.MULTILINE y opera línea
      a línea; un número de página suelto tiene sus propios \n antes y
      después. Al eliminarlo, puede dejar \n\n\n que el último paso colapsa
      a \n\n — nunca a \n. La estructura de párrafos siempre se preserva.
    - Referencias a imágenes Markdown (![](...)) → las conserva intactas.
      El Orquestador decidirá qué hacer con ellas según --no-img.
    """
    # Números de página sueltos
    texto = re.sub(r'^\s*\d{1,3}\s*$', '', texto, flags=re.MULTILINE)
    # Docente / firma al pie de página
    texto = re.sub(r'^Docente titular:.*$', '', texto, flags=re.MULTILINE | re.IGNORECASE)
    # Headers/footers repetitivos: cualquier línea que aparezca 3+ veces
    # es casi con certeza un encabezado o pie de página de PDF.
    # Cubre casos como "Universidad Nacional... CARRERA:T.U.I CátedraCOMUNICACION"
    # que no matchean ^CARRERA: porque el texto está embebido en la línea.
    from collections import Counter
    lineas = texto.split('\n')
    conteo = Counter(l.strip() for l in lineas if l.strip())
    repetidas = {l for l, c in conteo.items() if c >= 3}
    lineas = [l for l in lineas if l.strip() not in repetidas]
    texto = '\n'.join(lineas)
    # Colapsa 3+ saltos consecutivos a exactamente dos (preserva párrafos)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


def limpiar_markdown(texto: str) -> str:
    """
    Normalización tipográfica ligera para texto ya extraído.
    Úsala después de la conversión de formato, antes de escribir al disco.

    Qué hace:
    - Colapsa más de dos saltos de línea consecutivos.
    - Elimina espacios al final de cada línea.
    - Elimina caracteres nulos (comunes en PDFs mal exportados).
    """
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    texto = re.sub(r' +$', '', texto, flags=re.MULTILINE)
    texto = texto.replace('\x00', '')
    return texto.strip()


def necesita_limpieza_ia(texto: str, umbral: float = 0.015) -> bool:
    """
    Decide si un bloque justifica gastar una request de API.

    Criterio: ratio de ruido OCR residual sobre el total de caracteres.
    Si el bloque ya está limpio tras limpiar_ruido_estatico, se saltea la IA.

    Calibración del umbral (0.015 = 1.5%):
    - Demasiado bajo (< 0.010): envía casi todos los bloques a la IA,
      incrementa costos y riesgo de degradación estructural.
    - Demasiado alto (> 0.030): deja pasar bloques con ruido OCR visible.
    - 0.015 es conservador: prefiere limpiar de más a dejar ruido.

    Args:
        texto:   Bloque de texto ya pre-limpiado con limpiar_ruido_estatico.
        umbral:  Fracción mínima de basura para activar la IA (default: 1.5%).

    Returns:
        True si el bloque necesita corrección por IA, False si está limpio.
    """
    total = len(texto)
    if total < 100:
        return False

    # Caracteres fuera del rango latino/español estándar → señal de ruido OCR
    chars_raros = len(re.findall(
        r'[^\x00-\x7FÁÉÍÓÚáéíóúñÑüÜ¿¡€°\n\r\t]', texto
    ))
    # Líneas muy cortas sin contenido semántico (fragmentos rotos de OCR)
    lineas = texto.split('\n')
    lineas_basura = sum(
        1 for linea in lineas
        if linea.strip() and len(linea.strip()) < 4 and not linea.strip().startswith('#')
    )

    ratio = (chars_raros + lineas_basura * 10) / total
    return ratio > umbral
