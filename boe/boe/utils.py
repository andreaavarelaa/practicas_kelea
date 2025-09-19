import re

# ---------------------------------------------------------------------------
# Expresiones regulares
# ---------------------------------------------------------------------------

# Detecta el comienzo de una disposición normativa oficial del BOE.
# Ejemplos válidos:
#   - "Resolución de 1 de septiembre..."
#   - "Real Decreto-ley 12/2023..."
#   - "Real Decreto Legislativo 1/2010..."
#   - "Orden PCM/..."
#   - "Acuerdo de ..."
#   - "Anuncio de ..."
#   - "Circular ..."
#   - "Instrucción ..."
DISPO_PREFIX = re.compile(
    r"^(Resolución|Real Decreto(?:-ley| Legislativo)?|Orden|Acuerdo|Anuncio|Circular|Instrucción)\b"
)

# Detecta el código oficial de documento del BOE.
# Ejemplo válido: "BOE-A-2024-12345"
CODE_RE = re.compile(
    r"\bBOE-[A-Z]-\d{4}-\d{4,6}\b"
)

# Detecta el enlace al PDF de una disposición en el HTML (atributo href).
# Captura el valor del href completo que contenga la ruta a 'pdfs/BOE-...pdf'.
# Ejemplo de coincidencia: href="/boe/dias/2024/09/18/pdfs/BOE-A-2024-12345.pdf"
HREF_RE = re.compile(
    r'href="([^"]*pdfs/BOE-[A-Z]-\d{4}-\d{4,6}\.pdf)"'
)

# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def extract_dispositions(text: str) -> list[str]:
    """
    Extrae bloques de texto que parecen ser disposiciones normativas del BOE.

    Busca cualquier texto que comience con una palabra clave normativa
    (Resolución, Real Decreto, Orden, etc.) y captura hasta justo antes de
    encontrar la palabra "PDF" o el final de la cadena.

    Esto permite separar varias disposiciones que vengan agrupadas en el mismo
    bloque HTML.

    Args:
        text: Texto plano a analizar.

    Returns:
        list[str]: Lista de bloques de texto que parecen disposiciones.
    """
    return re.findall(
        r"(?:Resolución|Real Decreto(?:-ley| Legislativo)?|Orden|Acuerdo|Anuncio|Circular|Instrucción)[\s\S]*?(?=PDF\s*\(|$)",
        text
    )


def norm(s: str) -> str:
    """
    Normaliza cadenas para el preprocesamiento de texto del BOE:

    - Sustituye caracteres no visibles como \xa0 (espacio no separable) por espacios normales.
    - Reduce espacios múltiples a uno solo.
    - Elimina espacios en extremos.

    Args:
        s: Texto original (puede ser None o cadena vacía).

    Returns:
        str: Cadena normalizada. Devuelve '' si la entrada es falsy.
    """
    if not s:
        return ""
    return " ".join(s.replace("\xa0", " ").split()).strip()