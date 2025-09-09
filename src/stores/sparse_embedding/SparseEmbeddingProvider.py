import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer

class SparseEmbeddingProvider:
    def __init__(self, model_id: str ):
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForMaskedLM.from_pretrained(model_id)
        self.model.eval()  # Set model to evaluation mode

    def generate_sparse_vector(self, text: str):
        """
        Generates a sparse vector for a given text using the SPLADE model.
        """
        with torch.no_grad():
            tokens = self.tokenizer(text, return_tensors='pt')
            output = self.model(**tokens)
            
            # Aggregate token embeddings to get a document-level sparse vector
            vector = torch.max(
                torch.log(1 + torch.relu(output[0])) * tokens.attention_mask.unsqueeze(-1), 
                dim=1
            )[0].squeeze()

            # Extract non-zero indices and their values
            indices = vector.nonzero().squeeze().cpu().tolist()
            values = vector[indices].cpu().tolist()

            # Ensure indices are always a list
            if not isinstance(indices, list):
                indices = [indices]
                values = [values]
            
            return {
                "indices": indices,
                "values": values
            }