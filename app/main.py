from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router as v1_router

_TAGS = [
    {
        "name": "Customers",
        "description": "Register and retrieve customer accounts.",
    },
    {
        "name": "Products",
        "description": "Browse the product catalog and check stock.",
    },
    {
        "name": "Carts",
        "description": "Create carts, manage line items, and place orders via checkout.",
    },
    {
        "name": "Orders",
        "description": "Retrieve placed orders by ID.",
    },
    {
        "name": "Admin",
        "description": (
            "**Administrative operations** — unauthenticated in this build; "
            "in production these would be gated behind an `X-Admin-Key` header "
            "or restricted to an internal network boundary. "
            "Includes: milestone coupon generation and sales reporting."
        ),
    },
    {
        "name": "Health",
        "description": "Liveness probe used by Railway and UptimeRobot.",
    },
]

app = FastAPI(
    title="Uniblox E-com API",
    description=(
        "Checkout and rewards e-commerce service.  \n\n"
        "All routes are versioned under `/api/v1/`.  \n"
        "Adding a v2 requires only a new `app/api/v2/` folder and one "
        "`include_router` line in `main.py` — existing v1 routes are untouched.  \n\n"
        "**Money:** all `*_cents` fields are integer cents (USD). Divide by 100 for display.  \n"
        "**IDs:** all public IDs are UUIDv7 (time-ordered, RFC 9562)."
    ),
    version="1.0.0",
    openapi_tags=_TAGS,
)

# ── Security middleware ───────────────────────────────────────────────────────
# CORS: allow all origins for the assessment UI; production should restrict to
# specific domains (e.g. allow_origins=["https://store.example.com"]).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
    expose_headers=["X-Request-Id"],
)

# TrustedHost: allows all hosts for the assessment; production should list
# the Railway domain and any custom domain explicitly.
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


# Versioned API
# To add v2: create app/api/v2/router.py, import it, and add the line below.
app.include_router(v1_router, prefix="/api/v1")

# Static SPA — must come last; a catch-all that would shadow API routes if mounted first
app.mount("/", StaticFiles(directory="static", html=True), name="static")
