BOT_NAME = "boe"
SPIDER_MODULES = ["boe.spiders"]
NEWSPIDER_MODULE = "boe.spiders"

# Respetar normas del sitio (por ética y evitar bloqueos)
ROBOTSTXT_OBEY = True

# Decir quién eres (como dejar tu tarjeta de visita)
USER_AGENT = "boe-scraper/1.0 (+tu-correo@ejemplo.com)"

# No ir demasiado rápido (0.25 segundos entre peticiones)
DOWNLOAD_DELAY = 0.25

# Reintentar si hay errores puntuales en la web
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504]

# Guardar en UTF-8 (para que los acentos salgan bien)
FEED_EXPORT_ENCODING = "utf-8"





# from datetime import datetime
# import os

# BOT_NAME = "boe"
# SPIDER_MODULES = ["boe.spiders"]
# NEWSPIDER_MODULE = "boe.spiders"

# # Respeta robots.txt y usa un User-Agent identificable
# ROBOTSTXT_OBEY = True
# USER_AGENT = os.getenv("SCRAPY_USER_AGENT", f"{BOT_NAME}/1.0 (+contacto: tu-correo@ejemplo.com)")

# # Ritmo razonable (el spider puede sobreescribir con custom_settings)
# CONCURRENT_REQUESTS = 8
# CONCURRENT_REQUESTS_PER_DOMAIN = 4
# DOWNLOAD_DELAY = 0.25

# # Reintentos y timeout básicos (más estabilidad)
# RETRY_ENABLED = True
# RETRY_TIMES = 3
# DOWNLOAD_TIMEOUT = 30
# COOKIES_ENABLED = False

# # AutoThrottle: que Scrapy se autorregule según latencia
# AUTOTHROTTLE_ENABLED = True
# AUTOTHROTTLE_START_DELAY = 0.5
# AUTOTHROTTLE_MAX_DELAY = 5
# AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

# # Cabeceras por defecto (preferimos español)
# DEFAULT_REQUEST_HEADERS = {
#     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#     "Accept-Language": "es-ES,es;q=0.9",
#     "User-Agent": USER_AGENT,
# }

# # Pipeline para BD (inserta/actualiza)
# ITEM_PIPELINES = {
#     "boe.pipelines.BoePipeline": 300,
# }

# # Exportación a archivo (snapshot de lo scrapeado)
# FEED_EXPORT_ENCODING = "utf-8"
# EXPORTS_DIR = os.getenv("SCRAPY_EXPORTS_DIR", "exports")
# os.makedirs(EXPORTS_DIR, exist_ok=True)
# FEEDS = {
#     os.path.join(EXPORTS_DIR, f"boe_{datetime.now():%Y%m%d_%H%M%S}.jsonl"): {
#         "format": "jsonlines",
#         "encoding": "utf-8",
#         "overwrite": True,
#         "item_export_kwargs": {"ensure_ascii": False},
#     }
# }

# # Logging a archivo por job
# LOG_LEVEL = os.getenv("SCRAPY_LOG_LEVEL", "INFO")
# LOG_FILE = os.path.join(EXPORTS_DIR, f"scrapy_{datetime.now():%Y%m%d_%H%M%S}.log")

# # Cache HTTP solo en desarrollo (desactiva con: SCRAPY_HTTPCACHE_ENABLED=0)
# HTTPCACHE_ENABLED = bool(int(os.getenv("SCRAPY_HTTPCACHE_ENABLED", "1")))
# HTTPCACHE_DIR = "httpcache"
# HTTPCACHE_EXPIRATION_SECS = 0
