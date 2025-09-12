import scrapy

class BOESpider(scrapy.Spider):
    name = "boe"
    start_urls = ["https://boe.es/boe/dias/2025/09/10/"]

    def parse(self, response):
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
                        "section": section,
                        "department": block["department"],
                        "topic": block["topic"],
                        "text": block["text"].strip()
                    }