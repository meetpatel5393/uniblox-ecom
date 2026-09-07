from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="uniblox-ecom",
    description="E-commerce backend with cart management, checkout, and milestone-based coupon rewards.",
    version="1.0.0",
)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


# routers will be registered here in later phases


# static mount must come last — it acts as a catch-all and would swallow API routes if placed earlier
app.mount("/", StaticFiles(directory="static", html=True), name="static")
