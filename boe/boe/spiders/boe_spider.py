import datetime as dt
import scrapy

from boe.filters import SECTIONS_WHITELIST, DEPARTMENTS_WHITELIST
from boe.utils import DISPO_PREFIX, CODE_RE, HREF_RE, extract_dispositions

class BOESpider(scrapy.Spider):
    name = "boe"
    handle_httpstatus_list = [404]

    def __init__(self, start_date=None, end_date=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not start_date or not end_date:
            raise ValueError("Debes pasar -a start_date=YYYY-MM-DD y -a end_date=YYYY-MM-DD")

        self.start_date = dt.date.fromisoformat(start_date)
        self.end_date = dt.date.fromisoformat(end_date)

        if self.end_date < self.start_date:
            raise ValueError("end_date debe ser >= start_date")

    # Igual que tu original: start_requests sin async
    def start_requests(self):
        d = self.start_date
        one = dt.timedelta(days=1)
        while d <= self.end_date:
            url = f"https://boe.es/boe/dias/{d:%Y/%m/%d}/"
            self.logger.info("Queueing %s", url)
            yield scrapy.Request(url, callback=self.parse_day, cb_kwargs={"date": d})
            d += one

    def parse_day(self, response, date):
        if response.status == 404:
            self.logger.info("No hay BOE el %s (404).", date.isoformat())
            return

        # h2/h3 = títulos de sección
        for sec_node in response.xpath("//h2|//h3"):
            section_title = sec_node.xpath("normalize-space(string())").get() or ""
            if SECTIONS_WHITELIST and section_title not in SECTIONS_WHITELIST:
                continue

            current_dept = None
            current_topic = None

            # Recorremos los hermanos hasta el próximo h2/h3
            for el in sec_node.xpath("following-sibling::*"):
                tag = getattr(el.root, "tag", "").lower()
                if tag in ("h2", "h3"):
                    break

                text = el.xpath("normalize-space(string())").get() or ""

                # Nuevo departamento
                if tag == "h4":
                    current_dept = text.strip()
                    current_topic = None
                    continue

                # Si aún no hay departamento, ignoramos contenido suelto
                if not current_dept:
                    continue

                # Filtro por departamento
                if DEPARTMENTS_WHITELIST and current_dept not in DEPARTMENTS_WHITELIST:
                    continue

                # ¿Es una línea de topic/epígrafe (no empieza por disposición)?
                if text and not DISPO_PREFIX.match(text) and not text.startswith("PDF"):
                    # Heurística: topics suelen ser frases cortas (pero dejamos margen).
                    if len(text) <= 160:
                        current_topic = text.strip()
                        continue
                    # Si es muy largo, probablemente es cuerpo/introducción; seguimos sin cambiar topic.

                # ¿Este nodo contiene una o varias disposiciones?
                if DISPO_PREFIX.match(text):
                    # En este nodo extraemos títulos (puede haber varios)
                    chunks = extract_dispositions(text)

                    # Códigos/hrefs del propio nodo (mismo orden visual)
                    html = el.get()
                    codes = CODE_RE.findall(html)
                    hrefs = HREF_RE.findall(html)

                    # Si hay desalineación, lo anotamos en debug, pero seguimos.
                    if len(codes) != len(chunks):
                        self.logger.debug(
                            "Desalineado en %s / %s: %d títulos y %d códigos",
                            section_title, current_dept, len(chunks), len(codes)
                        )

                    for i, chunk in enumerate(chunks):
                        title = chunk.strip(" :;-")
                        code = codes[i] if i < len(codes) else None
                        href = hrefs[i] if i < len(hrefs) else None
                        pdf_url = response.urljoin(href) if href else (
                            f"https://boe.es/boe/dias/{date:%Y/%m/%d}/pdfs/{code}.pdf" if code else None
                        )

                        yield {
                            "date": f"{date:%Y-%m-%d}",
                            "section": section_title,
                            "department": current_dept,
                            "topic": current_topic or "",
                            "title": title,
                            "boe_code": code,
                            "pdf_url": pdf_url,
                        }
                # Si no es ni topic ni disposición, lo ignoramos (suele ser texto de relleno)