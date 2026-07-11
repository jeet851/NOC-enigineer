from pydantic import BaseModel

class SearchMemoryRequest(BaseModel):
    query: str

class AnalyzePcapRequest(BaseModel):
    filepath: str

class OCRDiagramRequest(BaseModel):
    imagepath: str
