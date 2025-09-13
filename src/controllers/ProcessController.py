from .BaseController import BaseController
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader, UnstructuredExcelLoader, PDFPlumberLoader
from langchain_community.document_loaders import UnstructuredWordDocumentLoader  
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ..models import ProcessingEnum
from .ProjectController import ProjectController
import os
from ..utils.metrics import DOCS_INDEXED, CHUNKS_PER_QUERY 

class ProcessController(BaseController):
    """Controller for processing files."""
    
    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id=project_id)

    def get_file_extention(self, file_id: str):
        return os.path.splitext(file_id)[-1]    
    
    def get_file_loader(self, file_id: str):

        file_ext = self.get_file_extention(file_id=file_id)
        file_path = os.path.join(
            self.project_path,
            file_id
        )
        """Process the file based on its type."""
        if file_ext == ProcessingEnum.PDF.value:
            try:
                return PDFPlumberLoader(file_path)
            except:
                return PyPDFLoader(file_path)
        if file_ext == ProcessingEnum.TXT.value:
            return  TextLoader(file_path)
        if file_ext == ProcessingEnum.DOCX.value:
            return  UnstructuredWordDocumentLoader(file_path)
        if file_ext == ProcessingEnum.DOC.value:
            return  Docx2txtLoader(file_path)
        if file_ext == ProcessingEnum.XLS.value or file_ext == ProcessingEnum.XLSX.value:
            return  UnstructuredExcelLoader(file_path)
        raise ValueError(f"Unsupported file type: {file_ext}")
        
    def get_file_content(self, file_id: str):

        loader = self.get_file_loader(file_id=file_id)
        return loader.load()
    
    def process_file_content(self, file_content: list, file_id: str,
                            chunk_size: int=400, overlap_size: int=30):

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap_size,
            length_function=len,
        )

        file_content_texts = [
            rec.page_content
            for rec in file_content
        ]

        file_content_metadata = [
            rec.metadata
            for rec in file_content
        ]

        chunks = text_splitter.create_documents(
            file_content_texts,
            metadatas=file_content_metadata
        )

        DOCS_INDEXED.inc()
        CHUNKS_PER_QUERY.observe(len(chunks))

        return chunks
    

    
    