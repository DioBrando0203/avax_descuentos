import httpx
from typing import Optional

from app.schemas.descuento_auto import ConfigEstadoLogica, EstadoLogica
from app.schemas.respuestas_descuento import RespProcesarProductos
from .descuento_helpers import (
    armar_resp_aplicado,
    armar_detalle_error,
    armar_resp_error_validacion,
    armar_resp_excluido,
    armar_resp_no_encontrado,
    armar_resp_no_apto,
    build_umbrales,
    buscar_en_zap,
    cargar_producto_avax,
    obtener_config_estado,
)
from .descuento_logic import DescuentosService

descuentos_service = DescuentosService()


def acumular_resultado_lote(
    resultado: RespProcesarProductos,
    detalle,
    cod_prod: str,
) -> None:
    status = getattr(detalle, "status", None)

    if status == "aplicado":
        resultado.productos_modificados += 1
        resultado.detalle_resultados.append(detalle)
        return

    if status in {"no_apto", "error_validacion"}:
        resultado.productos_no_aptos += 1
        resultado.detalle_resultados.append(detalle)
        return

    if status == "excluido":
        resultado.productos_excluidos += 1
        resultado.detalle_resultados.append(detalle)
        return

    if status == "no_encontrado":
        resultado.productos_no_encontrados += 1
        resultado.detalle_resultados.append(detalle)
        return

    resultado.errores += 1
    resultado.detalle_resultados.append(
        armar_detalle_error(
            cod_prod=cod_prod,
            error=f"Estado de respuesta no reconocido: {status}",
        )
    )

# Evalua reglas y devuelve la respuesta final }
async def procesar_producto_con_contexto(
    cod_prod: str,
    producto_zap: Optional[dict],
    estado_activo: EstadoLogica,
    config_estado: ConfigEstadoLogica,
):
    from app.services.avax_client import avax_client

    if not producto_zap:
        return armar_resp_no_encontrado(
            cod_prod=cod_prod,
        )

    producto_avax = await cargar_producto_avax(cod_prod)
    if not producto_avax.get("descuentos_automaticos", False):
        return armar_resp_excluido(
            cod_prod=cod_prod,
            descuentos_automaticos=False,
        )

    evaluacion = descuentos_service.evaluar_producto(
        producto_zap, producto_avax, config_estado, estado_activo
    )

    if evaluacion["razon"] == "no_cumple_condiciones":
        return armar_resp_no_apto(
            cod_prod, estado_activo, evaluacion, config_estado, producto_avax
        )

    if evaluacion["razon"] == "viola_regla_liquidacion":
        return armar_resp_error_validacion(
            cod_prod, estado_activo, evaluacion, config_estado, producto_avax
        )

    resultado_avax = await avax_client.actualizar_descuento(
        cod_prod=cod_prod,
        nuevo_descuento=evaluacion["nuevo_descuento"],
        nuevo_esq_costo=evaluacion["nuevo_esq_costo"],
        producto_actual=producto_avax,
    )

    return armar_resp_aplicado(
        cod_prod,
        estado_activo,
        evaluacion,
        config_estado,
        producto_avax,
        resultado_avax,
    )


async def procesar_productos(
    productos: list[str],
    estado_override: EstadoLogica = None,
) -> RespProcesarProductos:
    codigos = [cod_prod.strip() for cod_prod in productos if cod_prod and cod_prod.strip()]
    if not codigos:
        raise ValueError("Debes enviar al menos un cod_prod valido en 'productos'.")

    from app.services.zap_client import zap_client

    productos_churn = await zap_client.get_product_churn()
    churn_por_sku = {
        p.get("sku"): p
        for p in productos_churn
        if p.get("sku")
    }

    estado_activo, config_estado = await obtener_config_estado(estado_override)
    resultado = RespProcesarProductos(
        estado_ejecutado=estado_activo.value,
        umbrales_usados=build_umbrales(config_estado),
    )

    for cod_prod in codigos:
        resultado.productos_evaluados += 1

        try:
            detalle = await procesar_producto_con_contexto(
                cod_prod=cod_prod,
                producto_zap=churn_por_sku.get(cod_prod),
                estado_activo=estado_activo,
                config_estado=config_estado,
            )
            acumular_resultado_lote(resultado, detalle, cod_prod)
        except httpx.HTTPStatusError as e:
            resultado.errores += 1
            resultado.detalle_resultados.append(
                armar_detalle_error(
                    cod_prod=cod_prod,
                    error=f"AVAX devolvio {e.response.status_code}: {e.response.text}",
                )
            )
        except httpx.RequestError as e:
            resultado.errores += 1
            resultado.detalle_resultados.append(
                armar_detalle_error(
                    cod_prod=cod_prod,
                    error=f"No se pudo conectar con AVAX: {str(e)}",
                )
            )
        except Exception as e:
            resultado.errores += 1
            resultado.detalle_resultados.append(
                armar_detalle_error(
                    cod_prod=cod_prod,
                    error=f"Error procesando producto {cod_prod}: {str(e)}",
                )
            )

    return resultado


async def procesar_producto(cod_prod: str, estado_override: EstadoLogica = None):
    estado_activo, config_estado = await obtener_config_estado(estado_override)
    producto_zap = await buscar_en_zap(cod_prod)
    return await procesar_producto_con_contexto(
        cod_prod=cod_prod,
        producto_zap=producto_zap,
        estado_activo=estado_activo,
        config_estado=config_estado,
    )
