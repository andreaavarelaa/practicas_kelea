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
    Analiza el siguiente texto del BOE y responde SOLO con JSON:

        - "resumen": detallado; debe incluir la información clave, con los puntos principales identificados; 
        responde cualquier pregunta relevante que pueda inferirse del contenido.
        
        - "guardar_en_bd": true si tiene un impacto relevante en el sector retail; false si no.

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