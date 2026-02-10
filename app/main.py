from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.routes.descuento_auto_routes import router as descuento_router
from app.scheduler.jobs import scheduler, setup_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_scheduler()
    scheduler.start()
    print("Gaaa")
    yield
    scheduler.shutdown()
    print("ZZzz")


app = FastAPI(
    title="Gatillador de Descuentos Automáticos",
    description="API para aplicar Descuentos Automaticos",
    lifespan=lifespan
)

# Registrar rutas
app.include_router(descuento_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check del servicio"""
    return {"status": "ok", "scheduler_running": scheduler.running}


@app.get("/", tags=["Health"])
async def root():
    """Endpoint raíz"""
    return {"servicio": "Gatillador de Descuentos Automáticos", "docs": "/docs"}
