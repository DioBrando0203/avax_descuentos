from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.routes.descuento_auto_routes import get_configuracion_actual
from app.schemas.respuestas_descuento import RespProcesarProductos
from app.services.descuento_auto.descuento_auto import (
    acumular_resultado_lote,
    procesar_producto_con_contexto,
)
from app.services.descuento_auto.descuento_helpers import (
    armar_detalle_error,
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
                detalle = await procesar_producto_con_contexto(
                    cod_prod=cod_prod,
                    producto_zap=producto,
                    estado_activo=estado_activo,
                    config_estado=config_estado,
                )
                acumular_resultado_lote(resultado, detalle, cod_prod)

                if getattr(detalle, "status", None) == "aplicado":
                    cambio_esq = (
                        f" + esq_costo: {detalle.esq_costo_nuevo}"
                        if getattr(detalle, "esq_costo_nuevo", None)
                        else ""
                    )
                    print(
                        f"COD_PROD {cod_prod}: "
                        f"{detalle.descuento_anterior} -> {detalle.descuento_nuevo}"
                        f"{cambio_esq}"
                    )

            except Exception as e:
                resultado.errores += 1
                resultado.detalle_resultados.append(
                    armar_detalle_error(cod_prod=cod_prod, error=str(e))
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
        "GO Descuentos Automaticos - "
        f"Zz {settings.SCHEDULER_HOUR}:{settings.SCHEDULER_MINUTE:02d}"
    )
