import re

# Expresión regular para detectar el inicio de una disposición normativa del BOE.
DISPO_PREFIX = re.compile(r"^(Resolución|Real Decreto(?:-ley| Legislativo)?|Orden|Acuerdo|Anuncio|Circular|Instrucción)\b")

# Expresión regular para detectar el código oficial del BOE.
CODE_RE = re.compile(r"\bBOE-[A-Z]-\d{4}-\d{4,6}\b")

# Expresión regular para extraer el enlace al PDF desde el atributo 'href' en el HTML.
HREF_RE = re.compile(r'href="([^"]*pdfs/BOE-[A-Z]-\d{4}-\d{4,6}\.pdf)"')

def extract_dispositions(text):
    """Extrae bloques de texto que parecen ser disposiciones normativas del BOE."""
    return re.findall(
        r"(?:Resolución|Real Decreto(?:-ley| Legislativo)?|Orden|Acuerdo|Anuncio|Circular|Instrucción)[\s\S]*?(?=PDF\s*\(|$)",
        text
    )

def norm(s: str) -> str:
    """Normaliza strings eliminando espacios múltiples y caracteres no visibles como \xa0."""
    if not s:
        return ""
    return " ".join(s.replace("\xa0", " ").split()).strip()