"""
pipelines.py
------------

Pipeline de Scrapy encargado de guardar en la base de datos MySQL
los items que se extraen del BOE.

Flujo de trabajo:
1. Cuando el spider arranca (`open_spider`), se abre la conexión con MySQL.
2. Cada item pasa por `process_item`, donde:
   - Se limpian y validan todos los campos.
   - Si falta alguno, se descarta con `DropItem`.
   - Si está completo, se inserta en la tabla `boe_v2`. 
     Si ya existe (mismo `boe_code`), se actualiza.
3. Cuando el spider termina (`close_spider`), se hace `commit` y se cierra la conexión.

Requisitos:
- Archivo `.env` con las variables:
  DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
"""

import os
import pymysql

from itemadapter import ItemAdapter
from dotenv import load_dotenv
from scrapy.exceptions import DropItem

# Cargar variables de entorno (.env) con las credenciales de la BD
load_dotenv()


def _clean(s):
    """
    Normaliza strings eliminando espacios repetidos y caracteres invisibles.

    Args:
        s (str | None): Texto a limpiar.

    Returns:
        str | None: Texto limpio o None si estaba vacío.
    """
    return " ".join(str(s).split()) if s is not None else None


class BOEPipeline:
    """
    Pipeline para insertar ítems del BOE en MySQL.
    """

    def open_spider(self, spider):
        """
        Se ejecuta al abrir el spider.
        Establece la conexión a la base de datos usando las variables de entorno.
        """
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
        print("Conectando a base de datos:", os.getenv('DB_NAME'))

    def close_spider(self, spider):
        """
        Se ejecuta al cerrar el spider.
        Confirma los cambios y cierra la conexión.
        """
        self.connection.commit()
        self.cursor.close()
        self.connection.close()

    def process_item(self, item, spider):
        """
        Procesa cada item:
        - Limpia y valida todos los campos.
        - Descarta el item si falta alguno.
        - Inserta en la tabla boe_v2 (o actualiza si ya existía).

        Args:
            item (scrapy.Item): Item extraído por el spider.
            spider (scrapy.Spider): Instancia del spider que emitió el item.

        Returns:
            scrapy.Item: El item procesado (si se insertó con éxito).
        """
        adapter = ItemAdapter(item)

        # Validación y limpieza 
        campos = {}
        faltan = []
        for field in adapter.field_names():
            valor = _clean(adapter.get(field))
            campos[field] = valor
            if not valor:
                faltan.append(field)

        if faltan:
            raise DropItem(f"Item incompleto. Faltan: {faltan}")

        # Variables con los valores limpios
        boe_code   = campos["boe_code"]
        date       = campos["date"]
        section    = campos["section"]
        department = campos["department"]
        topic      = campos["topic"]
        preamble   = campos["preamble"]
        url        = campos["url"]
        pdf_url    = campos["pdf_url"]
        source     = campos["source"]

        # SQL: inserta o actualiza si ya existe 
        sql = """
            INSERT INTO boe_v2 (
                boe_code, date, section, department, topic, preamble, url, pdf_url, source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                date = VALUES(date),
                section = VALUES(section),
                department = VALUES(department),
                topic = VALUES(topic),
                preamble = VALUES(preamble),
                url = VALUES(url),
                pdf_url = VALUES(pdf_url),
                source = VALUES(source)
        """

        values = (
            boe_code,
            date,
            section,
            department,
            topic,
            preamble,
            url,
            pdf_url,
            source
        )

        self.cursor.execute(sql, values)
        return item
