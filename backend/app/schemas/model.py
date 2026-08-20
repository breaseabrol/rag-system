from pydantic import BaseModel, Field

class IngestRequest(BaseModel):
    url:str = Field(..., description="URL of the page to ingest")

class IngestResponse(BaseModel):
    document_id:int
    url:str
    title:str
    chunk_count:int

class ChunkResult(BaseModel):
    chunk_id:int
    content:str
    document_title:str
    document_url:str

class QueryRequest(BaseModel):
    query:str = Field(..., min_length=1, description="The user's question")
    top_k:int = Field(default=None, description="Override retrieval_top_k from config, if set")

class QueryResponse(BaseModel):
    answer:str
    sources: list[ChunkResult]