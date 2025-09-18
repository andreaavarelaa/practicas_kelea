# spiders/boe_spider.py
import datetime as dt
import scrapy

from scrapy import Request
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TimeoutError

from boe.items import BOEItem
from boe.filters import SECTIONS_WHITELIST, DEPARTMENTS_WHITELIST
from boe.utils import DISPO_PREFIX, CODE_RE, HREF_RE, extract_dispositions, norm


class BOESpider(scrapy.Spider):
    """Spider para recolectar las disposiciones del BOE entre dos fechas dadas."""
    name = "boe"
    handle_httpstatus_list = [404]

    TOPIC_MAXLEN = 160  # umbral para detectar 'topic' breve

    def __init__(self, start_date=None, end_date=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not start_date or not end_date:
            raise ValueError("Debes pasar -a start_date=YYYY-MM-DD y -a end_date=YYYY-MM-DD")

        self.start_date = dt.date.fromisoformat(start_date)
        self.end_date = dt.date.fromisoformat(end_date)

        if self.end_date < self.start_date:
            raise ValueError("end_date debe ser >= start_date")

    # Silencia el warning de Scrapy 2.13+ manteniendo la lógica de start_requests()
    async def start(self):
        for req in self.start_requests():
            yield req

    def start_requests(self):
        d = self.start_date
        one = dt.timedelta(days=1)
        while d <= self.end_date:
            url = f"https://boe.es/boe/dias/{d:%Y/%m/%d}/"
            self.logger.info("Queueing %s", url)
            yield Request(url, callback=self.parse_day, errback=self.on_error, cb_kwargs={"date": d})
            d += one

    # Incidencias de parseo (cambios HTML, etc.)
    def _parse_issue(self, reason: str, **ctx):
        self.crawler.stats.inc_value(f"parse/issues/{reason}")
        if ctx:
            self.logger.warning("Parse issue: %s | %s", reason, ctx)
        else:
            self.logger.warning("Parse issue: %s", reason)

    # Heurística por mayúsculas si dejan de usar <h4> para el departamento
    def _looks_like_department(self, text: str) -> bool:
        if not text:
            return False
        t = text.strip()
        return t.isupper() and 8 <= len(t) <= 140

    def parse_day(self, response, date):
        self.crawler.stats.inc_value(f"http/response/{response.status}")

        if response.status == 404:
            self.logger.info("No hay BOE el %s (404).", date.isoformat())
            return

        # Secciones: h2/h3 por defecto, con fallback si cambian etiquetas/clases
        sec_nodes = response.xpath("//h2|//h3")
        if not sec_nodes:
            self._parse_issue("sections_selector_fallback_used")
            sec_nodes = response.xpath(
                "//h1 | //*[@role='heading'] | "
                "//*[contains(@class,'seccion') or contains(@class,'section')]"
            )

        for sec_node in sec_nodes:
            section_title = norm(sec_node.xpath("normalize-space(string())").get())

            if SECTIONS_WHITELIST and section_title not in SECTIONS_WHITELIST:
                self._parse_issue("unknown_section", section=section_title)
                continue

            current_dept = None
            current_topic = None

            for el in sec_node.xpath("following-sibling::*"):
                tag = getattr(el.root, "tag", "").lower()

                # Límite de sección
                if tag in ("h2", "h3", "h1"):
                    break

                text = norm(el.xpath("normalize-space(string())").get())

                # Departamento: <h4> o heurística de mayúsculas
                if tag == "h4" or self._looks_like_department(text):
                    current_dept = text
                    current_topic = None
                    continue

                if not current_dept:
                    continue

                if DEPARTMENTS_WHITELIST and current_dept not in DEPARTMENTS_WHITELIST:
                    self._parse_issue("unknown_department", dept=current_dept, section=section_title)
                    continue

                # Topic breve (no disposición, no "PDF")
                if text and not DISPO_PREFIX.match(text) and not text.startswith("PDF"):
                    if len(text) <= self.TOPIC_MAXLEN:
                        current_topic = text
                        continue
                    else:
                        self._parse_issue("topic_too_long_or_changed",
                                          length=len(text), section=section_title, dept=current_dept)

                # Disposición detectada por contenido (regex), no por etiqueta
                if DISPO_PREFIX.match(text):
                    chunks = extract_dispositions(text)
                    html = el.get()
                    codes = CODE_RE.findall(html)
                    hrefs = HREF_RE.findall(html)

                    for i, chunk in enumerate(chunks):
                        preamble = chunk.strip(" :;-")
                        href = hrefs[i] if i < len(hrefs) else None

                        # Código preferente: el del href; si no, el que salga en HTML
                        code_from_href = None
                        if href:
                            m = CODE_RE.search(href)
                            if m:
                                code_from_href = m.group(0)

                        code_html = codes[i] if i < len(codes) else None
                        code = code_from_href or code_html

                    
                        if not code:
                            self._parse_issue("missing_boe_code", section=section_title, dept=current_dept)
                            continue
                        if not preamble:
                            self._parse_issue("missing_preamble", code=code,
                                              section=section_title, dept=current_dept)
                            continue

                        pdf_url = response.urljoin(href) if href else (
                            f"https://boe.es/boe/dias/{date:%Y/%m/%d}/pdfs/{code}.pdf"
                        )
                        url = f"https://www.boe.es/buscar/doc.php?id={code}"

                        self.crawler.stats.inc_value("parse/dispositions_emitted")

                        yield BOEItem(
                            boe_code=code,
                            date=f"{date:%Y-%m-%d}",
                            section=section_title,
                            department=current_dept,
                            topic=current_topic or "",
                            preamble=preamble,
                            url=url,
                            pdf_url=pdf_url,
                            summary="",
                            impact="",
                            source="BOE",
                        )

    # Errback de red: clasifica y cuenta el motivo
    def on_error(self, failure):
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
