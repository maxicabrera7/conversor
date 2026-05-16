"""
unificador.py — Ensambla los bloques procesados en un documento coherente.

Cambios respecto a la versión anterior:
  - Ventana de búsqueda en SequenceMatcher aumentada de 80 a 250 líneas.
    Con chunks de 3000 palabras, 80 líneas era insuficiente (~30% del bloque).
  - Normalización de headings reforzada: ahora elimina diacríticos/tildes
    además de puntuación. Cubre los casos donde Gemini altera sutilmente
    el texto de un encabezado (ej: "Símbolos" → "Simbolos").
  - Umbral de SequenceMatcher reducido de 4 a 3 líneas útiles consecutivas,
    compensado por la ventana más amplia para evitar falsos positivos.
  - Estrategia de deduplicación sin cambios estructurales (dos capas).

Estrategia de deduplicación (dos capas):
  1. Anclas de headings (primaria): detecta el primer H2/H3 del bloque actual
     y lo busca en la cola del bloque anterior. Si coincide, descarta todo
     lo que precede a ese heading en el bloque actual.

  2. SequenceMatcher sobre texto normalizado (fallback): si no hay heading
     de anclaje, compara líneas normalizadas para absorber micro-ediciones
     del modelo sin falsos positivos.
"""

import os
import re
import unicodedata
from difflib import SequenceMatcher


def _quitar_diacriticos(texto: str) -> str:
    """
    Convierte 'Símbolos significantes' → 'Simbolos significantes'.
    Cubre los casos donde la IA o el OCR añaden/quitan tildes en headings.
    """
    nfkd = unicodedata.normalize('NFD', texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


class Unificador:
    # Detecta H2 o H3 al inicio de una línea
    RE_HEADING_ANCLA = re.compile(r'^(#{2,3})\s+(.+)$')
    RE_H1 = re.compile(r'^#\s+.*$', re.MULTILINE)

    # Ventana de búsqueda para solapamiento. 250 líneas ≈ 60-70% de un chunk
    # de 3000 palabras, suficiente para atrapar cualquier borde duplicado.
    VENTANA_LINEAS = 250

    # Mínimo de líneas útiles contiguas para confirmar solapamiento.
    # 3 es más sensible que 4 pero la ventana amplia filtra falsos positivos.
    UMBRAL_SECUENCIA = 3

    # ------------------------------------------------------------------ #
    #  Capa 1 — Anclas de headings                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalizar_heading(texto: str) -> str:
        """
        Normalización agresiva para comparación de headings:
          1. Minúsculas.
          2. Elimina diacríticos (tildes, diéresis).
          3. Elimina puntuación terminal y espacios extra.
          4. Colapsa espacios internos múltiples.

        Esto cubre:
          - Variaciones de acento introducidas por la IA.
          - Diferencias de puntuación al final del título.
          - Espacios extras que pymupdf4llm a veces inserta.
        """
        texto = texto.strip().lower()
        texto = _quitar_diacriticos(texto)
        texto = re.sub(r'[^\w\s]', '', texto)   # elimina puntuación
        texto = re.sub(r'\s+', ' ', texto)       # colapsa espacios
        return texto.strip()

    def _ancla_por_heading(
        self, texto_anterior: str, texto_actual: str
    ) -> str | None:
        """
        Busca el primer H2/H3 del bloque actual en la cola del bloque anterior.
        Si lo encuentra con normalización agresiva, descarta el solapamiento.

        Returns:
            Texto recortado si se detectó solapamiento, None si no hay ancla.
        """
        lineas_act = texto_actual.splitlines()

        # Hallar el primer heading del bloque actual
        idx_heading = None
        heading_norm = None
        for i, linea in enumerate(lineas_act):
            m = self.RE_HEADING_ANCLA.match(linea)
            if m:
                idx_heading = i
                heading_norm = self._normalizar_heading(m.group(2))
                break

        if idx_heading is None:
            return None

        # Buscar en la cola del bloque anterior (ampliada a VENTANA_LINEAS)
        lineas_ant = texto_anterior.splitlines()
        cola = lineas_ant[-self.VENTANA_LINEAS:]

        for linea in cola:
            m = self.RE_HEADING_ANCLA.match(linea)
            if m:
                candidato = self._normalizar_heading(m.group(2))
                if candidato == heading_norm:
                    # Solapamiento confirmado: descarta heading y lo previo
                    resto = lineas_act[idx_heading + 1:]
                    return "\n".join(resto)

        return None

    # ------------------------------------------------------------------ #
    #  Capa 2 — SequenceMatcher sobre texto normalizado (fallback)        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalizar_linea(linea: str) -> str:
        """
        Normalización para SequenceMatcher:
          - Elimina puntuación y diacríticos.
          - Pasa a minúsculas.
        Más agresiva que antes para tolerar micro-ediciones de la IA.
        """
        linea = _quitar_diacriticos(linea.lower())
        linea = re.sub(r'[^\w\s]', '', linea)
        return re.sub(r'\s+', ' ', linea).strip()

    def _solapamiento_normalizado(
        self, texto_anterior: str, texto_actual: str
    ) -> str:
        """
        Fallback cuando no hay heading de anclaje.
        Ventana ampliada a VENTANA_LINEAS (250) para cubrir chunks grandes.
        """
        lineas_ant = texto_anterior.splitlines()
        lineas_act = texto_actual.splitlines()

        cola_orig   = lineas_ant[-self.VENTANA_LINEAS:]
        cabeza_orig = lineas_act[:self.VENTANA_LINEAS]

        cola_norm   = [self._normalizar_linea(l) for l in cola_orig]
        cabeza_norm = [self._normalizar_linea(l) for l in cabeza_orig]

        # Filtrar líneas vacías para evitar falsos positivos masivos
        cola_utiles   = [(i, t) for i, t in enumerate(cola_norm)   if t]
        cabeza_utiles = [(i, t) for i, t in enumerate(cabeza_norm) if t]

        if not cola_utiles or not cabeza_utiles:
            return texto_actual

        matcher = SequenceMatcher(
            None,
            [t for _, t in cola_utiles],
            [t for _, t in cabeza_utiles],
            autojunk=False,
        )
        mejor = matcher.find_longest_match(
            0, len(cola_utiles), 0, len(cabeza_utiles)
        )

        if mejor.size >= self.UMBRAL_SECUENCIA:
            ultimo_idx_original = cabeza_utiles[mejor.b + mejor.size - 1][0]
            return "\n".join(lineas_act[ultimo_idx_original + 1:])

        return texto_actual

    # ------------------------------------------------------------------ #
    #  API pública                                                         #
    # ------------------------------------------------------------------ #

    def _resolver_solapamiento(
        self, texto_anterior: str, texto_actual: str
    ) -> str:
        """Intenta Capa 1 (anclas). Si no resuelve, cae a Capa 2."""
        resultado = self._ancla_por_heading(texto_anterior, texto_actual)
        if resultado is not None:
            return resultado
        return self._solapamiento_normalizado(texto_anterior, texto_actual)

    def normalizar_espaciado(self, texto: str) -> str:
        """Colapsa saltos excesivos sin tocar los dobles (separadores de párrafo)."""
        texto = re.sub(r'\n{3,}', '\n\n', texto)
        texto = re.sub(r' +$', '', texto, flags=re.MULTILINE)
        return texto.strip()

    def fusionar(self, lista_archivos: list, archivo_final: str) -> str:
        """
        Une los bloques procesados en un único documento coherente.

        Pasos:
          1. Lee cada bloque del disco.
          2. Elimina H1 duplicados (solo se conserva el del primer bloque).
          3. Resuelve solapamientos con la estrategia de dos capas.
          4. Escribe el documento final normalizado.

        Returns:
            Ruta absoluta del archivo final generado.
        """
        bloques_validos: list[str] = []

        for i, ruta in enumerate(lista_archivos):
            if not os.path.exists(ruta):
                continue

            with open(ruta, 'r', encoding='utf-8') as f:
                bloque = f.read().strip()

            if not bloque:
                continue

            # Solo un H1 global: los bloques 1..N pierden el suyo
            if i > 0:
                bloque = self.RE_H1.sub('', bloque).strip()

            # Resolver solapamiento con el bloque anterior
            if bloques_validos:
                bloque = self._resolver_solapamiento(bloques_validos[-1], bloque)

            if bloque.strip():
                bloques_validos.append(bloque)

        documento_final = "\n\n".join(bloques_validos)
        documento_final = self.normalizar_espaciado(documento_final)

        with open(archivo_final, 'w', encoding='utf-8') as f:
            f.write(documento_final)

        return os.path.abspath(archivo_final)
