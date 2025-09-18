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
    return " ".join(str(s).split()) if s is not None else None

class BOEPipeline:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._batch = 0
        self._batch_size = int(os.getenv("DB_BATCH_SIZE", "100"))

    def open_spider(self, spider):
        self.connection = pymysql.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT')),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        self.cursor = self.connection.cursor()
        self.connection.ping(reconnect=True)
        self.logger.info("Conectado a MySQL DB=%s", os.getenv('DB_NAME'))

    def close_spider(self, spider):
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

        # Limpieza y validación
        required_fields = ["boe_code", "date", "section", "department", 
        "topic", "preamble", "url", "pdf_url", "source"]
        missing = []
        for field in required_fields:
            value = _clean(adapter.get(field))
            if not value:
                missing.append(field)
            else:
                adapter[field] = value
        # campos, faltan = {}, []
        # for field in adapter.field_names():
        #     valor = _clean(adapter.get(field))
        #     campos[field] = valor
        #     if not valor:
        #         faltan.append(field)

        if missing:
            for m in missing:
                spider.crawler.stats.inc_value(f"pipeline/missing_field/{m}")
            spider.crawler.stats.inc_value("pipeline/items_dropped/incomplete")
            raise DropItem(f"Item incompleto. Faltan: {missing}")

        # boe_code   = campos["boe_code"]
        # date       = campos["date"]
        # section    = campos["section"]
        # department = campos["department"]
        # topic      = campos["topic"]
        # preamble   = campos["preamble"]
        # url        = campos["url"]
        # pdf_url    = campos["pdf_url"]
        # source     = campos["source"]

        try:
            result = analyze_text(adapter["pdf_url"])
            save = result.get("guardar_en_bd", False)
            summary = result.get("resumen", "")
            impact = result.get("impacto", "")

            adapter["summary"] = summary
            adapter["impact"] = impact

            if not save:
                spider.logger.info("Descartado (sin impacto en el sector retail): %s", adapter["boe_code"])
                spider.crawler.stats.inc_value("pipeline/items_dropped/no_retail_impact")
                raise DropItem("Descartado por análisis semántico (sin impacto en el sector retail)")
        
        except Exception as e:
            spider.logger.exception("Error analizando con Gemini: %s", e)
            spider.crawler.stats.inc_value("pipeline/items_failed/gemini_error")
            raise DropItem("Error al procesar con Gemini")

        if not adapter["summary"] or not adapter["impact"]:
            spider.crawler.stats.inc_value("pipeline/items_dropped/incomplete_post_analysis")
            raise DropItem("Faltan summary o impact tras análisis")

        sql = """
            INSERT INTO boe_items (
                boe_code, date, section, department, topic, preamble, url, pdf_url, summary, impact, source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                date = VALUES(date),
                section = VALUES(section),
                department = VALUES(department),
                topic = VALUES(topic),
                preamble = VALUES(preamble),
                url = VALUES(url),
                pdf_url = VALUES(pdf_url),
                summary = VALUES(summary),
                impact = VALUES(impact),
                source = VALUES(source)
        """
        values = (boe_code, date, section, department, topic, preamble, url, pdf_url, summary, impact, source)

        try:
            self.connection.ping(reconnect=True)
            self.cursor.execute(sql, values)

            spider.crawler.stats.inc_value("pipeline/items_saved/db_ok")
            self._batch += 1
            if self._batch % self._batch_size == 0:
                self.connection.commit()
                self.logger.info("Commit por batch (items=%s)", self._batch)

            self.logger.info("UPSERT OK: %s", boe_code)
            # if os.getenv("ENABLE_GEMINI_SUMMARY", "1") == "1":
            #     summary = extract_and_summarize(pdf_url)
            #     item["text"] = summary
            #     self.logger.info("Resumen Gemini generado para %s", boe_code)
            return item

        except mysql_err.OperationalError as e:
            spider.crawler.stats.inc_value("pipeline/items_failed/OperationalError")
            spider.crawler.stats.inc_value("pipeline/items_failed/db_error")  # agregado
            self.connection.rollback()
            self.logger.exception("OperationalError BD en %s: %s", boe_code, e)
            raise
        except mysql_err.IntegrityError as e:
            spider.crawler.stats.inc_value("pipeline/items_failed/IntegrityError")
            spider.crawler.stats.inc_value("pipeline/items_failed/db_error")  # agregado
            self.connection.rollback()
            self.logger.exception("IntegrityError BD en %s: %s", boe_code, e)
            raise
        except Exception as e:
            spider.crawler.stats.inc_value("pipeline/items_failed/Other")
            spider.crawler.stats.inc_value("pipeline/items_failed/db_error")  # agregado
            self.connection.rollback()
            self.logger.exception("Error BD en %s: %s", boe_code, e)
            raise