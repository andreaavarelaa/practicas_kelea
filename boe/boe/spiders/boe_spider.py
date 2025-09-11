import scrapy

class BOESpider(scrapy.Spider):
    name = "boe"

    start_urls = ["https://boe.es/rss/boe.php?s=1"]

    def parse(self, response):
        for item in response.css("item"):
            texto = item.css("title::text").get()
            url = item.css("link::text").get()
            fecha = item.css("pubDate::text").get()
            id = item.css("guid::text").get()

            yield {
            "id": id,
            "fecha": fecha,
            "url": url,
            "texto_completo_boe": texto,
            }