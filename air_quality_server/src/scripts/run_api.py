import uvicorn
from air_quality_core.config.settings import settings


def main():
    uvicorn.run(
        "air_quality.adapters.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )


if __name__ == "__main__":
    main()
