from fastapi import FastAPI
from .routers import data
# from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorClient # type: ignore
from .help.config import Settings


app = FastAPI()
@app.on_event("startup")
async def startup_db_client():
    settings = Settings()
    app.mongodb_conn = AsyncIOMotorClient(settings.MONGODB_URL)
    app.db_client = app.mongodb_conn[settings.MONGODB_DATABASE]

@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_conn.close()


app.include_router(data.data_router)