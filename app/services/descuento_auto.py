from app.schemas.descuento_auto import ConfigEstadoLogica, EstadoLogica
from app.schemas.respuestas_descuento import (
    DatosAvax,
    DatosZap,
    RespAplicado,
    RespErrorValidacion,
    RespExcluido,
    RespNoApto,
    RespNoEncontrado,
    Umbrales,
)
from datetime import date, datetime


class DescuentosService:
    NIVELES_DESCUENTO = ["Sin descuento", "PUSH1", "PUSH2", "LIQUIDACION"]

    # Mapeo de esq_costo actual → esq_costo en LIQUIDACION
    MAPEO_ESQ_COSTO_LIQUIDACION = {
        # LIQ_20M 
        "DA_35R_T0": "LIQ_20M",
        "DA_35R_T1": "LIQ_20M",
        "DA_35R_T2": "LIQ_20M",
        "NDA_15M_PRM": "LIQ_20M",
        "NDA_15M_T1": "LIQ_20M",
        "NDA_17_5M_T1": "LIQ_20M",
        "NDA_20M_PRM": "LIQ_20M",
        "NDA_20M_T1": "LIQ_20M",
        "NDA_25M_PRM": "LIQ_20M",
        # LIQ_30M 
        "NDA_25M_T1": "LIQ_30M",
        "NDA_30M_PRM": "LIQ_30M",
        "NDA_30M_T1": "LIQ_30M",
        "NDA_35M_PRM": "LIQ_30M",
        "NDA_35M_T1": "LIQ_30M",
        "NDA_40M_T1": "LIQ_30M",
    }

    @staticmethod
    def obtener_siguiente_nivel(nivel_actual: str) -> str:
        niveles = DescuentosService.NIVELES_DESCUENTO

        if nivel_actual not in niveles:
            return nivel_actual

        idx = niveles.index(nivel_actual)
        
        # Si está en LIQUIDACION (último nivel), volver a PUSH1
        if idx == len(niveles) - 1:
            return "PUSH1"
        
        # Caso normal: avanzar al siguiente nivel
        if idx < len(niveles) - 1:
            return niveles[idx + 1]
        
        return nivel_actual

    @staticmethod
    def debe_subir_descuento_last_import(
        producto: dict,
        config: ConfigEstadoLogica,
        ult_actualizacion_descuento: date = None
    ) -> bool:
        last_import_age = producto.get("last_import_age_max", 0) or 0
        
        # Solo verificar last_import_age_max
        cumple_import_age = last_import_age > config.last_import_age_max

        return cumple_import_age

    @staticmethod
    def debe_subir_descuento_normal(
        producto: dict,
        config: ConfigEstadoLogica,
        ult_actualizacion_descuento: date = None
    ) -> bool: 
        days_since_sale = producto.get("days_since_last_sale_min")
        last_import_age = producto.get("last_import_age_max", 0) or 0
        
        # Si days_since_last_sale_min es null o 0, usar last_import_age_max
        if days_since_sale is None or days_since_sale == 0:
            days_since_sale = last_import_age

        # Calcular días desde última modificación de descuento
        if ult_actualizacion_descuento:
            dias_desde_modificacion = (date.today() - ult_actualizacion_descuento).days
        else:
            # Si nunca se modificó, consideramos que cumple la condición
            dias_desde_modificacion = float('inf')

        # Verificar condiciones (deben cumplirse AMBAS)
        cumple_days_sale = days_since_sale > config.days_since_last_sale_min
        cumple_dias_modificacion = dias_desde_modificacion > config.ult_modificacion_descuento

        return cumple_days_sale and cumple_dias_modificacion

    @staticmethod
    def validar_regla_liquidacion(id_esq_costo: str, id_descuento: str) -> bool:
        if id_esq_costo in ["LIQ_20M", "LIQ_30M"]:
            if id_descuento == "Sin descuento":
                return False
        return True

    @staticmethod
    def determinar_nuevo_esq_costo(
        id_esq_costo_actual: str,
        nuevo_descuento: str,
        estado_logica: EstadoLogica,
        cumple_last_import: bool
    ) -> str:
        # RUTA 2: NO cumple last_import → id_esq_costo NO CAMBIA
        if not cumple_last_import:
            return None
            
        # RUTA 1: Cumple last_import → DEBE cambiar a LIQ
        # Si ya está en LIQ_20M o LIQ_30M, mantenerlo
        if id_esq_costo_actual in ["LIQ_20M", "LIQ_30M"]:
            return None
            
        # Buscar en el mapeo
        nuevo_esq = DescuentosService.MAPEO_ESQ_COSTO_LIQUIDACION.get(id_esq_costo_actual)
        if nuevo_esq:
            return nuevo_esq
            
        # Si no está en el mapeo, usar LIQ_20M por defecto
        return "LIQ_20M"

    @staticmethod
    def obtener_descuento_minimo(estado_logica: EstadoLogica) -> str:
        if estado_logica == EstadoLogica.LIQUIDACION_TODO_STOCK:
            return "PUSH1"
        return "Sin descuento"

    @staticmethod
    def parse_fecha_modificacion(fecha_str) -> date:
        if not fecha_str:
            return None

        # Si ya es un objeto date, devolverlo
        if isinstance(fecha_str, date) and not isinstance(fecha_str, datetime):
            return fecha_str

        # Si es datetime, extraer date
        if isinstance(fecha_str, datetime):
            return fecha_str.date()

        # Si es string, intentar parsear
        if isinstance(fecha_str, str):
            # Intentar formato HTTP date: "Wed, 04 Feb 2026 00:00:00 GMT"
            try:
                return datetime.strptime(fecha_str, "%a, %d %b %Y %H:%M:%S %Z").date()
            except (ValueError, TypeError):
                pass

            # Intentar formato ISO date: "2026-02-04" o "2026-02-04T00:00:00"
            try:
                return date.fromisoformat(fecha_str[:10])
            except (ValueError, TypeError):
                pass

        return None

    @staticmethod
    def calcular_dias_desde_modificacion(ult_actualizacion: date) -> int:
        if not ult_actualizacion:
            return None
        return (date.today() - ult_actualizacion).days

    @staticmethod
    def formatear_days_since_sale(days_since_sale) -> str:
        if days_since_sale is None or days_since_sale == 0:
            return "No hubo ventas de producto"
        return str(days_since_sale)

    @staticmethod
    def evaluar_producto(
        producto_zap: dict,
        producto_avax: dict,
        config_estado: ConfigEstadoLogica,
        estado_logica: EstadoLogica
    ) -> dict:
        id_descuento_actual = producto_avax.get("id_descuento", "Sin descuento")
        id_esq_costo_actual = producto_avax.get("id_esq_costo", "")

        # Parsear fecha de modificación
        ult_actualizacion_str = producto_avax.get("ult_actualizacion_descuento_automatico")
        ult_actualizacion = DescuentosService.parse_fecha_modificacion(ult_actualizacion_str)
        dias_desde_mod = DescuentosService.calcular_dias_desde_modificacion(ult_actualizacion)

        # Datos para el response
        last_import = producto_zap.get("last_import_age_max") or 0
        days_since_sale = producto_zap.get("days_since_last_sale_min")
        days_since_sale_display = DescuentosService.formatear_days_since_sale(days_since_sale)

        resultado = {
            "debe_actualizar": False,
            "nuevo_descuento": None,
            "nuevo_esq_costo": None,
            "id_descuento_actual": id_descuento_actual,
            "id_esq_costo_actual": id_esq_costo_actual,
            "ult_actualizacion": ult_actualizacion,
            "dias_desde_mod": dias_desde_mod,
            "last_import": last_import,
            "days_since_sale": days_since_sale_display,
            "razon": None,
            "ruta_usada": None
        }

        # Evaluar RUTA 1: last_import_age_max
        cumple_ruta1 = DescuentosService.debe_subir_descuento_last_import(
            producto_zap, config_estado, ult_actualizacion
        )
        
        # Evaluar RUTA 2: days_since_last_sale + ult_modificacion
        cumple_ruta2 = DescuentosService.debe_subir_descuento_normal(
            producto_zap, config_estado, ult_actualizacion
        )

        # Determinar qué ruta usar (prioridad a RUTA 1)
        if not cumple_ruta1 and not cumple_ruta2:
            resultado["razon"] = "no_cumple_condiciones"
            resultado["ruta_usada"] = "ninguna"
            return resultado

        # Usar RUTA 1 si cumple, sino RUTA 2
        ruta_usada = "ruta1_last_import" if cumple_ruta1 else "ruta2_normal"
        resultado["ruta_usada"] = ruta_usada

        # Calcular nuevo descuento (con rotación: LIQUIDACION → PUSH1)
        nuevo_descuento = DescuentosService.obtener_siguiente_nivel(id_descuento_actual)

        # En liquidacion_todo_stock, mínimo PUSH1
        descuento_minimo = DescuentosService.obtener_descuento_minimo(estado_logica)
        if id_descuento_actual == "Sin descuento" and descuento_minimo == "PUSH1":
            nuevo_descuento = "PUSH1"

        # Determinar nuevo esq_costo según la ruta
        nuevo_esq_costo = DescuentosService.determinar_nuevo_esq_costo(
            id_esq_costo_actual, nuevo_descuento, estado_logica, cumple_ruta1
        )

        # Validar regla de liquidación
        esq_costo_final = nuevo_esq_costo or id_esq_costo_actual
        if not DescuentosService.validar_regla_liquidacion(esq_costo_final, nuevo_descuento):
            resultado["razon"] = "viola_regla_liquidacion"
            return resultado

        # Debe actualizar
        resultado["debe_actualizar"] = True
        resultado["nuevo_descuento"] = nuevo_descuento
        resultado["nuevo_esq_costo"] = nuevo_esq_costo
        return resultado


descuentos_service = DescuentosService()


async def procesar_producto(cod_prod: str, estado_override: EstadoLogica = None):

    from app.services.zap_client import zap_client
    from app.services.avax_client import avax_client
    from app.routes.descuento_auto_routes import get_configuracion_actual

    # 1. Obtener configuración
    configuracion = get_configuracion_actual()
    estado_activo = estado_override or configuracion.estado_logica_activo
    config_estado = getattr(configuracion, estado_activo.value)

    # 2. Buscar producto en ZAP
    productos_churn = await zap_client.get_product_churn()
    producto_zap = next(
        (p for p in productos_churn if p.get("sku") == cod_prod),
        None
    )

    if not producto_zap:
        return RespNoEncontrado(
            cod_prod=cod_prod,
            mensaje="Producto no encontrado en ZAP (churn)",
        )

    # 3. Obtener producto de AVAX
    producto_avax = await avax_client.get_producto(cod_prod)

    # 3.1 Verificar si descuentos_automaticos está activo
    if not producto_avax.get("descuentos_automaticos", False):
        return RespExcluido(
            cod_prod=cod_prod,
            descuentos_automaticos=False,
            mensaje="Producto tiene descuentos_automaticos = false",
        )

    # 4. Evaluar producto usando función reutilizable
    evaluacion = descuentos_service.evaluar_producto(
        producto_zap, producto_avax, config_estado, estado_activo
    )

    # 5. Manejar resultado según la razón
    if evaluacion["razon"] == "no_cumple_condiciones":
        return RespNoApto(
            cod_prod=cod_prod,
            estado_usado=estado_activo.value,
            ruta_evaluada=evaluacion["ruta_usada"],
            umbrales_usados=Umbrales(
                last_import_age_max=config_estado.last_import_age_max,
                days_since_last_sale_min=config_estado.days_since_last_sale_min,
                ult_modificacion_descuento=config_estado.ult_modificacion_descuento,
            ),
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

    if evaluacion["razon"] == "viola_regla_liquidacion":
        return RespErrorValidacion(
            cod_prod=cod_prod,
            estado_usado=estado_activo.value,
            ruta_evaluada=evaluacion["ruta_usada"],
            umbrales_usados=Umbrales(
                last_import_age_max=config_estado.last_import_age_max,
                days_since_last_sale_min=config_estado.days_since_last_sale_min,
                ult_modificacion_descuento=config_estado.ult_modificacion_descuento,
            ),
            descuento_actual=evaluacion["id_descuento_actual"],
            esq_costo_actual=evaluacion["id_esq_costo_actual"],
            datos_avax=DatosAvax(
                descuentos_automaticos=producto_avax.get("descuentos_automaticos"),
            ),
            mensaje="Viola regla: LIQ_20M/30M no puede tener Sin descuento",
        )

    # 6. Aplicar descuento
    resultado_avax = await avax_client.actualizar_descuento(
        cod_prod=cod_prod,
        nuevo_descuento=evaluacion["nuevo_descuento"],
        nuevo_esq_costo=evaluacion["nuevo_esq_costo"],
        producto_actual=producto_avax,  # Evita segundo GET
    )

    return RespAplicado(
        cod_prod=cod_prod,
        estado_usado=estado_activo.value,
        ruta_usada=evaluacion["ruta_usada"],
        umbrales_usados=Umbrales(
            last_import_age_max=config_estado.last_import_age_max,
            days_since_last_sale_min=config_estado.days_since_last_sale_min,
            ult_modificacion_descuento=config_estado.ult_modificacion_descuento,
        ),
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
        ),
        mensaje="Descuento aplicado correctamente",
    )
