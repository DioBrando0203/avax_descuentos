import httpx
from datetime import datetime, timedelta
from app.config import get_settings


class ZapClient:
    """Cliente para API ZAP - Endpoint de Churn"""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.ZAP_BASE_URL

    async def get_product_churn(self) -> list[dict]:
        """Obtener datos de churn desde ZAP"""
        
        # Rango de 2 días 

        today = datetime.now()
        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")

        url = f"{self.base_url}/kpi/product-churn"
        params = {
            "start_date": yesterday,
            "end_date": today_str,
            "granularity": 1,
            "group_by": "sku",
            "include_avax_licenses": "false",
            "include_initial_stock": "true",
            "include_credit": "true"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self.settings.ZAP_TOKEN}"},
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            # Los productos están en aging_products según la documentación
            return data.get("aging_products", [])


zap_client = ZapClient()
