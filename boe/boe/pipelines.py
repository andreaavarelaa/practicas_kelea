import os
import logging
import pymysql

from pymysql import err as mysql_err
from itemadapter import ItemAdapter
from dotenv import load_dotenv
from scrapy.exceptions import DropItem
from boe.gemini_utils import analyze_text

load_dotenv()


def _clean(s):
    """
    Normaliza cadenas eliminando espacios extra internos y en bordes.
    Devuelve None si la entrada es None.

    Args:
        s: Cualquier valor; se convierte a str si no es None.

    Returns:
        str | None: cadena limpia o None.
    """
    return " ".join(str(s).split()) if s is not None else None


class BOEPipeline:
    """
    Pipeline de Scrapy para insertar/actualizar (UPSERT) items del BOE en MySQL.

    - Valida campos requeridos: si falta alguno, descarta el item (DropItem) y registra métricas.
    - Limpia valores de texto (_clean) antes de persistir.
    - Inserta con `INSERT ... ON DUPLICATE KEY UPDATE` para que el proceso sea idempotente.
    - Hace commit por lotes (batch) para mejorar rendimiento.
    - Registra métricas en `crawler.stats` (útil para dashboards/monitorización).

    Requisitos:
      • Tabla `boe_v2` con clave única/primaria en `boe_code`.
      • Variables de entorno de conexión (ver README más abajo).
    """

    def __init__(self):
        # Logger del pipeline (útil para diferenciarlo del logger del spider)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Contador interno de items procesados desde el último commit
        self._batch = 0

        # Tamaño de lote para commits (reduce I/O). Por defecto 100 si no hay env.
        self._batch_size = int(os.getenv("DB_BATCH_SIZE", "100"))

    def open_spider(self, spider):
        """
        Se ejecuta una vez cuando se abre el spider.
        Establece la conexión y el cursor a MySQL.
        """

        self.logger.info("DB_HOST=%s DB_PORT=%s DB_NAME=%s",
                 os.getenv('DB_HOST'), os.getenv('DB_PORT'), os.getenv('DB_NAME'))

        self.connection = pymysql.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT')),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,  # Controlamos los commits manualmente
        )
        self.cursor = self.connection.cursor()

        # Asegura que la conexión está viva (reconecta si hiciera falta)
        self.connection.ping(reconnect=True)

        self.logger.info("Conectado a MySQL DB=%s", os.getenv('DB_NAME'))

    def close_spider(self, spider):
        """
        Se ejecuta una vez cuando se cierra el spider.
        Hace un último commit y cierra recursos.
        """
        try:
            self.connection.commit()
            self.logger.info("Commit final realizado.")
        except Exception as e:
            self.logger.exception("Error en commit final: %s", e)
        finally:
            try:
                self.cursor.close()
                self.connection.close()
                self.logger.info("Conexión a BD cerrada.")
            except Exception as e:
                self.logger.exception("Error cerrando conexión: %s", e)

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        spider.crawler.stats.inc_value("pipeline/items_seen")

        # Validación mínima de campos base
        required_fields = ["boe_code", "date", "section", "department",
                        "topic", "preamble", "url", "pdf_url", "source"]
        missing = []
        for field in required_fields:
            value = _clean(adapter.get(field))
            if not value:
                missing.append(field)
            else:
                adapter[field] = value

        if missing:
            for m in missing:
                spider.crawler.stats.inc_value(f"pipeline/missing_field/{m}")
            spider.crawler.stats.inc_value("pipeline/items_dropped/incomplete")
            raise DropItem(f"Item incompleto. Faltan: {missing}")

        # --- Análisis semántico (Gemini) ---
        try:
            result = analyze_text(adapter["pdf_url"])  # usa wrapper de gemini_utils
            save = result.get("guardar_en_bd", False)
            adapter["summary"] = result.get("resumen", "") or ""

            if not save:
                spider.logger.info("Descartado (sin impacto retail): %s", adapter["boe_code"])
                spider.crawler.stats.inc_value("pipeline/items_dropped/no_retail_impact")
                raise DropItem("Descartado por análisis semántico (sin impacto retail)")

        except Exception as e:
            spider.logger.exception("Error analizando con Gemini: %s", e)
            spider.crawler.stats.inc_value("pipeline/items_failed/gemini_error")
            raise DropItem("Error al procesar con Gemini")

        if not adapter["summary"]:
            spider.crawler.stats.inc_value("pipeline/items_dropped/incomplete_post_analysis")
            raise DropItem("Falta summary tras análisis")

        # --- UPSERT ---
        sql = """
            INSERT INTO boe_items (
                boe_code, date, section, department, topic, preamble, url, pdf_url, summary, source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                date = VALUES(date),
                section = VALUES(section),
                department = VALUES(department),
                topic = VALUES(topic),
                preamble = VALUES(preamble),
                url = VALUES(url),
                pdf_url = VALUES(pdf_url),
                summary = VALUES(summary),
                source = VALUES(source)
        """
        values = (
            adapter["boe_code"],
            adapter["date"],
            adapter["section"],
            adapter["department"],
            adapter["topic"],
            adapter["preamble"],
            adapter["url"],
            adapter["pdf_url"],
            adapter["summary"],
            adapter["source"],
        )

        try:
            self.connection.ping(reconnect=True)
            self.cursor.execute(sql, values)
            spider.crawler.stats.inc_value("pipeline/items_saved/db_ok")
            self._batch += 1

            if self._batch % self._batch_size == 0:
                self.connection.commit()
                self.logger.info("Commit por batch (items acumulados=%s)", self._batch)

            self.logger.info("UPSERT OK: %s", adapter["boe_code"])
            return item

        except mysql_err.OperationalError as e:
            spider.crawler.stats.inc_value("pipeline/items_failed/OperationalError")
            spider.crawler.stats.inc_value("pipeline/items_failed/db_error")
            self.connection.rollback()
            self.logger.exception("OperationalError BD en %s: %s", adapter["boe_code"], e)
            raise
        except mysql_err.IntegrityError as e:
            spider.crawler.stats.inc_value("pipeline/items_failed/IntegrityError")
            spider.crawler.stats.inc_value("pipeline/items_failed/db_error")
            self.connection.rollback()
            self.logger.exception("IntegrityError BD en %s: %s", adapter["boe_code"], e)
            raise
        except Exception as e:
            spider.crawler.stats.inc_value("pipeline/items_failed/Other")
            spider.crawler.stats.inc_value("pipeline/items_failed/db_error")
            self.connection.rollback()
            self.logger.exception("Error BD en %s: %s", adapter["boe_code"], e)
            raise