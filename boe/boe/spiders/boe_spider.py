import datetime as dt
import scrapy

from boe.items import BOEItem
from boe.filters import SECTIONS_WHITELIST, DEPARTMENTS_WHITELIST
from boe.utils import DISPO_PREFIX, CODE_RE, HREF_RE, extract_dispositions, norm

class BOESpider(scrapy.Spider):
    """Spider para recolectar las disposiciones del BOE entre dos fechas dadas."""
    name = "boe"
    handle_httpstatus_list = [404]

    def __init__(self, start_date=None, end_date=None, *args, **kwargs):
        """Constructor del spider, requiere start_date y end_date como fechas ISO."""
        super().__init__(*args, **kwargs)

        if not start_date or not end_date:
            raise ValueError("Debes pasar -a start_date=YYYY-MM-DD y -a end_date=YYYY-MM-DD")

        self.start_date = dt.date.fromisoformat(start_date)
        self.end_date = dt.date.fromisoformat(end_date)

        if self.end_date < self.start_date:
            raise ValueError("end_date debe ser >= start_date")

    def start_requests(self):
        """Genera una lista de fechas entre start_date y end_date, y lanza una petición por cada día al índice del BOE."""
        d = self.start_date
        one = dt.timedelta(days=1)

        while d <= self.end_date:
            url = f"https://boe.es/boe/dias/{d:%Y/%m/%d}/"
            self.logger.info("Queueing %s", url)
            yield scrapy.Request(url, callback=self.parse_day, cb_kwargs={"date": d})
            d += one

    def parse_day(self, response, date):
        """Procesa la página del BOE para un día específico, filtrando por secciones y departamentos. Genera un BOEItem por disposición encontrada."""
        if response.status == 404:
            self.logger.info("No hay BOE el %s (404).", date.isoformat())
            return

        # Selecciona encabezados de sección (h2/h3).
        for sec_node in response.xpath("//h2|//h3"):
            section_title = norm(sec_node.xpath("normalize-space(string())").get())

            # Ignora secciones no incluidas en el whitelist.
            if SECTIONS_WHITELIST and section_title not in SECTIONS_WHITELIST:
                continue

            current_dept = None
            current_topic = None

            # Recorre los nodos después del encabezado de sección.
            for el in sec_node.xpath("following-sibling::*"):
                tag = getattr(el.root, "tag", "").lower()
                
                if tag in ("h2", "h3"): 
                    # Límite de la sección actual.
                    break

                text = norm(el.xpath("normalize-space(string())").get())

                if tag == "h4":
                    # Encabezado de departamento.
                    current_dept = norm(text)
                    current_topic = None
                    continue

                if not current_dept:
                    # Aún no se ha definido el departamento.
                    continue

                # Ignora departamentos no incluidos en el whitelist.
                if DEPARTMENTS_WHITELIST and current_dept not in DEPARTMENTS_WHITELIST:
                    continue

                # Detecta el tema dentro del departamento.
                if text and not DISPO_PREFIX.match(text) and not text.startswith("PDF"):
                    if len(text) <= 160:
                        current_topic = text
                        continue

                # Detecta la disposición oficial por regex.
                if DISPO_PREFIX.match(text):
                    chunks = extract_dispositions(text)
                    html = el.get()
                    codes = CODE_RE.findall(html)
                    hrefs = HREF_RE.findall(html)

                    if len(codes) != len(chunks):
                        self.logger.debug(
                            "Desalineado en %s / %s: %d títulos y %d códigos",
                            section_title, current_dept, len(chunks), len(codes)
                        )

                    # Empareja cada disposición con su código y PDF.
                    for i, chunk in enumerate(chunks):
                        preamble = chunk.strip(" :;-")
                        code = codes[i] if i < len(codes) else None
                        href = hrefs[i] if i < len(hrefs) else None

                        if not code or not preamble:
                            self.logger.warning("Disposición incompleta en %s: saltando.", date)
                            continue

                        # Construye la URL del PDF y HTML.
                        pdf_url = response.urljoin(href) if href else (
                            f"https://boe.es/boe/dias/{date:%Y/%m/%d}/pdfs/{code}.pdf"
                        )
                        url = f"https://www.boe.es/buscar/doc.php?id={code}"

                        # Genera el item para enviar al pipeline.
                        yield BOEItem(
                            boe_code=code,
                            date=f"{date:%Y-%m-%d}",
                            section=section_title,
                            department=current_dept,
                            topic=current_topic or "",
                            preamble=preamble,
                            url=url,
                            pdf_url=pdf_url,
                            source="BOE"
                        )