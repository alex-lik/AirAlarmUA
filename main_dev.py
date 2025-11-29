import services.alerts_api
import asyncio
from config import settings
async def main():
    alerts_api_service = services.alerts_api.AlertsApiService()
    r = await alerts_api_service.get_alerts_status()
    print(r)

if __name__ == "__main__":
    asyncio.run(main())
    print(settings.alerts_api_token)