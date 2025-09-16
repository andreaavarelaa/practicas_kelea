ASEGURARSE QUE ESTAMOS DENTRO DE LA CARPETA 'boe' ANTES DE EJECUTAR EL COMANDO POR TERMINAL

scrapy crawl boe -a start_date=2025-09-01 -a end_date=2025-09-11 -O resultados.jsonl -s LOG_LEVEL=INFO

(la parte de '-O resultados.jsonl -s LOG_LEVEL=INFO' la podemos omitir, ahora los datos pasan directamente a la BBDD)