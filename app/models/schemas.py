from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class EstadoLogica(str, Enum):
    REGULAR = "regular"
    LIQUIDACION_TODO_STOCK = "liquidacion_todo_stock"
    LIQUIDACION_AGRESIVA = "liquidacion_agresiva"
    LIQUIDACION_SUAVE = "liquidacion_suave"


class ConfigEstadoLogica(BaseModel):
    last_import_age_max: int
    days_since_last_sale_min: int
    ult_modificacion_descuento: int


class ConfiguracionGeneral(BaseModel):
    estado_logica_activo: EstadoLogica = EstadoLogica.REGULAR
    regular: ConfigEstadoLogica = ConfigEstadoLogica(
        last_import_age_max=500,
        days_since_last_sale_min=80,
        ult_modificacion_descuento=80
    )
    liquidacion_todo_stock: ConfigEstadoLogica = ConfigEstadoLogica(
        last_import_age_max=500,
        days_since_last_sale_min=80,
        ult_modificacion_descuento=80
    )
    liquidacion_agresiva: ConfigEstadoLogica = ConfigEstadoLogica(
        last_import_age_max=500,
        days_since_last_sale_min=80,
        ult_modificacion_descuento=80
    )
    liquidacion_suave: ConfigEstadoLogica = ConfigEstadoLogica(
        last_import_age_max=500,
        days_since_last_sale_min=120,
        ult_modificacion_descuento=120
    )


class ConfiguracionPatch(BaseModel):
    estado_logica_activo: Optional[EstadoLogica] = None
    regular: Optional[ConfigEstadoLogica] = None
    liquidacion_todo_stock: Optional[ConfigEstadoLogica] = None
    liquidacion_agresiva: Optional[ConfigEstadoLogica] = None
    liquidacion_suave: Optional[ConfigEstadoLogica] = None


class ProductoAvax(BaseModel):
    """Modelo completo de producto para enviar a AVAX"""
    nombre: str
    id_marca: str
    id_genero: str
    id_tipo_producto: str
    valid_web: bool
    retail_val: bool
    retail_mto: float
    id_esq_costo: str
    id_descuento: str
    generos: List[str] = []
    productos_listas_precios: List[str] = []
    penalizacion_orden: Optional[str] = None
    id_subtipo_producto: Optional[str] = None
    ids_conjunto_categoria: List[int] = []
    ids_silueta: List[int] = []
    categorias: List[str] = []
    descuentos_automaticos: Optional[bool] = None
    ult_actualizacion_descuento_automatico: Optional[date] = None
