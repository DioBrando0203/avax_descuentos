from app.models.schemas import ConfigEstadoLogica, EstadoLogica
from datetime import date, datetime


class DescuentosService:
    """Lógica de negocio para descuentos automáticos"""

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
        """Obtener el siguiente nivel de descuento"""
        niveles = DescuentosService.NIVELES_DESCUENTO

        if nivel_actual not in niveles:
            return nivel_actual

        idx = niveles.index(nivel_actual)
        if idx < len(niveles) - 1:
            return niveles[idx + 1]
        return nivel_actual

    @staticmethod
    def debe_subir_descuento(
        producto: dict,
        config: ConfigEstadoLogica,
        ult_actualizacion_descuento: date = None
    ) -> bool:
        """
        Determinar si un producto debe subir de nivel de descuento.

        Según requerimientos (deben cumplirse TODAS):
        - last_import_age_max > threshold
        - days_since_last_sale_min > threshold
        - días desde ult_actualizacion_descuento > threshold
        """
        last_import_age = producto.get("last_import_age_max", 0) or 0
        days_since_sale = producto.get("days_since_last_sale_min")

        # Si days_since_last_sale_min es null, usar last_import_age_max
        if days_since_sale is None:
            days_since_sale = last_import_age

        # Calcular días desde última modificación de descuento
        if ult_actualizacion_descuento:
            dias_desde_modificacion = (date.today() - ult_actualizacion_descuento).days
        else:
            # Si nunca se modificó, consideramos que cumple la condición
            dias_desde_modificacion = float('inf')

        # Verificar condiciones (deben cumplirse TODAS)
        cumple_import_age = last_import_age > config.last_import_age_max
        cumple_days_sale = days_since_sale > config.days_since_last_sale_min
        cumple_dias_modificacion = dias_desde_modificacion > config.ult_modificacion_descuento

        return cumple_import_age and cumple_days_sale and cumple_dias_modificacion

    @staticmethod
    def validar_regla_liquidacion(id_esq_costo: str, id_descuento: str) -> bool:
        """
        Validar regla: NUNCA debe haber LIQ_20M/30M con id_descuento = 'Sin descuento'
        Retorna True si es válido, False si viola la regla
        """
        if id_esq_costo in ["LIQ_20M", "LIQ_30M"]:
            if id_descuento == "Sin descuento":
                return False
        return True

    @staticmethod
    def determinar_nuevo_esq_costo(
        id_esq_costo_actual: str,
        nuevo_descuento: str,
        estado_logica: EstadoLogica
    ) -> str:
        """
        Determina si se debe cambiar el id_esq_costo.

        Si el producto va a LIQUIDACION y estamos en estado liquidacion_todo_stock
        o liquidacion_agresiva, usar el mapeo según el esq_costo actual.
        """
        if nuevo_descuento == "LIQUIDACION":
            if estado_logica in [EstadoLogica.LIQUIDACION_TODO_STOCK, EstadoLogica.LIQUIDACION_AGRESIVA]:
                # Si ya está en LIQ_20M o LIQ_30M, no cambiar
                if id_esq_costo_actual in ["LIQ_20M", "LIQ_30M"]:
                    return None
                # Buscar en el mapeo
                nuevo_esq = DescuentosService.MAPEO_ESQ_COSTO_LIQUIDACION.get(id_esq_costo_actual)
                if nuevo_esq:
                    return nuevo_esq
                # Si no está en el mapeo, usar LIQ_20M por defecto
                return "LIQ_20M"
        return None

    @staticmethod
    def obtener_descuento_minimo(estado_logica: EstadoLogica) -> str:
        """
        Obtiene el descuento mínimo según el estado_logica.
        liquidacion_todo_stock: PUSH1 mínimo
        otros: Sin descuento
        """
        if estado_logica == EstadoLogica.LIQUIDACION_TODO_STOCK:
            return "PUSH1"
        return "Sin descuento"

    @staticmethod
    def parse_fecha_modificacion(fecha_str) -> date:
        """Parsea la fecha de última modificación desde string/date a date"""
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
        """Calcula días desde la última modificación"""
        if not ult_actualizacion:
            return None
        return (date.today() - ult_actualizacion).days

    @staticmethod
    def evaluar_producto(
        producto_zap: dict,
        producto_avax: dict,
        config_estado: ConfigEstadoLogica,
        estado_logica: EstadoLogica
    ) -> dict:
        """
        Evalúa un producto y retorna el resultado con la acción a tomar.

        Returns:
            dict con keys: debe_actualizar, nuevo_descuento, nuevo_esq_costo,
                          id_descuento_actual, id_esq_costo_actual, razon
        """
        id_descuento_actual = producto_avax.get("id_descuento", "Sin descuento")
        id_esq_costo_actual = producto_avax.get("id_esq_costo", "")

        # Parsear fecha de modificación
        ult_actualizacion_str = producto_avax.get("ult_actualizacion_descuento_automatico")
        ult_actualizacion = DescuentosService.parse_fecha_modificacion(ult_actualizacion_str)
        dias_desde_mod = DescuentosService.calcular_dias_desde_modificacion(ult_actualizacion)

        # Datos para el response
        last_import = producto_zap.get("last_import_age_max") or 0
        days_since_sale = producto_zap.get("days_since_last_sale_min")  # Puede ser null

        resultado = {
            "debe_actualizar": False,
            "nuevo_descuento": None,
            "nuevo_esq_costo": None,
            "id_descuento_actual": id_descuento_actual,
            "id_esq_costo_actual": id_esq_costo_actual,
            "ult_actualizacion": ult_actualizacion,
            "dias_desde_mod": dias_desde_mod,
            "last_import": last_import,
            "days_since_sale": days_since_sale,
            "razon": None
        }

        # Verificar si cumple condiciones
        if not DescuentosService.debe_subir_descuento(producto_zap, config_estado, ult_actualizacion):
            resultado["razon"] = "no_cumple_condiciones"
            return resultado

        # Calcular nuevo descuento
        nuevo_descuento = DescuentosService.obtener_siguiente_nivel(id_descuento_actual)

        # En liquidacion_todo_stock, mínimo PUSH1
        descuento_minimo = DescuentosService.obtener_descuento_minimo(estado_logica)
        if id_descuento_actual == "Sin descuento" and descuento_minimo == "PUSH1":
            nuevo_descuento = "PUSH1"

        # Si ya está en nivel máximo
        if nuevo_descuento == id_descuento_actual:
            resultado["razon"] = "nivel_maximo"
            return resultado

        # Determinar nuevo esq_costo
        nuevo_esq_costo = DescuentosService.determinar_nuevo_esq_costo(
            id_esq_costo_actual, nuevo_descuento, estado_logica
        )

        # Validar regla de liquidación
        esq_costo_final = nuevo_esq_costo or id_esq_costo_actual
        if not DescuentosService.validar_regla_liquidacion(esq_costo_final, nuevo_descuento):
            resultado["razon"] = "viola_regla_liquidacion"
            return resultado

        # Todo OK - debe actualizar
        resultado["debe_actualizar"] = True
        resultado["nuevo_descuento"] = nuevo_descuento
        resultado["nuevo_esq_costo"] = nuevo_esq_costo
        return resultado


descuentos_service = DescuentosService()


async def procesar_producto_individual(cod_prod: str, estado_override: EstadoLogica = None) -> dict:
    """
    Procesa UN producto: evalúa si es apto y aplica el descuento correspondiente.

    Args:
        cod_prod: Código del producto
        estado_override: Estado lógico a usar (si no se especifica, usa el activo)
    """
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
        return {
            "status": "no_encontrado",
            "cod_prod": cod_prod,
            "mensaje": "Producto no encontrado en ZAP (churn)"
        }

    # 3. Obtener producto de AVAX
    producto_avax = await avax_client.get_producto(cod_prod)

    # 3.1 Verificar si descuentos_automaticos está activo
    if not producto_avax.get("descuentos_automaticos", False):
        return {
            "status": "excluido",
            "cod_prod": cod_prod,
            "descuentos_automaticos": False,
            "mensaje": "Producto tiene descuentos_automaticos = false"
        }

    # 4. Evaluar producto usando función reutilizable
    evaluacion = descuentos_service.evaluar_producto(
        producto_zap, producto_avax, config_estado, estado_activo
    )

    # 5. Manejar resultado según la razón
    if evaluacion["razon"] == "no_cumple_condiciones":
        return {
            "status": "no_apto",
            "cod_prod": cod_prod,
            "estado_usado": estado_activo.value,
            "umbrales_usados": {
                "last_import_age_max": config_estado.last_import_age_max,
                "days_since_last_sale_min": config_estado.days_since_last_sale_min,
                "ult_modificacion_descuento": config_estado.ult_modificacion_descuento
            },
            "descuento_actual": evaluacion["id_descuento_actual"],
            "datos_zap": {
                "last_import_age_max": evaluacion["last_import"],
                "days_since_last_sale_min": evaluacion["days_since_sale"]
            },
            "datos_avax": {
                "ult_actualizacion_descuento": str(evaluacion["ult_actualizacion"]) if evaluacion["ult_actualizacion"] else None,
                "dias_desde_modificacion": evaluacion["dias_desde_mod"],
                "descuentos_automaticos": producto_avax.get("descuentos_automaticos")
            },
            "mensaje": "No cumple condiciones para subir descuento"
        }

    if evaluacion["razon"] == "nivel_maximo":
        return {
            "status": "nivel_maximo",
            "cod_prod": cod_prod,
            "estado_usado": estado_activo.value,
            "umbrales_usados": {
                "last_import_age_max": config_estado.last_import_age_max,
                "days_since_last_sale_min": config_estado.days_since_last_sale_min,
                "ult_modificacion_descuento": config_estado.ult_modificacion_descuento
            },
            "descuento_actual": evaluacion["id_descuento_actual"],
            "datos_zap": {
                "last_import_age_max": evaluacion["last_import"],
                "days_since_last_sale_min": evaluacion["days_since_sale"]
            },
            "datos_avax": {
                "ult_actualizacion_descuento": str(evaluacion["ult_actualizacion"]) if evaluacion["ult_actualizacion"] else None,
                "dias_desde_modificacion": evaluacion["dias_desde_mod"],
                "descuentos_automaticos": producto_avax.get("descuentos_automaticos")
            },
            "mensaje": "Producto ya está en nivel máximo (LIQUIDACION)"
        }

    if evaluacion["razon"] == "viola_regla_liquidacion":
        return {
            "status": "error_validacion",
            "cod_prod": cod_prod,
            "estado_usado": estado_activo.value,
            "umbrales_usados": {
                "last_import_age_max": config_estado.last_import_age_max,
                "days_since_last_sale_min": config_estado.days_since_last_sale_min,
                "ult_modificacion_descuento": config_estado.ult_modificacion_descuento
            },
            "descuento_actual": evaluacion["id_descuento_actual"],
            "esq_costo_actual": evaluacion["id_esq_costo_actual"],
            "datos_avax": {
                "descuentos_automaticos": producto_avax.get("descuentos_automaticos")
            },
            "mensaje": "Viola regla: LIQ_20M/30M no puede tener Sin descuento"
        }

    # 6. Aplicar descuento
    resultado_avax = await avax_client.actualizar_descuento(
        cod_prod=cod_prod,
        nuevo_descuento=evaluacion["nuevo_descuento"],
        nuevo_esq_costo=evaluacion["nuevo_esq_costo"]
    )

    return {
        "status": "aplicado",
        "cod_prod": cod_prod,
        "estado_usado": estado_activo.value,
        "umbrales_usados": {
            "last_import_age_max": config_estado.last_import_age_max,
            "days_since_last_sale_min": config_estado.days_since_last_sale_min,
            "ult_modificacion_descuento": config_estado.ult_modificacion_descuento
        },
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
        },
        "mensaje": "Descuento aplicado correctamente"
    }
