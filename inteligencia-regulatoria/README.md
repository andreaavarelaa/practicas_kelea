# BOE Scraper

Scraper basado en [Scrapy](https://scrapy.org) para recolectar y almacenar disposiciones normativas publicadas en el **Boletín Oficial del Estado (BOE)**.

Este proyecto permite automatizar la extracción de datos estructurados del BOE, filtrando por secciones y departamentos relevantes para el sector de retail, y almacenando la información directamente en una base de datos MySQL.

---

## Requisitos

- Python 3.8+
- MySQL
- pip (Python package manager)

---

## Utilización

Para hacer el scraping, debemos ejecutar el siguiente comando en la terminal:

`scrapy crawl boe -a start_date=YYYY-MM-DD -a end_date=YYYY-MM-DD`