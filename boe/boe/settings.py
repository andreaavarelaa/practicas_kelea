# settings.py — Configuración global de Scrapy para el proyecto BOE

# ---------------------------------------------------------------------------
# Identificación del proyecto
# ---------------------------------------------------------------------------

# Nombre interno del proyecto Scrapy
BOT_NAME = "boe"

# Módulos donde buscar spiders existentes y donde crear nuevos
SPIDER_MODULES = ["spiders"]
NEWSPIDER_MODULE = "spiders"

# ---------------------------------------------------------------------------
# Comportamiento HTTP / cortesía
# ---------------------------------------------------------------------------

# Respetar robots.txt (buenas prácticas con sitios web)
ROBOTSTXT_OBEY = True

# User-Agent personalizado para que el BOE identifique tu scraper
# Reemplaza el correo por uno real de contacto técnico
USER_AGENT = "boe-scraper/1.0 (+tu-correo@ejemplo.com)"

# ---------------------------------------------------------------------------
# Control de ritmo y reintentos
# ---------------------------------------------------------------------------

# Retraso entre peticiones consecutivas al mismo dominio (segundos)
# → reduce riesgo de bloqueo o saturación del servidor
DOWNLOAD_DELAY = 0.25

# Habilitar sistema de reintentos automáticos ante errores temporales
RETRY_ENABLED = True
# Número máximo de reintentos por petición fallida
RETRY_TIMES = 3
# Códigos HTTP que activan un reintento automático
RETRY_HTTP_CODES = [429, 500, 502, 503, 504]

# ---------------------------------------------------------------------------
# Exportación de datos
# ---------------------------------------------------------------------------

# Codificación UTF-8 por defecto para ficheros exportados (JSON, CSV, etc.)
FEED_EXPORT_ENCODING = "utf-8"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# Nivel de log por defecto (puede sobrescribirse con -s LOG_LEVEL=DEBUG al correr)
LOG_LEVEL = "INFO"

# Formato base de los mensajes de log
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s"

# Formato de fechas en los logs
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# Extensiones personalizadas
# ---------------------------------------------------------------------------

# Activamos la extensión RunLogger (ver extensions.py),
# que genera un resumen de ejecución y lo guarda en BD
EXTENSIONS = {
    "extensions.RunLogger": 300,  # la prioridad (300) define el orden de carga
}

# ---------------------------------------------------------------------------
# Pipelines de procesamiento de items
# ---------------------------------------------------------------------------

# Activamos el pipeline que guarda los items del BOE en MySQL
ITEM_PIPELINES = {
    "pipelines.BOEPipeline": 300,  # la prioridad (300) define el orden de ejecución
}
