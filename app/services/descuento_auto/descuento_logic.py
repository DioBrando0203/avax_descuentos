from datetime import date, datetime
from app.schemas.descuento_auto import ConfigEstadoLogica, EstadoLogica


class DescuentosService:
    NIVELES_DESCUENTO = ["Sin descuento", "PUSH1", "PUSH2", "LIQUIDACION"]

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
        if idx == len(niveles) - 1:
            return "PUSH1"
        if idx < len(niveles) - 1:
            return niveles[idx + 1]
        return nivel_actual

    @staticmethod
    def debe_subir_descuento_last_import(
        producto: dict,
        config: ConfigEstadoLogica,
        _ult_actualizacion_descuento: date = None,
    ) -> bool:
        last_import_age = producto.get("last_import_age_max", 0) or 0
        return last_import_age > config.last_import_age_max

    @staticmethod
    def debe_subir_descuento_normal(
        producto: dict,
        config: ConfigEstadoLogica,
        ult_actualizacion_descuento: date = None,
    ) -> bool:
        days_since_sale = producto.get("days_since_last_sale_min")
        last_import_age = producto.get("last_import_age_max", 0) or 0
        if days_since_sale is None or days_since_sale == 0:
            days_since_sale = last_import_age
        # Ruta 2 requiere validar ambos umbrales:
        # days_since_last_sale_min y ult_modificacion_descuento.
        # Si no hay fecha de ultima actualizacion, no puede habilitar la ruta 2.
        if not ult_actualizacion_descuento:
            return False
        dias_desde_modificacion = (date.today() - ult_actualizacion_descuento).days
        cumple_days_sale = days_since_sale > config.days_since_last_sale_min
        cumple_dias_modificacion = dias_desde_modificacion > config.ult_modificacion_descuento
        return cumple_days_sale and cumple_dias_modificacion

    @staticmethod
    def validar_regla_liquidacion(id_esq_costo: str, id_descuento: str) -> bool:
        if id_esq_costo in ["LIQ_20M", "LIQ_30M"] and id_descuento == "Sin descuento":
            return False
        return True

    @staticmethod
    def determinar_nuevo_esq_costo(
        id_esq_costo_actual: str,
        _nuevo_descuento: str,
        _estado_logica: EstadoLogica,
        cumple_last_import: bool,
    ) -> str:
        if not cumple_last_import:
            return None
        if id_esq_costo_actual in ["LIQ_20M", "LIQ_30M"]:
            return None
        nuevo_esq = DescuentosService.MAPEO_ESQ_COSTO_LIQUIDACION.get(id_esq_costo_actual)
        if nuevo_esq:
            return nuevo_esq
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
        if isinstance(fecha_str, date) and not isinstance(fecha_str, datetime):
            return fecha_str
        if isinstance(fecha_str, datetime):
            return fecha_str.date()
        if isinstance(fecha_str, str):
            try:
                return datetime.strptime(fecha_str, "%a, %d %b %Y %H:%M:%S %Z").date()
            except (ValueError, TypeError):
                pass
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
        estado_logica: EstadoLogica,
    ) -> dict:
        id_descuento_actual = producto_avax.get("id_descuento", "Sin descuento")
        id_esq_costo_actual = producto_avax.get("id_esq_costo", "")
        ult_actualizacion_str = producto_avax.get("ult_actualizacion_descuento_automatico")
        ult_actualizacion = DescuentosService.parse_fecha_modificacion(ult_actualizacion_str)
        dias_desde_mod = DescuentosService.calcular_dias_desde_modificacion(ult_actualizacion)
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
            "ruta_usada": None,
        }
        cumple_ruta1 = DescuentosService.debe_subir_descuento_last_import(
            producto_zap, config_estado, ult_actualizacion
        )
        cumple_ruta2 = DescuentosService.debe_subir_descuento_normal(
            producto_zap, config_estado, ult_actualizacion
        )
        if not cumple_ruta1 and not cumple_ruta2:
            resultado["razon"] = "no_cumple_condiciones"
            resultado["ruta_usada"] = "ninguna"
            return resultado
        ruta_usada = "ruta1_last_import" if cumple_ruta1 else "ruta2_normal"
        resultado["ruta_usada"] = ruta_usada
        nuevo_descuento = DescuentosService.obtener_siguiente_nivel(id_descuento_actual)
        descuento_minimo = DescuentosService.obtener_descuento_minimo(estado_logica)
        if id_descuento_actual == "Sin descuento" and descuento_minimo == "PUSH1":
            nuevo_descuento = "PUSH1"
        nuevo_esq_costo = DescuentosService.determinar_nuevo_esq_costo(
            id_esq_costo_actual, nuevo_descuento, estado_logica, cumple_ruta1
        )
        esq_costo_final = nuevo_esq_costo or id_esq_costo_actual
        if not DescuentosService.validar_regla_liquidacion(esq_costo_final, nuevo_descuento):
            resultado["razon"] = "viola_regla_liquidacion"
            return resultado
        resultado["debe_actualizar"] = True
        resultado["nuevo_descuento"] = nuevo_descuento
        resultado["nuevo_esq_costo"] = nuevo_esq_costo
        return resultado
