from fastapi import APIRouter, Path, Query
from typing import Optional
from app.models.schemas import ConfiguracionGeneral, ConfiguracionPatch, EstadoLogica

router = APIRouter(tags=["Entregables"])

# Estado en memoria (en producción usar BD o Redis)
configuracion_actual = ConfiguracionGeneral()


@router.get(
    "/config/estado-logica",
    response_model=ConfiguracionGeneral,
    summary="Obtener configuración de umbrales"
)
async def get_configuracion():
    """
    Retorna la configuración actual de todos los estados lógicos con sus umbrales:
    - **estado_logica_activo**: Estado que usa el scheduler (5 AM)
    - **regular, liquidacion_todo_stock, liquidacion_agresiva, liquidacion_suave**: Umbrales por estado
    """
    return configuracion_actual


@router.patch(
    "/config/estado-logica",
    response_model=ConfiguracionGeneral,
    summary="Modificar configuración de umbrales"
)
async def patch_configuracion(updates: ConfiguracionPatch):
    """
    Modifica los umbrales de uno o más estados lógicos. Solo enviar los campos a actualizar.

    Cada estado tiene 3 umbrales configurables:
    - **last_import_age_max**: Días desde último inventario
    - **days_since_last_sale_min**: Días desde última venta
    - **ult_modificacion_descuento**: Días desde última modificación de descuento
    """
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
    responses={
        200: {
            "description": "Proceso ejecutado correctamente",
            "content": {
                "application/json": {
                    "example": {
                        "estado_ejecutado": "liquidacion_todo_stock",
                        "umbrales_usados": {
                            "last_import_age_max": 500,
                            "days_since_last_sale_min": 80,
                            "ult_modificacion_descuento": 80
                        },
                        "productos_evaluados": 50,
                        "productos_modificados": 3,
                        "productos_excluidos": 10,
                        "errores": 0,
                        "detalle_modificados": [
                            {
                                "cod_prod": "IF6463",
                                "descuento_anterior": "Sin descuento",
                                "descuento_nuevo": "PUSH1",
                                "esq_costo_nuevo": None,
                                "categoria_liquidacion_agregada": False,
                                "datos_zap": {
                                    "last_import_age_max": 759.0,
                                    "days_since_last_sale_min": None
                                },
                                "datos_avax": {
                                    "ult_actualizacion_descuento": "2026-02-06",
                                    "dias_desde_modificacion": 90,
                                    "descuentos_automaticos": True
                                }
                            }
                        ],
                        "detalle_errores": []
                    }
                }
            }
        }
    }
)
async def ejecutar_proceso_manual():
    """
    Ejecuta el proceso de descuentos automáticos para todos los productos con **descuentos_automaticos = true**.

    Es el mismo proceso que corre el scheduler a las 5 AM.

    Condiciones para subir descuento:
    - **last_import_age** > umbral configurado
    - **days_since_last_sale** > umbral (si es null, usa last_import_age)
    - **dias_desde_ultima_modificacion** > umbral configurado

    Progresión: Sin descuento → PUSH1 → PUSH2 → LIQUIDACION
    """
    from app.scheduler.jobs import procesar_descuentos_automaticos
    resultado = await procesar_descuentos_automaticos()
    return resultado


@router.post(
    "/procesar/{cod_prod}",
    summary="Procesar un producto individual",
    responses={
        200: {
            "description": "Producto procesado",
            "content": {
                "application/json": {
                    "examples": {
                        "aplicado": {
                            "summary": "Descuento aplicado",
                            "value": {
                                "status": "aplicado",
                                "cod_prod": "IF6463",
                                "estado_usado": "liquidacion_todo_stock",
                                "umbrales_usados": {
                                    "last_import_age_max": 500,
                                    "days_since_last_sale_min": 80,
                                    "ult_modificacion_descuento": 80
                                },
                                "descuento_anterior": "Sin descuento",
                                "descuento_nuevo": "PUSH1",
                                "esq_costo_nuevo": None,
                                "categoria_liquidacion_agregada": False,
                                "datos_zap": {
                                    "last_import_age_max": 759.0,
                                    "days_since_last_sale_min": None
                                },
                                "datos_avax": {
                                    "ult_actualizacion_descuento": "2026-02-06",
                                    "dias_desde_modificacion": 90,
                                    "descuentos_automaticos": True
                                },
                                "mensaje": "Descuento aplicado correctamente"
                            }
                        },
                        "no_apto": {
                            "summary": "No cumple condiciones",
                            "value": {
                                "status": "no_apto",
                                "cod_prod": "IF6463",
                                "estado_usado": "liquidacion_todo_stock",
                                "umbrales_usados": {
                                    "last_import_age_max": 500,
                                    "days_since_last_sale_min": 80,
                                    "ult_modificacion_descuento": 80
                                },
                                "descuento_actual": "Sin descuento",
                                "datos_zap": {
                                    "last_import_age_max": 200.0,
                                    "days_since_last_sale_min": 30
                                },
                                "datos_avax": {
                                    "ult_actualizacion_descuento": None,
                                    "dias_desde_modificacion": None,
                                    "descuentos_automaticos": True
                                },
                                "mensaje": "No cumple condiciones para subir descuento"
                            }
                        },
                        "excluido": {
                            "summary": "Descuentos automáticos desactivados",
                            "value": {
                                "status": "excluido",
                                "cod_prod": "IF6463",
                                "descuentos_automaticos": False,
                                "mensaje": "Producto tiene descuentos_automaticos = false"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def procesar_producto(
    cod_prod: str = Path(description="Código del producto (IF6463)"),
    estado: Optional[EstadoLogica] = Query(
        default=None,
        description="Estado lógico a usar."
    )
):
    """
    Evalúa un producto y aplica descuento si cumple las condiciones.

    - Si **descuentos_automaticos = false** → excluye el producto
    - Consulta datos de **ZAP** (churn) y **AVAX** (producto)
    - Evalúa las 3 condiciones (AND) según los umbrales del estado seleccionado
    - Retorna status: **aplicado**, **no_apto**, **excluido**, **nivel_maximo** o **error**
    """
    from app.services.descuentos import procesar_producto_individual
    try:
        return await procesar_producto_individual(cod_prod, estado)
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}


def get_configuracion_actual() -> ConfiguracionGeneral:
    """Helper para obtener configuración desde otros módulos"""
    return configuracion_actual
