from fastapi import FastAPI
from subprocess import run
from datetime import date

app = FastAPI()

@app.get("/run")
def run_scraper():
    today = date.today().isoformat()

    command = [
        "scrapy", "crawl", "boe",
        "-a", f"start_date={today}",
        "-a", f"end_date={today}"
    ]

    result = run(command, capture_output=True, text=True, cwd="boe")

    return {
        "date": today,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    }