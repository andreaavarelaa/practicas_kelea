# extensions.py
import json
import logging
import os
from datetime import timezone

import pymysql
from dotenv import load_dotenv
from scrapy import signals

load_dotenv()


class RunLogger:
    """
    Extensión que:
    - Cuenta items caídos (y motivo) vía señales.
    - Inserta un resumen JSON de la ejecución en MySQL al cerrar el spider.
    - (Opcional) imprime el resumen en logs.
    """

    def __init__(self, stats):
        self.stats = stats
        self.logger = logging.getLogger(self.__class__.__name__)
        # Config de guardado en BD
        self.db_enabled = bool(int(os.getenv("RUN_DB_LOG_ENABLED", "1")))
        self.table = os.getenv("RUN_DB_LOG_TABLE", "run_log")
        self._conn = None
        self._cursor = None

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls(crawler.stats)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.item_dropped, signal=signals.item_dropped)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def _open_db(self):
        if not self.db_enabled or self._conn:
            return
        try:
            self._conn = pymysql.connect(
                host=os.getenv("DB_HOST"),
                port=int(os.getenv("DB_PORT")),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME"),
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
            )
            self._cursor = self._conn.cursor()
            # No creamos tabla aquí para no recalcar permisos; asume creada por DDL
        except Exception as e:
            self.logger.exception("No se pudo abrir conexión MySQL para run_log: %s", e)
            self.db_enabled = False  # desactiva para este run

    def _close_db(self):
        try:
            if self._conn:
                self._conn.commit()
        except Exception as e:
            self.logger.exception("Error commit run_log: %s", e)
        finally:
            try:
                if self._cursor:
                    self._cursor.close()
                if self._conn:
                    self._conn.close()
            except Exception as e:
                self.logger.exception("Error cerrando conexión run_log: %s", e)
            self._cursor = None
            self._conn = None

    def spider_opened(self, spider):
        self.logger.info("Spider abierto: %s", spider.name)
        if self.db_enabled:
            self._open_db()

    def item_dropped(self, item, response, exception, spider):
        # Cuenta drops y agrupa por motivo de DropItem (o excepción)
        self.stats.inc_value("run/items_dropped")
        self.stats.inc_value(f"run/drop_reason/{str(exception)}")

    def spider_closed(self, spider, reason):
        s = self.stats.get_stats()

        # Agregados para dicts JSON
        http_responses = {
            k.split("http/response/")[1]: v
            for k, v in s.items()
            if isinstance(k, str) and k.startswith("http/response/")
        }
        http_errors = {
            k.split("http/error/")[1]: v
            for k, v in s.items()
            if isinstance(k, str) and k.startswith("http/error/")
        }
        parse_issues = {
            k.split("parse/issues/")[1]: v
            for k, v in s.items()
            if isinstance(k, str) and k.startswith("parse/issues/")
        }
        drop_reasons = {
            k.split("run/drop_reason/")[1]: v
            for k, v in s.items()
            if isinstance(k, str) and k.startswith("run/drop_reason/")
        }

        # Tiempos y duración (Scrapy da UTC con tzinfo)
        start_dt = s.get("start_time")
        finish_dt = s.get("finish_time")
        if start_dt:
            start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
        if finish_dt:
            finish_dt = finish_dt.astimezone(timezone.utc).replace(tzinfo=None)
        duration = int((finish_dt - start_dt).total_seconds()) if start_dt and finish_dt else 0

        # Intenta leer los args que pasaste al spider (si existen)
        start_date = getattr(spider, "start_date", None)
        end_date = getattr(spider, "end_date", None)

        resumen = {
            "reason": reason,
            "items_scraped": s.get("item_scraped_count", 0),
            "items_dropped": s.get("run/items_dropped", 0),
            "drop_reasons": drop_reasons,
            "db_ok": s.get("pipeline/items_saved/db_ok", 0),
            "db_error": s.get("pipeline/items_failed/db_error", 0),
            "http_responses": http_responses,
            "http_errors": http_errors,
            "parse_issues": parse_issues,
        }

        # Log a consola (elige INFO o WARNING según tu preferencia)
        self.logger.info("Resumen de ejecución: %s", json.dumps(resumen, ensure_ascii=False))

        # Persistencia en BD
        if self.db_enabled and self._cursor:
            try:
                sql = f"""
                    INSERT INTO {self.table} (
                        spider, started_at_utc, finished_at_utc, duration_sec,
                        start_date, end_date, reason,
                        items_scraped, items_dropped, db_ok, db_error,
                        http_responses, http_errors, parse_issues, drop_reasons, extra
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                """
                extra = {
                    "project": os.getenv("BOT_NAME", spider.settings.get("BOT_NAME", "")),
                    "scrapy_version": spider.settings.get("SCRAPY_VERSION", ""),
                }
                self._cursor.execute(
                    sql,
                    (
                        spider.name,
                        start_dt,
                        finish_dt,
                        duration,
                        getattr(start_date, "isoformat", lambda: start_date)(),
                        getattr(end_date, "isoformat", lambda: end_date)(),
                        reason,
                        resumen["items_scraped"],
                        resumen["items_dropped"],
                        resumen["db_ok"],
                        resumen["db_error"],
                        json.dumps(http_responses, ensure_ascii=False),
                        json.dumps(http_errors, ensure_ascii=False),
                        json.dumps(parse_issues, ensure_ascii=False),
                        json.dumps(drop_reasons, ensure_ascii=False),
                        json.dumps(extra, ensure_ascii=False),
                    ),
                )
                self._conn.commit()
                self.logger.info("run_log insertado en tabla %s", self.table)
            except Exception as e:
                self.logger.exception("No se pudo insertar run_log: %s", e)
            finally:
                self._close_db()
        else:
            # Si no hay BD, asegúrate de cerrar si se abrió
            self._close_db()
