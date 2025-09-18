import os
import fitz
import requests
import json
import google.generativeai as genai 

api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("No se encontró la variable de entorno GOOGLE_API_KEY")
print("API key cargada.")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

def analyze_text(url):
    text = url_to_text(url)
    if text.startswith("ERROR:"):
        return {
            "resumen": "",
            "impacto": f"Error al leer PDF: {text}",
            "guardar_en_bd": False
        }

    prompt = f"""
    Analiza el siguiente texto extraído de un documento PDF del Boletín Oficial del Estado (BOE).

    Necesito que generes una respuesta en **formato JSON** con los siguientes campos:

    1. "resumen": resumen breve y claro del contenido del texto.
    2. "impacto": describe si el contenido tienen un impacto (directo o indirecto) en el sector retail
        o comercio minorista en España. Si no hay impacto, indícalo explícitamente.
    3. "guardar_en_bd": true si el contenido es relevante para el sector retail y debe guardarse en la
        base de datos; false si no lo es.
    
    No incluyas explicaciones adicionales fuera del JSON. Limítate a responder con el objeto JSON.

    ---
    TEXTO DEL PDF:
    {text}
    ---
    """

    try:
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        return {
            "resumen": "",
            "impacto": f"Error en análisis con Gemini: {e}",
            "guardar_en_bd": False
        }

def url_to_text(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        pdf = fitz.open(stream=response.content, filetype="pdf")

        text = ""
        for page in pdf:
            text += page.get_text()
        return text

    except Exception as e:
        return f"Error: {e}"

# def extract_and_summarize(url: str) -> str:
#     text = url_to_text(url)
#     if text.startswith("Error"):
#         return text
#     return analyze_text(text)