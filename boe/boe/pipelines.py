import os
import pymysql

from itemadapter import ItemAdapter
from dotenv import load_dotenv
from scrapy.exceptions import DropItem

load_dotenv()

def _clean(s):
    return " ".join(str(s).split()) if s is not None else None

class BOEPipeline:

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

    def close_spider(self, spider):
        self.connection.commit()
        self.cursor.close()
        self.connection.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # --- Validación mínima ---
        boe_code = _clean(adapter.get("boe_code"))
        date     = _clean(adapter.get("date"))
        preamble = _clean(adapter.get("preamble"))

        if not boe_code or not date or not preamble:
            raise DropItem(f"Item incompleto: boe_code={boe_code}, date={date}, preamble={preamble}")

        # --- Limpieza del resto ---
        section    = _clean(adapter.get("section"))
        department = _clean(adapter.get("department"))
        topic      = _clean(adapter.get("topic"))
        pdf_url    = _clean(adapter.get("pdf_url"))
        url        = _clean(adapter.get("url"))
        source     = _clean(adapter.get("source"))

        # --- SQL ---
        sql = """
            INSERT INTO boe (
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
