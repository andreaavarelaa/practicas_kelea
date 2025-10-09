from fastapi import FastAPI
from subprocess import run
from datetime import date

app = FastAPI()

@app.get("/run")
def run_scraper():
    today = date.today().isoformat()

    command = [
        "scrapy", "crawl", "boe",
        "-a", "start_date=2025-10-07",
        "-a", "end_date=2025-10-07"
    ]

    result = run(command, capture_output=True, text=True, cwd="boe")

    return {
        "date": today,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    }