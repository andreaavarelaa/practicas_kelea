import os, re, json, requests, fitz
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("Falta GOOGLE_API_KEY en .env")
genai.configure(api_key=API_KEY)
MODEL = genai.GenerativeModel("gemini-1.5-flash")

def _safe_parse_json(s: str) -> dict:
    s = (s or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.IGNORECASE)
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        raise ValueError("Respuesta sin objeto JSON.")
    return json.loads(m.group(0))

def _resp_text(resp) -> str:
    t = getattr(resp, "text", None)
    if t:
        return t
    parts = []
    for c in getattr(resp, "candidates", []) or []:
        content = getattr(c, "content", None)
        for p in getattr(content, "parts", []) or []:
            txt = getattr(p, "text", None)
            if txt:
                parts.append(txt)
    return "\n".join(parts).strip()

def extract_text_from_pdf(url: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": "boe-scraper/1.0"}, timeout=30)
        r.raise_for_status()
        with fitz.open(stream=r.content, filetype="pdf") as pdf:
            text = "".join(page.get_text() for page in pdf).strip()
        return text if text else "ERROR: PDF sin texto extraíble (posible escaneado/imagen)."
    except Exception as e:
        return f"ERROR: {e}"

def analyze_text_with_gemini(text: str) -> dict:
    if not text or text.startswith("ERROR:"):
        return {"resumen": "", "guardar_en_bd": False}

    prompt = f"""
    Analiza el siguiente texto del BOE y responde SOLO con JSON, hazlo siempre en español:

        - "resumen": detallado; debe incluir la información clave, con los puntos principales identificados; 
        responde cualquier pregunta relevante que pueda inferirse del contenido.

        - "guardar_en_bd": true si tiene un impacto relevante en el sector retail; false si no.

        Ejemplo de estructura del JSON:
        'informacion_clave': ['El plan estratégico tiene una duración de '
                                   'tres años (2025-2027).',
                                   'Se priorizan las actuaciones relacionadas '
                                   'con la estabilidad en el empleo, el tiempo '
                                   'de trabajo, los salarios, la seguridad y '
                                   'salud laboral, la igualdad y la inclusión.',
                                   'Se busca mejorar la eficiencia y la '
                                   'calidad del servicio público, adaptándose '
                                   'a los nuevos desafíos tecnológicos y '
                                   'sociales.',
                                   'Se contempla el incremento de la '
                                   'plantilla, la formación del personal, la '
                                   'digitalización de procesos, y la mejora de '
                                   'la comunicación con la ciudadanía.'],
             'preguntas_relevantes': ['¿Qué impacto tendrá el plan en el '
                                      'mercado laboral español?',
                                      ' ¿Cómo se financiarán las medidas '
                                      'propuestas?',
                                      '¿Cómo se evaluará el éxito del plan?'],
             'puntos_principales': ['Aprobación del Plan Estratégico de la '
                                    'Inspección de Trabajo y Seguridad Social '
                                    '2025-2027',
                                    'El plan se centra en la defensa de los '
                                    'derechos de los trabajadores y la '
                                    'prestación de un servicio público de '
                                    'calidad.',
                                    'Se establecen 17 objetivos, agrupados en '
                                    'dos ejes principales: actividad '
                                    'inspectora y organización.',
                                    'Se incluyen medidas para la modernización '
                                    'tecnológica, la formación del personal y '
                                    'la transparencia.',
                                    'El plan está alineado con los Objetivos '
                                    'de Desarrollo Sostenible (ODS) de la '
                                    'Agenda 2030.']

    TEXTO:
    {text}
    """
    try:
        resp = MODEL.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        raw = _resp_text(resp)
        return json.loads(raw) if raw.strip().startswith("{") else _safe_parse_json(raw)
    except Exception as e:
        return {"resumen": "", "guardar_en_bd": False}

# Wrapper compatible con tu pipeline actual:
def analyze_text(pdf_url: str) -> dict:
    return analyze_text_with_gemini(extract_text_from_pdf(pdf_url))