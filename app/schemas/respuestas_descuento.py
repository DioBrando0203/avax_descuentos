from typing import Optional, Union
from pydantic import BaseModel


class Umbrales(BaseModel):
    last_import_age_max: int
    days_since_last_sale_min: int
    ult_modificacion_descuento: int


class DatosZap(BaseModel):
    last_import_age_max: float
    days_since_last_sale_min: Optional[str] = None


class DatosAvax(BaseModel):
    ult_actualizacion_descuento: Optional[str] = None
    dias_desde_modificacion: Optional[int] = None
    descuentos_automaticos: Optional[bool] = None
    esq_costo_actual: Optional[str] = None


class RespNoEncontrado(BaseModel):
    status: str = "no_encontrado"
    cod_prod: str
    mensaje: str


class RespExcluido(BaseModel):
    status: str = "excluido"
    cod_prod: str
    descuentos_automaticos: bool
    mensaje: str


class RespNoApto(BaseModel):
    status: str = "no_apto"
    cod_prod: str
    estado_usado: str
    ruta_evaluada: str
    umbrales_usados: Umbrales
    descuento_actual: str
    datos_zap: DatosZap
    datos_avax: DatosAvax
    mensaje: str


class RespErrorValidacion(BaseModel):
    status: str = "error_validacion"
    cod_prod: str
    estado_usado: str
    ruta_evaluada: str
    umbrales_usados: Umbrales
    descuento_actual: str
    esq_costo_actual: str
    datos_avax: DatosAvax
    mensaje: str


class RespAplicado(BaseModel):
    status: str = "aplicado"
    cod_prod: str
    estado_usado: str
    ruta_usada: str
    umbrales_usados: Umbrales
    descuento_anterior: str
    descuento_nuevo: str
    esq_costo_nuevo: Optional[str] = None
    categoria_liquidacion_agregada: bool = False
    datos_zap: DatosZap
    datos_avax: DatosAvax
    mensaje: str


class DetalleError(BaseModel):
    cod_prod: Optional[str] = None
    error: str


class RespProcesarProductos(BaseModel):
    estado_ejecutado: Optional[str] = None
    umbrales_usados: Optional[Umbrales] = None
    productos_evaluados: int = 0
    productos_modificados: int = 0
    productos_no_aptos: int = 0
    productos_excluidos: int = 0
    productos_no_encontrados: int = 0
    errores: int = 0
    error_general: Optional[str] = None
    detalle_resultados: list[
        Union[
            RespAplicado,
            RespNoApto,
            RespErrorValidacion,
            RespExcluido,
            RespNoEncontrado,
            DetalleError,
        ]
    ] = []
