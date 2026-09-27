from fastapi import FastAPI

from app.api.assistant import router as assistant_router

app = FastAPI(title="EPI Energy Assistant", version="0.1.0")
app.include_router(assistant_router)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}

