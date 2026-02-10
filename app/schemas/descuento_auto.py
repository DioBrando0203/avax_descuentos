from pydantic import BaseModel, Field
from typing import Optional, List
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


class ProcesarProductosRequest(BaseModel):
    productos: List[str] = Field(min_length=1)
    estado: Optional[EstadoLogica] = None
