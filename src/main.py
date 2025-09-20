from fastapi import FastAPI 
from .routers import data , nlp
# from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorClient 
from .help.config import Settings
from .stores.llm.LLMProviderFactory import LLMProviderFactory
from .stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from .stores.llm.templates.template_parser import TemplateParser
from .stores.sparse_embedding.SparseEmbeddingProvider import SparseEmbeddingProvider
from .stores.reranker.CrossEncoderProvider import CrossEncoderProvider
from .utils.metrics import setup_metrics 
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS Middleware Configuration
origins = [*]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


setup_metrics(app)

@app.on_event("startup")
async def startup_db_client():
    settings = Settings()
    app.mongodb_conn = AsyncIOMotorClient(settings.MONGODB_URL)
    app.db_client = app.mongodb_conn[settings.MONGODB_DATABASE]
    
    llm_provider_factory = LLMProviderFactory(settings)

    # generation client
    app.generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(model_id = settings.GENERATION_MODEL_ID)

    # embedding client
    app.embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID,
                                             embedding_size=settings.EMBEDDING_MODEL_SIZE)
    
    # vector db client
    vectordb_factory = VectorDBProviderFactory(config=settings)
    app.vectordb_client = vectordb_factory.create(provider=settings.VECTOR_DB_BACKEND)
    app.vectordb_client.connect()

    app.template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )
    
    # sparse embedding client
    app.sparse_embedding_client = SparseEmbeddingProvider(model_id=settings.SPLADE_MODEL_ID)
    
     # reranker client
    app.reranker_client = CrossEncoderProvider(model_id=settings.RERANKER_MODEL_ID)


@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_conn.close()
    app.vectordb_client.disconnect()

# app.router.lifespan.on_startup.append(startup_db_client)
# app.router.lifespan.on_shutdown.append(shutdown_db_client)

app.include_router(data.data_router)
app.include_router(nlp.nlp_router)