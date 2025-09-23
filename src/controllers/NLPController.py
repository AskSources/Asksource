from .BaseController import BaseController
from ..models.db_schemes import Project, DataChunk
from ..stores.llm.LLMEnums import DocumentTypeEnum
from typing import List
import json
from ..models.ChunkModel import ChunkModel
import logging
from ..utils.metrics import EMBEDDINGS_COUNT , ANSWER_CONFIDENCE  , SPARSE_EMBEDDINGS_COUNT
from qdrant_client.http.exceptions import UnexpectedResponse
logger = logging.getLogger(__name__)

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser, sparse_embedding_client, reranker_client):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.sparse_embedding_client = sparse_embedding_client
        self.template_parser = template_parser
        self.reranker_client = reranker_client
    def create_collection_name(self, project_id: str):
        return f"collection_{project_id}".strip()
    
    def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return self.vectordb_client.delete_collection(collection_name=collection_name)
    
    # الكود الصحيح مع المسافات البادئة
    def get_vector_db_collection_info(self, project: Project):
            collection_name = self.create_collection_name(project_id=project.project_id)
            try:
                collection_info = self.vectordb_client.get_collection_info(collection_name=collection_name)
                return json.loads(
                    json.dumps(collection_info, default=lambda x: x.__dict__)
                )
            except UnexpectedResponse as e:
                if e.status_code == 404:
                    return {
                        "vectors_count": 0,
                        "points_count": 0,
                        "status": "not_indexed"
                    }
                raise e
    
    
    def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                                   chunks_ids: List[int], 
                                   do_reset: bool = False):
        
        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: manage items
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in  chunks]
        # Generate dense vectors (existing logic)
        dense_vectors = [
            self.embedding_client.embed_text(text=text, 
                                             document_type=DocumentTypeEnum.DOCUMENT.value)
            for text in texts
        ]
        
        EMBEDDINGS_COUNT.inc(len(dense_vectors))
        # Generate sparse vectors (new logic)
        sparse_vectors = [
            self.sparse_embedding_client.generate_sparse_vector(text=text)
            for text in texts
        ]
        
        SPARSE_EMBEDDINGS_COUNT.inc(len(sparse_vectors))

        # step3: create collection if not exists
        _ = self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        # Pass both vector types to the insert function
        _ = self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            dense_vectors=dense_vectors, # Changed from "vectors"
            sparse_vectors=sparse_vectors, # Add this
            record_ids=chunks_ids,
        )

        return True

    
    
    
    async def reindex_project(self, project: Project, chunk_model: ChunkModel):
        """
        Deletes the entire vector collection and re-indexes all chunks
        from MongoDB for a given project.
        """
        logger.info(f"Starting auto re-indexing for project: {project.project_id}")

        has_records = True
        page_no = 1
        inserted_items_count = 0
        is_first_batch = True

        while has_records:
            page_chunks = await chunk_model.get_project_chunks(project_id=project.id, page_no=page_no)
            
            if not page_chunks or len(page_chunks) == 0:
                has_records = False
                # If no chunks are left, ensure the vector collection is cleared.
                if is_first_batch:
                    collection_name = self.create_collection_name(project_id=project.project_id)
                    self.vectordb_client.delete_collection(collection_name=collection_name)
                    logger.warning(f"Project {project.project_id} has no chunks. Vector DB collection cleared.")
                break

            page_no += 1
            chunks_ids = list(range(inserted_items_count, inserted_items_count + len(page_chunks)))

            self.index_into_vector_db(
                project=project,
                chunks=page_chunks,
                do_reset=is_first_batch,
                chunks_ids=chunks_ids
            )

            is_first_batch = False
            inserted_items_count += len(page_chunks)

        logger.info(f"Finished auto re-indexing for project: {project.project_id}. Total chunks indexed: {inserted_items_count}")
        return inserted_items_count
    
    def search_hybrid_collection(self, project: Project, text: str, 
                                 dense_limit: int, sparse_limit: int, limit: int):
        
        collection_name = self.create_collection_name(project_id=project.project_id)

        # Step 1: Generate dense vector for the query
        dense_vector = self.embedding_client.embed_text(
            text=text, 
            document_type=DocumentTypeEnum.QUERY.value
        )
        if not dense_vector:
            return None

        # Step 2: Generate sparse vector for the query
        sparse_vector = self.sparse_embedding_client.generate_sparse_vector(text=text)
        if not sparse_vector:
            return None
        
        # Step 3: Perform hybrid search
        results = self.vectordb_client.search_hybrid(
            collection_name=collection_name,
            dense_vector=dense_vector,
            sparse_vector=sparse_vector,
            dense_limit=dense_limit,
            sparse_limit=sparse_limit,
            limit=limit
        )

        return results
    
    def search_hybrid_with_rerank(self, project: Project, text: str, 
                                  dense_limit: int, sparse_limit: int, 
                                  rerank_limit: int):
        
        # Step 1: Perform an initial hybrid search to get candidate documents.
        # We fetch more documents than needed (e.g., 25) to give the reranker a good selection.
        initial_candidates = self.search_hybrid_collection(
            project=project,
            text=text,
            dense_limit=dense_limit,
            sparse_limit=sparse_limit,
            limit=rerank_limit * 3  # Fetch more candidates for reranking
        )

        if not initial_candidates:
            return None

        # Step 2: Rerank the candidates using the Cross-Encoder model.
        # The documents need to be converted to dicts for the reranker.
        candidate_dicts = [doc.dict() for doc in initial_candidates]
        reranked_results = self.reranker_client.rerank_documents(
            query=text,
            documents=candidate_dicts
        )

        # Step 3: Return the top N results after reranking.
        return reranked_results[:rerank_limit]
    
    def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):

        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: get text embedding vector
        vector = self.embedding_client.embed_text(text=text, 
                                                 document_type=DocumentTypeEnum.QUERY.value)

        if not vector or len(vector) == 0:
            return False

        # step3: do semantic search
        results = self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=vector,
            limit=limit
        )

        if not results:
            return False

        return results
    


    def answer_rag_question(self, project: Project, query: str, limit: int = 10):
        
        answer, full_prompt, chat_history = None, None, None

        # step1: retrieve related documents
        retrieved_documents = self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit,
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, chat_history
        
        # ===== confidence score=====
        total_score = sum(doc.score for doc in retrieved_documents)
        average_score = total_score / len(retrieved_documents) if retrieved_documents else 0
        # ====================================

        # step2: Construct LLM prompt
        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                    "doc_num": idx + 1,
                    "chunk_text": doc.text,
            })
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": query
        })

        # step3: Construct Generation Client Prompts
        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([ documents_prompts,  footer_prompt])

        # step4: Retrieve the Answer
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )
        ANSWER_CONFIDENCE.observe(average_score)
        return answer, full_prompt, chat_history
    

    def answer_rag_question_hybrid(self, project: Project, query: str, 
                                   dense_limit: int, sparse_limit: int, 
                                   limit: int):
        
        answer, full_prompt, chat_history = None, None, None

        # Step 1: Retrieve related documents using HYBRID SEARCH
        retrieved_documents = self.search_hybrid_collection(
            project=project,
            text=query,
            dense_limit=dense_limit,
            sparse_limit=sparse_limit,
            limit=limit,
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, chat_history
        
        # ===== confidence score=====
        total_score = sum(doc.score for doc in retrieved_documents)
        average_score = total_score / len(retrieved_documents) if retrieved_documents else 0
        # ====================================

        # Step 2: Construct LLM prompt (This logic remains the same)
        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                    "doc_num": idx + 1,
                    "chunk_text": doc.text,
            })
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": query
        })

        # Step 3: Construct Generation Client Prompts (This logic remains the same)
        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([ documents_prompts,  footer_prompt])

        # Step 4: Retrieve the Answer (This logic remains the same)
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )
        ANSWER_CONFIDENCE.observe(average_score)
        return answer, full_prompt, chat_history
    
    def answer_rag_question_hybrid_cross(self, project: Project, query: str, 
                                         dense_limit: int, sparse_limit: int, 
                                         limit: int):
        
        answer, full_prompt, chat_history = None, None, None

        # Step 1: Retrieve the best possible documents using hybrid search + reranker
        reranked_documents = self.search_hybrid_with_rerank(
            project=project,
            text=query,
            dense_limit=dense_limit,
            sparse_limit=sparse_limit,
            rerank_limit=limit, # Use the final limit for the reranker
        )

        if not reranked_documents or len(reranked_documents) == 0:
            return answer, full_prompt, chat_history
        
        # ===== confidence score =====
        total_score = sum(doc['rerank_score'] for doc in reranked_documents)
        average_score = total_score / len(reranked_documents) if reranked_documents else 0
        # ====================================
        # Step 2: Construct LLM prompt (Same logic as before)
        system_prompt = self.template_parser.get("rag", "system_prompt")

        # The reranked_documents are already dicts, so we access text with ['text']
        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                    "doc_num": idx + 1,
                    "chunk_text": doc['text'],
            })
            for idx, doc in enumerate(reranked_documents)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": query
        })

        # Step 3: Construct Generation Client Prompts (Same logic as before)
        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([ documents_prompts,  footer_prompt])

        # Step 4: Retrieve the Answer (Same logic as before)
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )
        ANSWER_CONFIDENCE.observe(average_score)
        return answer, full_prompt, chat_history