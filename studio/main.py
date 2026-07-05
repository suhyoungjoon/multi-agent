from fastapi import FastAPI

app = FastAPI(title="Advanced Agent Studio")


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}
