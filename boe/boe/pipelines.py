# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import os
import pymysql

from itemadapter import ItemAdapter
from dotenv import load_dotenv

load_dotenv()

class BoePipeline:

    def open_spider(self, spider):
        self.connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
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

        sql = """
            INSERT INTO boe (
                boe_code, date, section, department, topic, title, pdf_url
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                date = VALUES(date),
                section = VALUES(section),
                department = VALUES(department),
                topic = VALUES(topic),
                title = VALUES(title),
                pdf_url = VALUES(pdf_url)
        """

        values = (
            adapter.get("boe_code"),
            adapter.get("date"),
            adapter.get("section"),
            adapter.get("department"),
            adapter.get("topic"),
            adapter.get("title"),
            adapter.get("pdf_url"),
        )

        self.cursor.execute(sql, values)
        return item