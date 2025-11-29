import services.alerts_api
import asyncio
from config import settings, regions
from icecream import ic
async def main():
    alerts_api_service = services.alerts_api.AlertsApiService()
    r = await alerts_api_service.get_alerts_status()
    # `ic(r[''])

    for k in r:
        ic(k)
    print(r.regions)
    print(r.regions['Автономна Республіка Крим'])
if __name__ == "__main__":
    asyncio.run(main())
    ic(settings.alerts_api_token)
    # ic()