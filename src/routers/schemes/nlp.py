from pydantic import BaseModel
from typing import Optional

class PushRequest(BaseModel):
    do_reset: Optional[int] = 0

class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 5

class HybridSearchRequest(BaseModel):
    text: str
    dense_limit: Optional[int] = 10
    sparse_limit: Optional[int] = 5
    limit: Optional[int] = 5    

class RerankSearchRequest(BaseModel):
    text: str
    dense_limit: Optional[int] = 10
    sparse_limit: Optional[int] = 5
    limit: Optional[int] = 5
