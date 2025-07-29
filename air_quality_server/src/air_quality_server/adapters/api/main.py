from fastapi import FastAPI

from air_quality_server.adapters.api.routes import router

app = FastAPI()
app.include_router(router)
