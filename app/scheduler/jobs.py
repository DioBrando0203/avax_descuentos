import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.services.zap_client import zap_client
from app.services.avax_client import avax_client
from app.services.descuento_auto import descuentos_service
from app.routes.descuento_auto_routes import get_configuracion_actual
from app.schemas.descuento_auto import EstadoLogica
from app.schemas.respuestas_descuento import RespBatch

settings = get_settings()
scheduler = AsyncIOScheduler()


async def procesar_descuentos_automaticos() -> RespBatch:
    print(f"[{datetime.now()}] Iniciando proceso de descuentos automáticos...")

    resultado = {
        "estado_ejecutado": None,
        "umbrales_usados": {},
        "productos_evaluados": 0,
        "productos_modificados": 0,
        "productos_no_aptos": 0,
        "productos_excluidos": 0,
        "errores": 0,
        "detalle_modificados": [],
        "detalle_errores": []
    }

    try:
        # 1. Obtener datos de churn de ZAP
        productos_churn = await zap_client.get_product_churn()
        resultado["productos_evaluados"] = len(productos_churn)
        print(f"Obtenidos {len(productos_churn)} productos de ZAP")

        # 2. Obtener configuración del estado lógico activo
        configuracion = get_configuracion_actual()
        estado_activo = configuracion.estado_logica_activo

        # Obtener config del estado activo
        config_estado = getattr(configuracion, estado_activo.value)

        # Guardar estado y umbrales en el resultado
        resultado["estado_ejecutado"] = estado_activo.value
        resultado["umbrales_usados"] = {
            "last_import_age_max": config_estado.last_import_age_max,
            "days_since_last_sale_min": config_estado.days_since_last_sale_min,
            "ult_modificacion_descuento": config_estado.ult_modificacion_descuento
        }

        print(f"Estado lógico activo: {estado_activo.value}")
        print(f"Umbrales: last_import_age_max > {config_estado.last_import_age_max}, "
              f"days_since_last_sale_min > {config_estado.days_since_last_sale_min}")

        for producto in productos_churn:
            cod_prod = producto.get("cod_prod") or producto.get("sku")

            if not cod_prod:
                continue

            try:
                # Obtener producto de AVAX para verificar descuentos_automaticos
                producto_avax = await avax_client.get_producto(cod_prod)

                # Verificar si descuentos_automaticos está activo (desde AVAX)
                # Según requerimientos: default false, solo procesar si está explícitamente en True
                if not producto_avax.get("descuentos_automaticos", False):
                    resultado["productos_excluidos"] += 1
                    continue

                # Evaluar producto usando función reutilizable
                evaluacion = descuentos_service.evaluar_producto(
                    producto, producto_avax, config_estado, estado_activo
                )

                # Si no debe actualizar, contar como no apto
                if not evaluacion["debe_actualizar"]:
                    if evaluacion["razon"] == "viola_regla_liquidacion":
                        print(f"COD_PROD {cod_prod}: Saltado - viola regla LIQ_20M/30M con Sin descuento")
                    resultado["productos_no_aptos"] += 1
                    continue

                # Llamar al cliente AVAX (maneja categorías y actualizar_precio automáticamente)
                resultado_avax = await avax_client.actualizar_descuento(
                    cod_prod=cod_prod,
                    nuevo_descuento=evaluacion["nuevo_descuento"],
                    nuevo_esq_costo=evaluacion["nuevo_esq_costo"],
                    producto_actual=producto_avax,  # Reutiliza GET previo
                )
                resultado["productos_modificados"] += 1
                resultado["detalle_modificados"].append({
                    "cod_prod": cod_prod,
                    "descuento_anterior": evaluacion["id_descuento_actual"],
                    "descuento_nuevo": evaluacion["nuevo_descuento"],
                    "esq_costo_nuevo": evaluacion["nuevo_esq_costo"],
                    "categoria_liquidacion_agregada": resultado_avax.get("categoria_liquidacion_agregada", False),
                    "datos_zap": {
                        "last_import_age_max": evaluacion["last_import"],
                        "days_since_last_sale_min": evaluacion["days_since_sale"]
                    },
                    "datos_avax": {
                        "ult_actualizacion_descuento": str(evaluacion["ult_actualizacion"]) if evaluacion["ult_actualizacion"] else None,
                        "dias_desde_modificacion": evaluacion["dias_desde_mod"],
                        "descuentos_automaticos": producto_avax.get("descuentos_automaticos")
                    }
                })

                cambio_esq = f" + esq_costo: {evaluacion['nuevo_esq_costo']}" if evaluacion["nuevo_esq_costo"] else ""
                print(f"COD_PROD {cod_prod}: {evaluacion['id_descuento_actual']} -> {evaluacion['nuevo_descuento']}{cambio_esq}")

                # Timer de 3 segundos entre requests (evitar bloqueo Bsale)
                await asyncio.sleep(settings.REQUEST_DELAY)

            except Exception as e:
                resultado["errores"] += 1
                resultado["detalle_errores"].append({
                    "cod_prod": cod_prod,
                    "error": str(e)
                })
                print(f"Error procesando COD_PROD {cod_prod}: {e}")

        print(f"[{datetime.now()}] Proceso completado.")
        print(f"  - Productos modificados: {resultado['productos_modificados']}")
        print(f"  - Errores: {resultado['errores']}")

    except Exception as e:
        print(f"[{datetime.now()}] Error en proceso: {e}")
        resultado["error_general"] = str(e)

    return RespBatch(**resultado)


def setup_scheduler():
    """Configurar el scheduler con el job de las 5 AM"""
    scheduler.add_job(
        procesar_descuentos_automaticos,
        CronTrigger(hour=settings.SCHEDULER_HOUR, minute=settings.SCHEDULER_MINUTE),
        id="proceso_descuentos",
        name="Proceso de descuentos automáticos",
        replace_existing=True
    )
    print(f"Scheduler configurado - Proceso programado para las {settings.SCHEDULER_HOUR}:{settings.SCHEDULER_MINUTE:02d}")
