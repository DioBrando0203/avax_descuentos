from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.routes.descuento_auto_routes import router as descuento_router
from app.scheduler.jobs import scheduler, setup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejo del ciclo de vida de la aplicación"""
    setup_scheduler()
    scheduler.start()
    print("Aplicación iniciada - Scheduler corriendo")
    yield
    scheduler.shutdown()
    print("Aplicación cerrada - Scheduler detenido")


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
