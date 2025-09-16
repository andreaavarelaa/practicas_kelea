import re

DISPO_PREFIX = re.compile(r"^(Resolución|Real Decreto(?:-ley| Legislativo)?|Orden|Acuerdo|Anuncio|Circular|Instrucción)\b")
CODE_RE = re.compile(r"\bBOE-[A-Z]-\d{4}-\d{4,6}\b")
HREF_RE = re.compile(r'href="([^"]*pdfs/BOE-[A-Z]-\d{4}-\d{4,6}\.pdf)"')

def extract_dispositions(text):
    return re.findall(
        r"(?:Resolución|Real Decreto(?:-ley| Legislativo)?|Orden|Acuerdo|Anuncio|Circular|Instrucción)[\s\S]*?(?=PDF\s*\(|$)",
        text
    )

def norm(s: str) -> str:
    """Normaliza strings eliminando espacios múltiples y caracteres no visibles como \xa0."""
    if not s:
        return ""
    return " ".join(s.replace("\xa0", " ").split()).strip()
