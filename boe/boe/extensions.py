import json
import logging
import os
import pymysql

from datetime import timezone, datetime
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from scrapy import signals

from scrapy.crawler import Crawler
from scrapy.spiders import Spider
from scrapy.statscollectors import StatsCollector
from twisted.python.failure import Failure

load_dotenv()


class RunLogger:
    """
    Extensión de Scrapy para observabilidad de ejecuciones:

    - Escucha señales para:
        * spider_opened: abrir (opcional) conexión a BD para el log de la ejecución.
        * item_dropped: contar items caídos y agrupar por motivo.
        * spider_closed: construir un resumen y:
            · Loguearlo en consola (JSON).
            · Insertarlo en MySQL (si está habilitado).

    Diseño:
      • No crea la tabla en caliente (asumimos DDL gestionado fuera).
      • Controla commit/rollback y cierre de conexión de forma segura.
      • Usa Scrapy stats como fuente de métricas (http/response/*, http/error/*, parse/issues/*, etc.).

    Variables de entorno:
      - RUN_DB_LOG_ENABLED: "1" (por defecto) para habilitar guardado en BD; "0" desactiva.
      - RUN_DB_LOG_TABLE: nombre de la tabla (por defecto: "run_log").
      - DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME: credenciales MySQL.

    Requisitos BD:
      • Tabla {RUN_DB_LOG_TABLE} con columnas compatibles (ver README abajo).
    """

    def __init__(self, stats: StatsCollector):
        self.stats: StatsCollector = stats
        self.logger = logging.getLogger(self.__class__.__name__)

        # Config de guardado en BD
        self.db_enabled: bool = bool(int(os.getenv("RUN_DB_LOG_ENABLED", "1")))
        self.table: str = os.getenv("RUN_DB_LOG_TABLE", "run_log")

        # Conexión/cursor se abren on-demand al abrir el spider
        self._conn: Optional[pymysql.Connection] = None
        self._cursor: Optional[pymysql.cursors.DictCursor] = None

    # ---- Ciclo de vida: registro de señales ---------------------------------

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "RunLogger":
        """
        Hook estándar de Scrapy para inicializar extensiones y conectar señales.
        """
        ext = cls(crawler.stats)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.item_dropped, signal=signals.item_dropped)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    # ---- Gestión de BD -------------------------------------------------------

    def _open_db(self) -> None:
        """
        Abre la conexión a MySQL si está habilitado RUN_DB_LOG_ENABLED.
        Si falla, desactiva la persistencia para esta ejecución.
        """
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
            # No creamos tabla aquí para no exigir permisos DDL en runtime.
        except Exception as e:
            self.logger.exception("No se pudo abrir conexión MySQL para run_log: %s", e)
            self.db_enabled = False  # desactiva persistencia para este run

    def _close_db(self) -> None:
        """
        Hace commit pendiente y cierra recursos de BD de forma segura.
        """
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

    # ---- Señales -------------------------------------------------------------

    def spider_opened(self, spider: Spider) -> None:
        """
        Se dispara al abrir el spider. Prepara (si procede) la conexión a BD.
        """
        self.logger.info("Spider abierto: %s", spider.name)
        if self.db_enabled:
            self._open_db()

    def item_dropped(self, item: Any, response: Any, exception: Exception, spider: Spider) -> None:
        """
        Se dispara cuando un item es descartado (DropItem u otros errores).

        - Sube contadores globales y por motivo de drop.
        - Útil para detectar validaciones que fallan sistemáticamente.
        """
        self.stats.inc_value("run/items_dropped")
        self.stats.inc_value(f"run/drop_reason/{str(exception)}")

    def spider_closed(self, spider: Spider, reason: str) -> None:
        """
        Se dispara al cerrar el spider. Construye un resumen y lo:
          - Imprime en logs (JSON).
          - Inserta en BD (si habilitado).

        Campos agregados:
          • http_responses:  stats http/response/*
          • http_errors:     stats http/error/*
          • parse_issues:    stats parse/issues/*
          • drop_reasons:    stats run/drop_reason/*
          • items_scraped, items_dropped, db_ok, db_error
          • started/finished UTC + duración
          • start_date / end_date (si el spider los define)
        """
        s: Dict[str, Any] = self.stats.get_stats()

        # ---- Agregados a dicts JSON -----------------------------------------
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

        # ---- Tiempos (Scrapy entrega timezone-aware, convertimos a UTC naive) -
        start_dt: Optional[datetime] = s.get("start_time")
        finish_dt: Optional[datetime] = s.get("finish_time")
        if start_dt:
            start_dt = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
        if finish_dt:
            finish_dt = finish_dt.astimezone(timezone.utc).replace(tzinfo=None)
        duration = int((finish_dt - start_dt).total_seconds()) if start_dt and finish_dt else 0

        # ---- Args del spider (si existen) ------------------------------------
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

        # ---- Log a consola (puedes cambiar a .warning si prefieres) ----------
        self.logger.info("Resumen de ejecución: %s", json.dumps(resumen, ensure_ascii=False))

        # ---- Persistencia en BD ----------------------------------------------
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

                # Nota: start_date/end_date pueden ser date o str; normalizamos a str
                def _iso(x: Any) -> Optional[str]:
                    if x is None:
                        return None
                    if hasattr(x, "isoformat"):
                        return x.isoformat()
                    return str(x)

                self._cursor.execute(
                    sql,
                    (
                        spider.name,
                        start_dt,
                        finish_dt,
                        duration,
                        _iso(start_date),
                        _iso(end_date),
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
            # Si no hay BD o falló, intenta cerrar por si se abrió previamente
            self._close_db()