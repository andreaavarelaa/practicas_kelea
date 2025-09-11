import scrapy

class BOESpider(scrapy.Spider):
    name = "boe"
    start_urls = ["https://boe.es/boe/dias/2025/09/10/"]

    def parse(self, response):
        secciones = ["I. Disposiciones generales", "III. Otras disposiciones"]

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

                    if texto.isupper() and len(texto) < 100:
                        if current_bloque:
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

                if current_bloque:
                    bloques.append(current_bloque)

                for bloque in bloques:
                    yield {
                        "seccion": titulo,
                        "departamento": bloque["departamento"],
                        "topic": bloque["topic"],
                        "texto": bloque["texto"].strip()
                    }