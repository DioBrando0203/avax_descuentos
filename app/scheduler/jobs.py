from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.routes.descuento_auto_routes import get_configuracion_actual
from app.schemas.respuestas_descuento import DetalleError, RespExcluido, RespProcesarProductos
from app.services.avax_client import avax_client
from app.services.descuento_auto.descuento_auto import descuentos_service
from app.services.descuento_auto.descuento_helpers import (
    armar_resp_aplicado,
    armar_resp_error_validacion,
    armar_resp_no_apto,
    build_umbrales,
)
from app.services.zap_client import zap_client

settings = get_settings()
scheduler = AsyncIOScheduler()


async def procesar_descuentos_automaticos() -> RespProcesarProductos:
    print(f"[{datetime.now()}] Descuentos Automaticos")

    resultado = RespProcesarProductos()

    try:
        productos_churn = await zap_client.get_product_churn()
        resultado.productos_evaluados = len(productos_churn)
        print(f"Obtenidos {len(productos_churn)} productos de ZAP")

        configuracion = get_configuracion_actual()
        estado_activo = configuracion.estado_logica_activo
        config_estado = getattr(configuracion, estado_activo.value)

        resultado.estado_ejecutado = estado_activo.value
        resultado.umbrales_usados = build_umbrales(config_estado)

        print(f"Estado logico activo: {estado_activo.value}")
        print(
            "Umbrales: "
            f"last_import_age_max > {config_estado.last_import_age_max}, "
            f"days_since_last_sale_min > {config_estado.days_since_last_sale_min}"
        )

        for producto in productos_churn:
            cod_prod = producto.get("cod_prod") or producto.get("sku")
            if not cod_prod:
                continue

            try:
                producto_avax = await avax_client.get_producto(cod_prod)

                if not producto_avax.get("descuentos_automaticos", False):
                    resultado.productos_excluidos += 1
                    resultado.detalle_resultados.append(
                        RespExcluido(
                            cod_prod=cod_prod,
                            descuentos_automaticos=False,
                            mensaje="Producto tiene descuentos_automaticos = false",
                        )
                    )
                    continue

                evaluacion = descuentos_service.evaluar_producto(
                    producto, producto_avax, config_estado, estado_activo
                )

                if not evaluacion["debe_actualizar"]:
                    resultado.productos_no_aptos += 1
                    if evaluacion["razon"] == "viola_regla_liquidacion":
                        detalle = armar_resp_error_validacion(
                            cod_prod,
                            estado_activo,
                            evaluacion,
                            config_estado,
                            producto_avax,
                        )
                    else:
                        detalle = armar_resp_no_apto(
                            cod_prod,
                            estado_activo,
                            evaluacion,
                            config_estado,
                            producto_avax,
                        )
                    resultado.detalle_resultados.append(detalle)
                    continue

                resultado_avax = await avax_client.actualizar_descuento(
                    cod_prod=cod_prod,
                    nuevo_descuento=evaluacion["nuevo_descuento"],
                    nuevo_esq_costo=evaluacion["nuevo_esq_costo"],
                    producto_actual=producto_avax,
                )

                resultado.productos_modificados += 1
                resultado.detalle_resultados.append(
                    armar_resp_aplicado(
                        cod_prod,
                        estado_activo,
                        evaluacion,
                        config_estado,
                        producto_avax,
                        resultado_avax,
                    )
                )

                cambio_esq = (
                    f" + esq_costo: {evaluacion['nuevo_esq_costo']}"
                    if evaluacion["nuevo_esq_costo"]
                    else ""
                )
                print(
                    f"COD_PROD {cod_prod}: "
                    f"{evaluacion['id_descuento_actual']} -> {evaluacion['nuevo_descuento']}"
                    f"{cambio_esq}"
                )

            except Exception as e:
                resultado.errores += 1
                resultado.detalle_resultados.append(
                    DetalleError(cod_prod=cod_prod, error=str(e))
                )
                print(f"Error procesando COD_PROD {cod_prod}: {e}")

        print(f"[{datetime.now()}] Proceso completado.")
        print(f"  - Productos modificados: {resultado.productos_modificados}")
        print(f"  - Errores: {resultado.errores}")

    except Exception as e:
        print(f"[{datetime.now()}] Error en proceso: {e}")
        resultado.error_general = str(e)

    return resultado


def setup_scheduler():
    """Scheduler 5 AM"""
    scheduler.add_job(
        procesar_descuentos_automaticos,
        CronTrigger(hour=settings.SCHEDULER_HOUR, minute=settings.SCHEDULER_MINUTE),
        id="proceso_descuentos",
        name="Proceso de descuentos automaticos",
        replace_existing=True,
    )
    print(
        "Scheduler configurado - "
        f"Zz {settings.SCHEDULER_HOUR}:{settings.SCHEDULER_MINUTE:02d}"
    )
