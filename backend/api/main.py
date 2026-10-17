"""FastAPI Application Entrypoint for FlytBase Asset Intelligence Copilot."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import duckdb

from backend.db.connection import close_all_connections, get_db, get_db_connection
from backend.api.routes.chat import router as chat_router
from backend.api.routes.users import router as users_router
from backend.api.routes.wells import router as wells_router
from backend.api.routes.feedback import router as feedback_router
from backend.api.routes.evaluation import router as evaluation_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: verify database and semantic views on startup."""
    try:
        con = get_db_connection()
        tables = con.execute("SHOW TABLES").fetchall()
        con.close()
        print(f"🚀 Asset Intelligence Copilot API started. DuckDB tables active: {len(tables)}")
    except Exception as e:
        print(f"⚠️ Warning: Database startup check warning: {e}")
    yield
    close_all_connections()
    print("🛑 Shutting down Asset Intelligence Copilot API.")


app = FastAPI(
    title="FlytBase Asset Intelligence Copilot API",
    version="1.0.0",
    description="Agentic AI copilot for oilfield asset operations with Generative UI, scoped runtime overrides, and two-level memory.",
    lifespan=lifespan,
)

# CORS middleware for local frontend development (Next.js, Vite, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(chat_router)
app.include_router(users_router)
app.include_router(wells_router)
app.include_router(feedback_router)
app.include_router(evaluation_router)


@app.get("/api/health", tags=["Health"])
@app.get("/health", tags=["Health"])
def health_check(con: duckdb.DuckDBPyConnection = Depends(get_db)) -> Dict[str, Any]:
    """Health & Readiness probe checking database connectivity and table state."""
    try:
        well_count = con.execute("SELECT COUNT(*) FROM wells").fetchone()[0]
        inspection_count = con.execute("SELECT COUNT(*) FROM raw_inspections").fetchone()[0]
        active_overrides = con.execute(
            "SELECT COUNT(*) FROM corrections_ledger WHERE source_origin = 'runtime_user_chat' AND is_active = TRUE"
        ).fetchone()[0]
        db_status = "connected"
    except Exception as e:
        well_count = 0
        inspection_count = 0
        active_overrides = 0
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "total_wells": well_count,
        "total_inspections": inspection_count,
        "active_runtime_overrides": active_overrides,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


# Static directory setup
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_dashboard():
    """Serve the interactive Copilot Web Dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html>
        <head><title>Asset Intelligence Copilot</title></head>
        <body style="font-family: sans-serif; padding: 40px; line-height: 1.6;">
            <h1>FlytBase Asset Intelligence Copilot API</h1>
            <p>API is running successfully. Interactive documentation is available at:</p>
            <ul>
                <li><a href="/docs">Swagger UI (/docs)</a></li>
                <li><a href="/redoc">ReDoc (/redoc)</a></li>
                <li><a href="/api/health">Health Check (/api/health)</a></li>
            </ul>
        </body>
        </html>
        """
    )
