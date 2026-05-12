from google import genai
from google.genai import types
import time
import os

class AgenteLimpiador:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Falta la GEMINI_API_KEY en el entorno.")

        # SDK google-genai 2.x usa v1beta por defecto.
        # Eso es CORRECTO: los modelos Gemini viven en v1beta, no en v1.
        # No se sobreescribe el endpoint.
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-2.0-flash-lite"

    def procesar_bloque(self, texto_crudo: str, reintentos: int = 3) -> str:
        """
        Envía un bloque de texto crudo a Gemini para limpieza de ruido OCR.
        Implementa reintentos con backoff exponencial para el Error 429 (rate limit).
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
        for intento in range(reintentos):
            try:
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        # Temperatura 0 para máxima fidelidad y reproducibilidad.
                        temperature=0.0,
                        max_output_tokens=8192,
                    )
                )
                # Validación de respuesta no vacía antes de retornar.
                if response.text and response.text.strip():
                    return response.text.strip()

                return "ERROR: La API devolvió una respuesta vacía."

            except Exception as e:
                error_str = str(e)

                # Manejo específico del Error 429: Rate Limit del Tier Gratuito.
                # Backoff exponencial: espera 10s, 20s, 30s entre reintentos.
                if "429" in error_str:
                    espera = (intento + 1) * 10
                    print(f"  [!] Rate limit (429). Esperando {espera}s antes de reintentar...")
                    time.sleep(espera)
                    continue

                # Cualquier otro error (400, 403, 500) es fatal para este bloque.
                return f"ERROR API [{type(e).__name__}]: {error_str}"

        return "ERROR: Canal saturado. Se agotaron todos los reintentos."