from app.schemas.descuento_auto import ConfigEstadoLogica, EstadoLogica
from app.schemas.respuestas_descuento import (
    DatosAvax,
    DatosZap,
    RespAplicado,
    RespErrorValidacion,
    RespNoApto,
    Umbrales,
)


def build_umbrales(config_estado: ConfigEstadoLogica) -> Umbrales:
    return Umbrales(
        last_import_age_max=config_estado.last_import_age_max,
        days_since_last_sale_min=config_estado.days_since_last_sale_min,
        ult_modificacion_descuento=config_estado.ult_modificacion_descuento,
    )


def armar_resp_no_apto(
    cod_prod: str,
    estado_activo: EstadoLogica,
    evaluacion: dict,
    config_estado: ConfigEstadoLogica,
    producto_avax: dict,
) -> RespNoApto:
    return RespNoApto(
        cod_prod=cod_prod,
        estado_usado=estado_activo.value,
        ruta_evaluada=evaluacion["ruta_usada"],
        umbrales_usados=build_umbrales(config_estado),
        descuento_actual=evaluacion["id_descuento_actual"],
        datos_zap=DatosZap(
            last_import_age_max=evaluacion["last_import"],
            days_since_last_sale_min=evaluacion["days_since_sale"],
        ),
        datos_avax=DatosAvax(
            ult_actualizacion_descuento=str(evaluacion["ult_actualizacion"])
            if evaluacion["ult_actualizacion"]
            else None,
            dias_desde_modificacion=evaluacion["dias_desde_mod"],
            descuentos_automaticos=producto_avax.get("descuentos_automaticos"),
        ),
        mensaje="No cumple condiciones para subir descuento",
    )


def armar_resp_error_validacion(
    cod_prod: str,
    estado_activo: EstadoLogica,
    evaluacion: dict,
    config_estado: ConfigEstadoLogica,
    producto_avax: dict,
) -> RespErrorValidacion:
    return RespErrorValidacion(
        cod_prod=cod_prod,
        estado_usado=estado_activo.value,
        ruta_evaluada=evaluacion["ruta_usada"],
        umbrales_usados=build_umbrales(config_estado),
        descuento_actual=evaluacion["id_descuento_actual"],
        esq_costo_actual=evaluacion["id_esq_costo_actual"],
        datos_avax=DatosAvax(
            descuentos_automaticos=producto_avax.get("descuentos_automaticos"),
        ),
        mensaje="Viola regla: LIQ_20M/30M no puede tener Sin descuento",
    )


def armar_resp_aplicado(
    cod_prod: str,
    estado_activo: EstadoLogica,
    evaluacion: dict,
    config_estado: ConfigEstadoLogica,
    producto_avax: dict,
    resultado_avax: dict,
) -> RespAplicado:
    return RespAplicado(
        cod_prod=cod_prod,
        estado_usado=estado_activo.value,
        ruta_usada=evaluacion["ruta_usada"],
        umbrales_usados=build_umbrales(config_estado),
        descuento_anterior=evaluacion["id_descuento_actual"],
        descuento_nuevo=evaluacion["nuevo_descuento"],
        esq_costo_nuevo=evaluacion["nuevo_esq_costo"],
        categoria_liquidacion_agregada=resultado_avax.get(
            "categoria_liquidacion_agregada", False
        ),
        datos_zap=DatosZap(
            last_import_age_max=evaluacion["last_import"],
            days_since_last_sale_min=evaluacion["days_since_sale"],
        ),
        datos_avax=DatosAvax(
            ult_actualizacion_descuento=str(evaluacion["ult_actualizacion"])
            if evaluacion["ult_actualizacion"]
            else None,
            dias_desde_modificacion=evaluacion["dias_desde_mod"],
            descuentos_automaticos=producto_avax.get("descuentos_automaticos"),
            esq_costo_actual=evaluacion["id_esq_costo_actual"],
        ),
        mensaje="Descuento aplicado correctamente",
    )


async def obtener_config_estado(estado_override: EstadoLogica):
    from app.routes.descuento_auto_routes import get_configuracion_actual

    configuracion = get_configuracion_actual()
    estado_activo = estado_override or configuracion.estado_logica_activo
    config_estado = getattr(configuracion, estado_activo.value)
    return estado_activo, config_estado


async def buscar_en_zap(cod_prod: str):
    from app.services.zap_client import zap_client

    productos_churn = await zap_client.get_product_churn()
    return next((p for p in productos_churn if p.get("sku") == cod_prod), None)


async def cargar_producto_avax(cod_prod: str):
    from app.services.avax_client import avax_client

    return await avax_client.get_producto(cod_prod)
