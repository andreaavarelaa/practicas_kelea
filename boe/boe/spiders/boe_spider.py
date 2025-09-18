# spiders/boe_spider.py
import datetime as dt
import scrapy

from typing import Iterable, Optional
from scrapy import Request
from scrapy.http import Response
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TimeoutError

from items import BOEItem
from filters import SECTIONS_WHITELIST, DEPARTMENTS_WHITELIST
from utils import DISPO_PREFIX, CODE_RE, HREF_RE, extract_dispositions, norm


class BOESpider(scrapy.Spider):
    """
    Spider para recolectar disposiciones del BOE entre dos fechas (ambas inclusive).

    Flujo:
      1) __init__ valida y convierte start_date / end_date (YYYY-MM-DD) a `date`.
      2) start() / start_requests() encola una URL de índice por cada día del rango.
      3) parse_day() parsea la página de un día:
         - Detecta secciones (h2/h3; con fallback).
         - Dentro de cada sección, identifica departamentos (h4 o heurística de MAYÚSCULAS).
         - Asocia un 'topic' breve si aparece justo antes de las disposiciones.
         - Extrae disposiciones (regex sobre el texto) y obtiene:
             • boe_code (preferentemente desde el href; si no, desde el HTML)
             • preámbulo
             • urls (doc.php y PDF)
         - Emite BOEItem para cada disposición válida.
      4) on_error() clasifica y cuenta los fallos de red/HTTP.

    Métricas principales (crawler.stats):
      - http/response/<status>
      - parse/issues/<motivo> (cambios HTML, selectores de fallback, etc.)
      - parse/dispositions_emitted
      - http/error/<tipo>
    """
    name = "boe"
    handle_httpstatus_list = [404]

    # Longitud máxima para considerar un texto como 'topic' (no disposición ni "PDF")
    TOPIC_MAXLEN = 160

    def __init__(self, start_date: Optional[str] = None, end_date: Optional[str] = None, *args, **kwargs):
        """
        Args:
            start_date: fecha ISO 'YYYY-MM-DD' (inclusive).
            end_date:   fecha ISO 'YYYY-MM-DD' (inclusive).

        Raises:
            ValueError: si faltan fechas o end_date < start_date.
        """
        super().__init__(*args, **kwargs)

        if not start_date or not end_date:
            raise ValueError("Debes pasar -a start_date=YYYY-MM-DD y -a end_date=YYYY-MM-DD")

        self.start_date: dt.date = dt.date.fromisoformat(start_date)
        self.end_date: dt.date = dt.date.fromisoformat(end_date)

        if self.end_date < self.start_date:
            raise ValueError("end_date debe ser >= start_date")

    # Scrapy 2.13+: evita warning manteniendo la semántica de start_requests()
    async def start(self):
        """
        Arranque async compatible con Scrapy 2.13+.
        Delegamos en start_requests() para no duplicar la lógica de encolado.
        """
        for req in self.start_requests():
            yield req

    def start_requests(self) -> Iterable[Request]:
        """
        Genera una Request por cada día del rango [start_date, end_date].

        Yields:
            Request: hacia https://boe.es/boe/dias/YYYY/MM/DD/
        """
        d = self.start_date
        one = dt.timedelta(days=1)
        while d <= self.end_date:
            url = f"https://boe.es/boe/dias/{d:%Y/%m/%d}/"
            self.logger.info("Queueing %s", url)
            yield Request(
                url,
                callback=self.parse_day,
                errback=self.on_error,
                cb_kwargs={"date": d},  # pasamos la fecha del día al parser
            )
            d += one

    # --- Utilidades de trazabilidad de parsing ---

    def _parse_issue(self, reason: str, **ctx) -> None:
        """
        Registra incidencias de parseo y suma métricas para su monitorización.

        Args:
            reason: etiqueta del problema detectado (selector roto, heurística activada, etc.).
            **ctx:  contexto opcional (section, dept, length, code...), se imprime en el log.
        """
        self.crawler.stats.inc_value(f"parse/issues/{reason}")
        if ctx:
            self.logger.warning("Parse issue: %s | %s", reason, ctx)
        else:
            self.logger.warning("Parse issue: %s", reason)

    def _looks_like_department(self, text: str) -> bool:
        """
        Heurística para detectar un departamento si se pierde el <h4>:
        - Texto en MAYÚSCULAS
        - Longitud razonable (8..140)

        Args:
            text: cadena a evaluar.

        Returns:
            bool: True si parece un departamento.
        """
        if not text:
            return False
        t = text.strip()
        return t.isupper() and 8 <= len(t) <= 140

    # --- Parser principal del día ---

    def parse_day(self, response: Response, date: dt.date):
        """
        Parsea el índice del BOE de un día concreto.

        Estrategia:
          - Cuenta el status HTTP.
          - Si 404, no hay publicación ese día -> salir.
          - Detecta secciones (h2/h3, con fallback robusto).
          - Para cada sección:
              * Recorre nodos siguientes (following-sibling) hasta el próximo título (h1/h2/h3).
              * Detecta departamentos por <h4> o heurística.
              * Filtra por listas blancas (sección/departamento) si están definidas.
              * Identifica 'topic' (texto breve no disposición ni "PDF").
              * Detecta disposiciones (regex por contenido), extrae boe_code, preámbulo y hrefs.
              * Construye urls y emite BOEItem.

        Métricas:
          - http/response/<status>
          - parse/issues/<motivo>
          - parse/dispositions_emitted

        Args:
            response: HTML del índice diario del BOE.
            date:     fecha del día que se está parseando (cb_kwargs).
        """
        self.crawler.stats.inc_value(f"http/response/{response.status}")

        if response.status == 404:
            self.logger.info("No hay BOE el %s (404).", date.isoformat())
            return

        # Secciones: selector primario y fallback si el HTML cambia
        sec_nodes = response.xpath("//h2|//h3")
        if not sec_nodes:
            self._parse_issue("sections_selector_fallback_used")
            sec_nodes = response.xpath(
                "//h1 | //*[@role='heading'] | "
                "//*[contains(@class,'seccion') or contains(@class,'section')]"
            )

        for sec_node in sec_nodes:
            section_title = norm(sec_node.xpath("normalize-space(string())").get())

            # Lista blanca opcional de secciones
            if SECTIONS_WHITELIST and section_title not in SECTIONS_WHITELIST:
                self._parse_issue("unknown_section", section=section_title)
                continue

            current_dept: Optional[str] = None
            current_topic: Optional[str] = None

            # Recorremos hermanos siguientes hasta el próximo encabezado de sección
            for el in sec_node.xpath("following-sibling::*"):
                tag = getattr(el.root, "tag", "").lower()

                # Límite de sección (siguiente h1/h2/h3 corta el recorrido)
                if tag in ("h2", "h3", "h1"):
                    break

                text = norm(el.xpath("normalize-space(string())").get())

                # Detección de departamento: <h4> o heurística por MAYÚSCULAS
                if tag == "h4" or self._looks_like_department(text):
                    current_dept = text
                    current_topic = None  # reinicia topic al cambiar de dept
                    continue

                # Si aún no tenemos departamento, seguimos
                if not current_dept:
                    continue

                # Lista blanca opcional de departamentos
                if DEPARTMENTS_WHITELIST and current_dept not in DEPARTMENTS_WHITELIST:
                    self._parse_issue("unknown_department", dept=current_dept, section=section_title)
                    continue

                # Topic breve (texto informativo previo a disposiciones, no "PDF", no coincide con patrón de disposición)
                if text and not DISPO_PREFIX.match(text) and not text.startswith("PDF"):
                    if len(text) <= self.TOPIC_MAXLEN:
                        current_topic = text
                        continue
                    else:
                        self._parse_issue(
                            "topic_too_long_or_changed",
                            length=len(text), section=section_title, dept=current_dept
                        )

                # Disposición detectada por contenido mediante regex (no dependemos de etiqueta concreta)
                if DISPO_PREFIX.match(text):
                    # 1) Troceamos las disposiciones del bloque textual
                    chunks = extract_dispositions(text)
                    # 2) Inspeccionamos el HTML para extraer códigos y hrefs paralelos
                    html = el.get()
                    codes = CODE_RE.findall(html)  # códigos en el HTML
                    hrefs = HREF_RE.findall(html)  # hrefs de los enlaces

                    for i, chunk in enumerate(chunks):
                        preamble = chunk.strip(" :;-")
                        href = hrefs[i] if i < len(hrefs) else None

                        # Código preferente: el que venga en el href del enlace
                        code_from_href = None
                        if href:
                            m = CODE_RE.search(href)
                            if m:
                                code_from_href = m.group(0)

                        # Si no, tomamos el que aparezca embebido en el HTML
                        code_html = codes[i] if i < len(codes) else None
                        code = code_from_href or code_html

                        # Validaciones mínimas
                        if not code:
                            self._parse_issue("missing_boe_code", section=section_title, dept=current_dept)
                            continue
                        if not preamble:
                            self._parse_issue("missing_preamble", code=code, section=section_title, dept=current_dept)
                            continue

                        # Construcción de URLs
                        pdf_url = response.urljoin(href) if href else (
                            f"https://boe.es/boe/dias/{date:%Y/%m/%d}/pdfs/{code}.pdf"
                        )
                        url = f"https://www.boe.es/buscar/doc.php?id={code}"

                        # Métrica de disposición emitida
                        self.crawler.stats.inc_value("parse/dispositions_emitted")

                        # Emisión del item
                        yield BOEItem(
                            boe_code=code,
                            date=f"{date:%Y-%m-%d}",
                            section=section_title,
                            department=current_dept,
                            topic=current_topic or "",
                            preamble=preamble,
                            url=url,
                            pdf_url=pdf_url,
                            source="BOE",
                        )

    # --- Errback de red -------------------------------------------------------

    def on_error(self, failure):
        """
        Errback de red/HTTP.
        Clasifica y cuenta el error para observabilidad.

        Métricas:
          - http/error/<status> (para HttpError)
          - http/error/DNSLookupError
          - http/error/TimeoutError
          - http/error/Unknown
        """
        stats = self.crawler.stats
        if failure.check(HttpError):
            r = failure.value.response
            self.logger.error("HTTP error %s en %s", r.status, r.url)
            stats.inc_value(f"http/error/{r.status}")
        elif failure.check(DNSLookupError):
            self.logger.error("DNS error: %s", failure.request.url)
            stats.inc_value("http/error/DNSLookupError")
        elif failure.check(TimeoutError):
            self.logger.error("Timeout: %s", failure.request.url)
            stats.inc_value("http/error/TimeoutError")
        else:
            self.logger.exception("Error no controlado: %r", failure)
            stats.inc_value("http/error/Unknown")
