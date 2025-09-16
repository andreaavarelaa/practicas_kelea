import scrapy

class BOEItem(scrapy.Item):
    boe_code = scrapy.Field()       # ID oficial BOE (ej: BOE-A-2025-12345)
    date = scrapy.Field()           # Fecha publicación (YYYY-MM-DD)
    section = scrapy.Field()        # Sección (I, II, III…)
    department = scrapy.Field()     # Ministerio / Organismo
    topic = scrapy.Field()          # Etiqueta temática 
    preamble = scrapy.Field()       # Preámbulo del articulo
    url = scrapy.Field()            # URL HTML 
    pdf_url = scrapy.Field()        # URL al PDF oficial
    # text = scrapy.Field()         # Texto completo (opcional)
    source = scrapy.Field()         # Fuente (ej: "BOE", "DOG", etc..)