import os, re, json, requests, fitz
import google.generativeai as genai
from dotenv import load_dotenv

# --- Config ---
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("Falta GOOGLE_API_KEY en .env")
genai.configure(api_key=API_KEY)
MODEL = genai.GenerativeModel("gemini-2.5")


# --- Helpers ---
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

def _clean_fences(s: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", (s or "").strip(), flags=re.IGNORECASE)


# --- Extracción de texto ---
def extract_text(url: str) -> str:
    """Soporta PDF y HTML (fallback simple quitando tags)."""
    r = requests.get(url, headers={"User-Agent": "boe-scraper/1.0"}, timeout=30)
    r.raise_for_status()
    ctype = r.headers.get("Content-Type", "").lower()
    if url.lower().endswith(".pdf") or "application/pdf" in ctype:
        with fitz.open(stream=r.content, filetype="pdf") as pdf:
            return "\n".join(page.get_text("text") for page in pdf).strip()
    else:
        text = re.sub(r"<[^>]+>", " ", r.text)
        return re.sub(r"\s+", " ", text).strip()


# --- Análisis con Gemini ---
def analyze_text_with_gemini(text: str) -> dict:
    """
    Devuelve siempre {"impacto_retail": bool, "resumen": str|None}
    """
    if not text or text.startswith("ERROR:"):
        return {"impacto_retail": False, "resumen": None}

    prompt = f"""
Eres analista de regulación española. Analiza este texto y determina si tiene
impacto en una COMPAÑÍA INTERNACIONAL DEL SECTOR TEXTIL RETAIL que opera en España y en otros países.

Instrucciones:
- Si NO hay impacto relevante → responde exactamente con la palabra NONE.
- Si SÍ hay impacto → responde en JSON con este formato:
{{
  "impacto_retail": true,
  "resumen": "explica de forma clara el texto, a quién afecta y fechas clave"
}}

Texto a analizar:
{text}
"""
    try:
        resp = MODEL.generate_content(prompt)
        raw = _clean_fences(_resp_text(resp))

        if raw.strip().upper() == "NONE":
            return {"impacto_retail": False, "resumen": None}

        data = json.loads(raw)
        return {
            "impacto_retail": bool(data.get("impacto_retail", False)),
            "resumen": data.get("resumen") if data.get("impacto_retail") else None,
        }
    except Exception as e:
        print(f"Error en Gemini: {e}")
        return {"impacto_retail": False, "resumen": None}


# --- Wrapper para pipeline ---
def analyze_text(url: str) -> dict:
    return analyze_text_with_gemini(extract_text(url))
