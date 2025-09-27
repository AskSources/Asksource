APP_NAME="ASKSOURCE"
APP_VERSION="0.1"

FILE_ALLOWED_TYPES='["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword", "text/plain", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]'
FILE_DEFAULT_CHUNK_SIZE=512000 # 512KB
FILE_MAX_SIZE=10 # 10MB

MONGODB_URL="mongodb://admin:admin123@localhost:20022"
MONGODB_DATABASE="ASKSOURCE_DB"

# .env file
WATCHFILES_IGNORE_PATHS="docker"

############ llm configurations ###########

GENERATION_BACKEND = "OPENAI"
EMBEDDING_BACKEND = "COHERE"

OPENAI_API_KEY=
OPENAI_base_URL=

COHERE_API_KEY=
GEMINI_API_KEY=
GENERATION_MODEL_ID=
# GENERATION_MODEL_ID="gemma2:9b-instruct-q5_0"
EMBEDDING_MODEL_ID="embed-multilingual-light-v3.0"
EMBEDDING_MODEL_SIZE=384

INPUT_DEFAULT_MAX_CHARACTERS=10244
GENERATION_DEFAULT_MAX_TOKENS=2000
GENERATION_DEFAULT_TEMPERATURE=0.1

# ========================= Vector DB Config =========================
VECTOR_DB_BACKEND="QDRANT"
VECTOR_DB_PATH="qdrant_db"
VECTOR_DB_DISTANCE_METHOD="cosine"

# ========================= Template Configs =========================
PRIMARY_LANG = "en"
DEFAULT_LANG = "en"

# ========================= Model Configs =========================
SPLADE_MODEL_ID="opensearch-project/opensearch-neural-sparse-encoding-v1"
RERANKER_MODEL_ID="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


