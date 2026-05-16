"""
api.py — Agente de limpieza OCR sobre Gemini Flash.

Cambios respecto a la versión anterior:
  - Prompt completamente reescrito con énfasis crítico en preservación de
    saltos de línea dobles. La regla de whitespace ahora es la #0 (previa a
    todas las demás) e incluye un ejemplo concreto de lo prohibido.
  - Sección "EJEMPLO PROHIBIDO" para eliminar ambigüedad en temperatura=0.
  - Resto de la lógica de rotación de keys y backoff sin cambios.
"""

from google import genai
from google.genai import types
import time
import os


# ---------------------------------------------------------------------------
# PROMPT — reescrito para forzar preservación de whitespace estructural
# ---------------------------------------------------------------------------

_PROMPT_SISTEMA = """\
Sos un corrector técnico de documentos Markdown. Tu ÚNICA tarea es eliminar \
ruido de OCR sin alterar contenido, estructura ni espaciado.

══════════════════════════════════════════════════════════════
REGLA 0 — WHITESPACE ESTRUCTURAL (CRÍTICA, NUNCA VIOLA)
══════════════════════════════════════════════════════════════
Los saltos de línea dobles (\\n\\n) son separadores de párrafo.
JAMÁS los elimines ni reduzcas a un salto simple (\\n).

EJEMPLO PROHIBIDO — esto es un error gravísimo:
  ENTRADA:
    La célula eucariota posee núcleo definido.

    El ADN se organiza en cromosomas.

  SALIDA INCORRECTA (NO hagas esto):
    La célula eucariota posee núcleo definido.
    El ADN se organiza en cromosomas.

  SALIDA CORRECTA:
    La célula eucariota posee núcleo definido.

    El ADN se organiza en cromosomas.

Cada vez que veas \\n\\n en la entrada, DEBE aparecer \\n\\n en la salida.
No hay excepciones. Ni siquiera cuando los párrafos traten el mismo tema.

══════════════════════════════════════════════════════════════
REGLAS DE ESTRUCTURA (ABSOLUTAS)
══════════════════════════════════════════════════════════════
1. Conservá TODOS los encabezados Markdown (##, ###, ####) exactamente
   como están, incluyendo el salto de línea que los precede y los sigue.
2. Conservá el formato de listas (-, *, 1.) sin modificarlo.
   Cada ítem de lista mantiene su propio salto de línea.
3. Conservá negritas (**texto**) e itálicas (*texto*) exactamente donde
   están, sin moverlas ni fusionarlas con texto adyacente.
4. Conservá TODAS las referencias a imágenes Markdown (![](...)) tal cual
   aparecen. No las muevas, no las borres, no las modifiques.
   Asegurate de que queden en su propia línea, con \\n\\n antes y después.
5. La salida debe ser Markdown CommonMark válido con la misma jerarquía
   que la entrada.

══════════════════════════════════════════════════════════════
LO ÚNICO QUE SÍ PODÉS HACER (LIMPIEZA)
══════════════════════════════════════════════════════════════
6. Eliminá números de página sueltos (líneas que contengan solo 1-3 dígitos).
7. Eliminá encabezados repetitivos de página (ej: "CARRERA:", "Catedra:",
   "T.U.I.") que no sean parte del contenido académico real.
8. Corregí ligaduras tipográficas y caracteres corruptos de OCR evidentes
   (ej: "ﬁ" → "fi", "—" mal codificado) manteniendo ortografía original.

══════════════════════════════════════════════════════════════
PROHIBIDO ABSOLUTAMENTE
══════════════════════════════════════════════════════════════
- Resumir, sintetizar o condensar cualquier parte del contenido.
- Parafrasear o reescribir oraciones.
- Agregar texto, títulos, introducciones o conclusiones ausentes.
- UNIR párrafos separados por \\n\\n en uno solo. (Ver REGLA 0)
- Eliminar o reducir saltos de línea entre párrafos. (Ver REGLA 0)
- Eliminar o alterar referencias a imágenes.
- Cambiar el texto de los encabezados (##, ###) aunque parezca un error
  tipográfico: la IA podría estar viendo ruido OCR, no un error real.
"""

_PROMPT_USUARIO = "TEXTO A PROCESAR:\n{texto_crudo}"


# ---------------------------------------------------------------------------
# AGENTE
# ---------------------------------------------------------------------------

class AgenteLimpiador:
    def __init__(self):
        claves = [
            os.environ.get("GEMINI_API_KEY_1"),
            os.environ.get("GEMINI_API_KEY_2"),
            os.environ.get("GEMINI_API_KEY_3"),
        ]
        self.api_keys = [k for k in claves if k]

        if not self.api_keys:
            fallback = os.environ.get("GEMINI_API_KEY")
            if fallback:
                self.api_keys = [fallback]
            else:
                raise ValueError(
                    "No se encontró ninguna API key. "
                    "Define GEMINI_API_KEY_1 (o GEMINI_API_KEY) en el entorno."
                )

        self.key_index = 0
        self.model_id = "gemini-2.5-flash"
        self._inicializar_cliente()

    def _inicializar_cliente(self):
        self.client = genai.Client(api_key=self.api_keys[self.key_index])

    def _rotar_key(self) -> bool:
        """Cambia a la siguiente key disponible. Útil ante RPD agotado."""
        siguiente = (self.key_index + 1) % len(self.api_keys)
        if siguiente == self.key_index:
            return False
        self.key_index = siguiente
        self._inicializar_cliente()
        print(f"  [~] Rotando a key {self.key_index + 1}/{len(self.api_keys)}")
        return True

    def procesar_bloque(self, texto_crudo: str, reintentos: int = 5) -> str:
        """
        Limpia ruido OCR preservando TODA la estructura Markdown original.

        - temperature=0.0 garantiza reproducibilidad y minimiza alucinaciones.
        - max_output_tokens alineado con chunk_words=3000 (~4000 tokens de salida).
        - Backoff calibrado al reset real del tier gratuito (~60s por minuto).
        """
        prompt_usuario = _PROMPT_USUARIO.format(texto_crudo=texto_crudo)
        backoff = [60, 90, 120, 150, 180]

        for intento in range(reintentos):
            try:
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part(text=_PROMPT_SISTEMA),
                                types.Part(text=prompt_usuario),
                            ],
                        )
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=5000,
                    ),
                )

                if response.text and response.text.strip():
                    return response.text.strip()

                return "ERROR: La API devolvió una respuesta vacía."

            except Exception as e:
                error_str = str(e)

                if "429" in error_str:
                    if self._rotar_key():
                        print("  [~] Key rotada. Reintentando sin espera...")
                        continue

                    espera = backoff[intento] if intento < len(backoff) else 180
                    print(
                        f"  [!] Rate limit (429). Esperando {espera}s... "
                        f"(intento {intento + 1}/{reintentos})"
                    )
                    time.sleep(espera)
                    continue

                return f"ERROR API [{type(e).__name__}]: {error_str}"

        return "ERROR: Canal saturado. Se agotaron todos los reintentos."
