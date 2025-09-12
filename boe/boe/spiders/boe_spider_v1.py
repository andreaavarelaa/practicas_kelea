import scrapy
from datetime import datetime, timedelta

class BOESpider(scrapy.Spider):
    name = "boe"
    
    def __init__(self, start_date=None, end_date=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not start_date or not end_date:
            raise ValueError("Debes pasar -a start_date=YYYY-MM-DD y -a end_date=YYYY-MM-DD")
        self.start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        self.end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        if self.end_dt < self.start_dt:
            raise ValueError("end_date debe ser >= start_date")
        
    def start_requests(self):
        day = self.start_dt
        one = timedelta(days=1)
        while day <= self.end_dt:
            y, m, d = day.strftime("%Y"), day.strftime("%m"), day.strftime("%d")
            url = f"https://boe.es/boe/dias/{y}/{m}/{d}/"  # barra final
            self.logger.info(f"Queueing {url}")             # <-- línea de debug útil
            yield scrapy.Request(
                url,
                callback=self.parse,
                cb_kwargs={"date_str": day.isoformat()}
            )
            day += one  





    def parse(self, response, date_str):
        sections = ["I. Disposiciones generales", "III. Otras disposiciones"]
        departments = ["MINISTERIO DE TRABAJO Y ECONOMÍA SOCIAL","MINISTERIO DE INCLUSIÓN, SEGURIDAD SOCIAL Y MIGRACIONES", "MINISTERIO DE HACIENDA", "MINISTERIO DE ECONOMÍA, COMERCIO Y EMPRESA",
                       "MINISTERIO DE INDUSTRIA Y TURISMO", "MINISTERIO DE DERECHOS SOCIALES, CONSUMO Y AGENDA 2030", "MINISTERIO PARA LA TRANSICIÓN ECOLÓGICA Y EL RETO DEMOGRÁFICO",
                       "MINISTERIO DE SANIDAD", "MINISTERIO DE TRANSPORTES Y MOVILIDAD SOSTENIBLE", "MINISTERIO PARA LA TRANSFORMACIÓN DIGITAL Y DE LA FUNCIÓN PÚBLICA", "BANCO DE ESPAÑA"]

        for h3 in response.css("h3"):
            section = h3.xpath("string()").get().strip()
            if section in sections:
                content = []
                for sibling in h3.xpath("following-sibling::*"):
                    if sibling.root.tag in ["h2", "h3"]:
                        break
                    content.append(sibling)

                blocks = []
                current_block ={}

                for element in content:
                    text = element.xpath("string()").get().strip()

                    if element.root.tag == "h4":
                        if current_block and current_block["department"] in departments:
                            blocks.append(current_block)

                        current_block = {
                            "department": text,
                            "topic": None,
                            "text": ""
                        }

                    elif current_block and current_block["topic"] is None:
                        current_block["topic"] = text

                    elif current_block:
                        current_block["text"] += text + "\n"

                if current_block and current_block["department"] in departments:
                    blocks.append(current_block)

                for block in blocks:
                    yield {
                        "date": date_str,
                        "section": section,
                        "department": block["department"],
                        "topic": block["topic"],
                        "text": block["text"].strip()
                    }