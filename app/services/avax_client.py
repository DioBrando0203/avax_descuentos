import asyncio
from datetime import date
from typing import List, Optional

import httpx

from app.config import get_settings


class AvaxClient:
    CATEGORIA_LIQUIDACION = "Liquidacion"
    ESQ_COSTO_LIQUIDACION = {"LIQ_20M", "LIQ_30M"}
    DESCUENTOS_PUSH = {"PUSH1", "PUSH2"}

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.AVAX_BASE_URL

    async def get_producto(self, cod_prod: str) -> dict:
        url = f"{self.base_url}/empleados/productos/{cod_prod}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"token": self.settings.AVAX_TOKEN},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", data)

    async def actualizar_precio(self, cod_prod: str) -> dict:
        url = f"{self.base_url}/empleados/productos/{cod_prod}/actions/actualizar_precio"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"token": self.settings.AVAX_TOKEN},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def actualizar_categorias(self, cod_prod: str, categorias: List[str]) -> dict:
        url = f"{self.base_url}/empleados/categorias_productos/{cod_prod}"

        payload = {"id_categorias": categorias}

        async with httpx.AsyncClient() as client:
            response = await client.put(
                url,
                json=payload,
                headers={"token": self.settings.AVAX_TOKEN},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def _esperar_con_timer_actualizar_precio(self, cod_prod: str, segundos: int) -> None:
        if segundos <= 0:
            return

        print(f"[{cod_prod}] Esperando {segundos}s antes de actualizar precio...")
        for restante in range(segundos, 0, -1):
            print(f"[{cod_prod}] actualizar_precio en {restante}s")
            await asyncio.sleep(1)

    def _extraer_lista_strings(self, datos: list, campo: str) -> List[str]:
        if not datos:
            return []
        if isinstance(datos[0], dict):
            return [item.get(campo) for item in datos if item.get(campo)]
        return datos

    def _extraer_lista_ints(self, datos: list, campo: str) -> List[int]:
        if not datos:
            return []
        if isinstance(datos[0], dict):
            return [item.get(campo) for item in datos if item.get(campo)]
        return datos

    def _debe_agregar_categoria_liquidacion(
        self,
        id_esq_costo: str,
        id_descuento: str,
    ) -> bool:
        if id_descuento == "LIQUIDACION":
            return True
        return (
            id_esq_costo in self.ESQ_COSTO_LIQUIDACION
            and id_descuento in self.DESCUENTOS_PUSH
        )

    def _debe_actualizar_ult_descuento_automatico(
        self,
        esq_costo_actual: str,
        esq_costo_final: str,
        descuento_actual: str,
        descuento_final: str,
    ) -> bool:
        cambio_a_esq_liq = (
            esq_costo_actual != esq_costo_final
            and esq_costo_final in self.ESQ_COSTO_LIQUIDACION
        )
        descuentos_objetivo = self.DESCUENTOS_PUSH | {"LIQUIDACION"}
        cambio_descuento_objetivo = (
            descuento_actual != descuento_final
            and descuento_final in descuentos_objetivo
        )
        return cambio_a_esq_liq or cambio_descuento_objetivo

    def _gestionar_categoria_liquidacion(
        self,
        categorias_actuales: List[str],
        id_esq_costo: str,
        id_descuento: str,
    ) -> tuple[List[str], bool]:
        categorias = categorias_actuales.copy()
        categoria_agregada_ahora = False

        if self._debe_agregar_categoria_liquidacion(id_esq_costo, id_descuento) and (
            self.CATEGORIA_LIQUIDACION not in categorias
        ):
            categorias.append(self.CATEGORIA_LIQUIDACION)
            categoria_agregada_ahora = True

        # Si ya tiene la categoria Liquidacion, mantenerla.
        return categorias, categoria_agregada_ahora

    async def actualizar_descuento(
        self,
        cod_prod: str,
        nuevo_descuento: str,
        nuevo_esq_costo: Optional[str] = None,
        producto_actual: Optional[dict] = None,
    ) -> dict:
        # 1. Obtener producto actual (si no nos lo pasaron)
        producto = producto_actual or await self.get_producto(cod_prod)
        esq_costo_actual = producto.get("id_esq_costo")
        descuento_actual = producto.get("id_descuento")

        # 2. Determinar nuevo esq_costo
        esq_costo_final = nuevo_esq_costo or esq_costo_actual

        # 3. Extraer listas del formato de respuesta de AVAX
        generos = self._extraer_lista_strings(producto.get("generos", []), "id_genero")
        listas_precios = self._extraer_lista_strings(
            producto.get("productos_listas_precios", []), "id_lista_precio"
        )
        conjunto_cats = self._extraer_lista_ints(
            producto.get("conjunto_categorias", []), "id_conjunto_categoria"
        )
        siluetas = self._extraer_lista_ints(
            producto.get("siluetas", []), "id_silueta"
        )
        categorias_actuales = self._extraer_lista_strings(
            producto.get("categorias", []), "id_categoria"
        )

        # 4. Gestionar categoria Liquidacion
        categorias_nuevas, categoria_agregada = self._gestionar_categoria_liquidacion(
            categorias_actuales, esq_costo_final, nuevo_descuento
        )

        # 5. Payload completo para PATCH
        actualizar_ult_descuento = self._debe_actualizar_ult_descuento_automatico(
            esq_costo_actual,
            esq_costo_final,
            descuento_actual,
            nuevo_descuento,
        )
        payload = {
            "nombre": producto.get("nombre"),
            "id_marca": producto.get("id_marca"),
            "id_genero": producto.get("id_genero"),
            "id_tipo_producto": producto.get("id_tipo_producto"),
            "valid_web": False,
            "retail_val": producto.get("retail_val"),
            "retail_mto": producto.get("retail_mto"),
            "id_esq_costo": esq_costo_final,
            "id_descuento": nuevo_descuento,
            "generos": generos,
            "productos_listas_precios": listas_precios,
            "penalizacion_orden": producto.get("penalizacion_orden"),
            "id_subtipo_producto": producto.get("id_subtipo_producto"),
            "ids_conjunto_categoria": conjunto_cats,
            "ids_silueta": siluetas,
            "descuentos_automaticos": producto.get("descuentos_automaticos"),
        }
        if actualizar_ult_descuento:
            # Se toca fecha si cambia a esquema LIQ o si cambia descuento a PUSH/LIQUIDACION.
            payload["ult_actualizacion_descuento_automatico"] = date.today().isoformat()

        # 6. Enviar PATCH al producto
        url = f"{self.base_url}/empleados/productos/{cod_prod}"

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                url,
                json=payload,
                headers={"token": self.settings.AVAX_TOKEN},
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

        # 7. Actualizar categorias
        if categorias_nuevas != categorias_actuales:
            await self.actualizar_categorias(cod_prod, categorias_nuevas)

        # 8. Si cambio id_esq_costo, gatillar actualizacion de precios
        if nuevo_esq_costo and nuevo_esq_costo != esq_costo_actual:
            await self._esperar_con_timer_actualizar_precio(
                cod_prod, self.settings.REQUEST_DELAY
            )
            await self.actualizar_precio(cod_prod)

        # 9. Retornar resultado con info adicional
        return {
            "response": result,
            "categoria_liquidacion_agregada": categoria_agregada,
            "categorias_finales": categorias_nuevas,
        }


avax_client = AvaxClient()
