from sentence_transformers import CrossEncoder
from typing import List

class CrossEncoderProvider:
    def __init__(self, model_id: str = 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'):
        # Load a pre-trained Cross-Encoder model
        self.model = CrossEncoder(model_id)

    def rerank_documents(self, query: str, documents: List[dict]) -> List[dict]:
        """
        Re-ranks a list of documents based on their relevance to a query.
        """
        if not documents:
            return []

        # Create pairs of [query, document_text] for the model
        model_input = [[query, doc['text']] for doc in documents]
        
        # Predict scores for each pair
        scores = self.model.predict(model_input)
        
        # Add the new cross-encoder score to each document
        for i in range(len(documents)):
            documents[i]['rerank_score'] = float(scores[i])
            
        # Sort documents by the new score in descending order
        reranked_docs = sorted(documents, key=lambda x: x['rerank_score'], reverse=True)
        
        return reranked_docs