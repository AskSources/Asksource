from fastapi import FastAPI
from routers import data

app = FastAPI()
app.include_router(data.data_router)