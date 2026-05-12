from google import genai
from google.genai import types
import time
import os

class AgenteLimpiador:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Falta la GEMINI_API_KEY en el entorno.")

        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-2.5-flash"

    def procesar_bloque(self, texto_crudo: str, reintentos: int = 5) -> str:
        """
        Envía un bloque de texto crudo a Gemini para limpieza de ruido OCR.
        Backoff progresivo calibrado al reset real del tier gratuito (~60s).
        No resume ni parafrasea: fidelidad absoluta al contenido original.
        """
        prompt = f"""Eres un auditor técnico. Tu única misión es limpiar el siguiente texto:
- Elimina ruido de OCR: caracteres corruptos, números de página sueltos, encabezados/pies de página repetitivos.
- Corrige la sintaxis Markdown rota (tablas mal formadas, saltos de línea incorrectos).
- PROHIBIDO: resumir, parafrasear, agregar o inventar contenido. Fidelidad absoluta al texto original.
- Devuelve ÚNICAMENTE el texto limpio, sin explicaciones ni comentarios tuyos.

TEXTO A PROCESAR:
{texto_crudo}
"""
        # Tiempos calibrados al reset real de Gemini (~60s por minuto).
        # Intento 0->60s, 1->90s, 2->120s, 3->150s, 4->180s
        backoff = [60, 90, 120, 150, 180]

        for intento in range(reintentos):
            try:
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=8192,
                    )
                )
                if response.text and response.text.strip():
                    return response.text.strip()

                return "ERROR: La API devolvió una respuesta vacía."

            except Exception as e:
                error_str = str(e)

                if "429" in error_str:
                    espera = backoff[intento] if intento < len(backoff) else 180
                    print(f"  [!] Rate limit (429). Esperando {espera}s... (intento {intento + 1}/{reintentos})")
                    time.sleep(espera)
                    continue

                return f"ERROR API [{type(e).__name__}]: {error_str}"

        return "ERROR: Canal saturado. Se agotaron todos los reintentos."