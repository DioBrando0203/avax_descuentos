from fastapi import APIRouter, Path, Query
from typing import Optional
from app.schemas.descuento_auto import ConfiguracionGeneral, ConfiguracionPatch, EstadoLogica
from app.schemas.respuestas_descuento import (
    RespAplicado,
    RespErrorValidacion,
    RespExcluido,
    RespNoApto,
    RespNoEncontrado,
    RespBatch,
)

router = APIRouter(tags=["Entregables"])

# Estado en memoria (en producción usar BD o Redis)
configuracion_actual = ConfiguracionGeneral()


@router.get(
    "/config/estado-logica",
    response_model=ConfiguracionGeneral,
    summary="Obtener configuración de umbrales"
)
async def get_configuracion():
    return configuracion_actual


@router.patch(
    "/config/estado-logica",
    response_model=ConfiguracionGeneral,
    summary="Modificar configuración de umbrales"
)
async def patch_configuracion(updates: ConfiguracionPatch):
    global configuracion_actual

    if updates.estado_logica_activo is not None:
        configuracion_actual.estado_logica_activo = updates.estado_logica_activo

    if updates.regular is not None:
        configuracion_actual.regular = updates.regular

    if updates.liquidacion_todo_stock is not None:
        configuracion_actual.liquidacion_todo_stock = updates.liquidacion_todo_stock

    if updates.liquidacion_agresiva is not None:
        configuracion_actual.liquidacion_agresiva = updates.liquidacion_agresiva

    if updates.liquidacion_suave is not None:
        configuracion_actual.liquidacion_suave = updates.liquidacion_suave

    return configuracion_actual


@router.post(
    "/ejecutar-proceso",
    summary="Ejecutar proceso batch manualmente",
    response_model=RespBatch,
)
async def ejecutar_proceso_manual():
    from app.scheduler.jobs import procesar_descuentos_automaticos
    resultado = await procesar_descuentos_automaticos()
    return resultado


@router.post(
    "/procesar/{cod_prod}",
    summary="Procesar un producto individual",
    response_model=RespAplicado | RespNoApto | RespErrorValidacion | RespExcluido | RespNoEncontrado,
)
async def procesar_producto(
    cod_prod: str = Path(description="Código del producto (IF6463)"),
    estado: Optional[EstadoLogica] = Query(
        default=None,
        description="Estado lógico a usar."
    )
):

    from app.services.descuento_auto import procesar_producto as procesar_producto_service
    try:
        return await procesar_producto_service(cod_prod, estado)
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}


def get_configuracion_actual() -> ConfiguracionGeneral:
    """Helper para obtener configuración desde otros módulos"""
    return configuracion_actual
