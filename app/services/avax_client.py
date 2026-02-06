import httpx
import asyncio
from datetime import date
from typing import Optional, List
from app.config import get_settings


class AvaxClient:
    """Cliente para API AVAX - Modificación de Productos"""

    CATEGORIA_LIQUIDACION = "Liquidacion"

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.AVAX_BASE_URL

    async def get_producto(self, cod_prod: str) -> dict:
        """Obtener información de un producto"""
        url = f"{self.base_url}/empleados/productos/{cod_prod}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"token": self.settings.AVAX_TOKEN},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", data)

    async def actualizar_precio(self, cod_prod: str) -> dict:
        """
        Gatilla el proceso de actualización de precio.
        Se usa SOLO cuando cambia el id_esq_costo.
        """
        url = f"{self.base_url}/empleados/productos/{cod_prod}/actions/actualizar_precio"

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                url,
                headers={"token": self.settings.AVAX_TOKEN},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    def _extraer_lista_strings(self, datos: list, campo: str) -> List[str]:
        """Extrae lista de strings de un array de dicts"""
        if not datos:
            return []
        if isinstance(datos[0], dict):
            return [item.get(campo) for item in datos if item.get(campo)]
        return datos

    def _extraer_lista_ints(self, datos: list, campo: str) -> List[int]:
        """Extrae lista de ints de un array de dicts"""
        if not datos:
            return []
        if isinstance(datos[0], dict):
            return [item.get(campo) for item in datos if item.get(campo)]
        return datos

    def _debe_agregar_liquidacion(self, id_esq_costo: str, id_descuento: str) -> bool:
        """
        Determina si el producto debe tener categoría Liquidación.

        Condiciones:
        - (ESQ_PRECIO: LIQ_20M/LIQ_30M) Y (DESCUENTO: PUSH1, PUSH2, LIQUIDACION)
        - O (CUALQUIER ESQ_PRECIO) + (DESCUENTO: LIQUIDACION)
        """
        if id_esq_costo in ["LIQ_20M", "LIQ_30M"]:
            if id_descuento in ["PUSH1", "PUSH2", "LIQUIDACION"]:
                return True

        if id_descuento == "LIQUIDACION":
            return True

        return False

    def _gestionar_categoria_liquidacion(
        self,
        categorias_actuales: List[str],
        id_esq_costo: str,
        id_descuento: str
    ) -> List[str]:
        """Agrega o quita la categoría Liquidacion según las condiciones"""
        categorias = categorias_actuales.copy()
        debe_tener = self._debe_agregar_liquidacion(id_esq_costo, id_descuento)

        if debe_tener and self.CATEGORIA_LIQUIDACION not in categorias:
            categorias.append(self.CATEGORIA_LIQUIDACION)
        elif not debe_tener and self.CATEGORIA_LIQUIDACION in categorias:
            categorias.remove(self.CATEGORIA_LIQUIDACION)

        return categorias

    async def actualizar_descuento(
        self,
        cod_prod: str,
        nuevo_descuento: str,
        nuevo_esq_costo: Optional[str] = None
    ) -> dict:
        """
        Actualiza el descuento de un producto.

        1. Obtiene el producto actual
        2. Construye payload completo (AVAX requiere todos los campos)
        3. Gestiona categoría Liquidacion automáticamente
        4. Si cambia id_esq_costo, llama a actualizar_precio con timer de 3 segundos

        Args:
            cod_prod: Código del producto
            nuevo_descuento: Nuevo id_descuento (Sin descuento, PUSH1, PUSH2, LIQUIDACION)
            nuevo_esq_costo: Nuevo id_esq_costo (opcional, para LIQ_20M, LIQ_30M)
        """
        # 1. Obtener producto actual
        producto = await self.get_producto(cod_prod)
        esq_costo_actual = producto.get("id_esq_costo")

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

        # 4. Gestionar categoría Liquidacion
        categorias_nuevas = self._gestionar_categoria_liquidacion(
            categorias_actuales, esq_costo_final, nuevo_descuento
        )

        # 5. Construir payload completo
        payload = {
            "nombre": producto.get("nombre"),
            "id_marca": producto.get("id_marca"),
            "id_genero": producto.get("id_genero"),
            "id_tipo_producto": producto.get("id_tipo_producto"),
            "valid_web": producto.get("valid_web"),
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
            "categorias": categorias_nuevas,
            "descuentos_automaticos": producto.get("descuentos_automaticos"),
            "ult_actualizacion_descuento_automatico": date.today().isoformat()
        }

        # 6. Enviar PATCH
        url = f"{self.base_url}/empleados/productos/{cod_prod}"

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                url,
                json=payload,
                headers={"token": self.settings.AVAX_TOKEN},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

        # 7. Si cambió id_esq_costo, gatillar actualización de precios
        if nuevo_esq_costo and nuevo_esq_costo != esq_costo_actual:
            # Timer de 3 segundos antes de llamar actualizar_precio
            await asyncio.sleep(3)
            await self.actualizar_precio(cod_prod)

        # 8. Retornar resultado con info adicional
        categoria_liquidacion_agregada = (
            self.CATEGORIA_LIQUIDACION in categorias_nuevas and
            self.CATEGORIA_LIQUIDACION not in categorias_actuales
        )

        return {
            "response": result,
            "categoria_liquidacion_agregada": categoria_liquidacion_agregada
        }


avax_client = AvaxClient()
