import scrapy

class BOESpider(scrapy.Spider):
    name = "boe"
    start_urls = ["https://boe.es/boe/dias/2025/09/10/"]

    def parse(self, response):
        secciones = ["I. Disposiciones generales", "III. Otras disposiciones"]
        departments = ["MINISTERIO DE TRABAJO Y ECONOMÍA SOCIAL","MINISTERIO DE INCLUSIÓN, SEGURIDAD SOCIAL Y MIGRACIONES", "MINISTERIO DE HACIENDA", "MINISTERIO DE ECONOMÍA, COMERCIO Y EMPRESA",
                       "MINISTERIO DE INDUSTRIA Y TURISMO", "MINISTERIO DE DERECHOS SOCIALES, CONSUMO Y AGENDA 2030", "MINISTERIO PARA LA TRANSICIÓN ECOLÓGICA Y EL RETO DEMOGRÁFICO",
                       "MINISTERIO DE SANIDAD", "MINISTERIO DE TRANSPORTES Y MOVILIDAD SOSTENIBLE", "MINISTERIO PARA LA TRANSFORMACIÓN DIGITAL Y DE LA FUNCIÓN PÚBLICA", "BANCO DE ESPAÑA"]

        for h3 in response.css("h3"):
            topic = h3.xpath("string()").get().strip()
            if topic in secciones:
                contenido = []
                for sibling in h3.xpath("following-sibling::*"):
                    if sibling.root.tag in ["h2", "h3"]:
                        break
                    contenido.append(sibling)

                bloques = []
                current_bloque ={}

                for element in contenido:
                    texto = element.xpath("string()").get().strip()

                    if element.root.tag == "h4":
                        if current_bloque and current_bloque["departamento"] in departments:
                            bloques.append(current_bloque)

                        current_bloque = {
                            "departamento": texto,
                            "topic": None,
                            "texto": ""
                        }

                    elif current_bloque and current_bloque["topic"] is None:
                        current_bloque["topic"] = texto
                        
                    elif current_bloque:
                        current_bloque["texto"] += texto + "\n"

                if current_bloque and current_bloque["departamento"] in departments:
                    bloques.append(current_bloque)

                for bloque in bloques:
                    yield {
                        "seccion": topic,
                        "departamento": bloque["departamento"],
                        "topic": bloque["topic"],
                        "texto": bloque["texto"].strip()
                    }