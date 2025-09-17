BOT_NAME = "boe"

SPIDER_MODULES = ["spiders"]
NEWSPIDER_MODULE = "spiders"

# Respeto robots + UA identificable
ROBOTSTXT_OBEY = True
USER_AGENT = "boe-scraper/1.0 (+tu-correo@ejemplo.com)"

# Ritmo y reintentos
DOWNLOAD_DELAY = 0.25
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504]

# Exportación
FEED_EXPORT_ENCODING = "utf-8"

# Logging base
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# Extensión de resumen
EXTENSIONS = {
    "extensions.RunLogger": 300,
}

# Pipeline de BD
ITEM_PIPELINES = {
    "pipelines.BOEPipeline": 300,
}
