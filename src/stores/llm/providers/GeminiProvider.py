from ..LLMInterface import LLMInterface
from ..LLMEnums import DocumentTypeEnum, GeminiEnums
import google.generativeai as genai
import logging

class GeminiProvider(LLMInterface):

    def __init__(self, api_key: str,
                       default_input_max_characters: int=1000,
                       default_generation_max_output_tokens: int=1000,
                       default_generation_temperature: float=0.1):
        
        self.api_key = api_key
        self.default_input_max_characters = default_input_max_characters
        
        self.generation_config = {
            "temperature": default_generation_temperature,
            "max_output_tokens": default_generation_max_output_tokens,
        }

        self.generation_model_id = None
        self.generation_client = None

        self.embedding_model_id = None
        self.embedding_size = None
        self.embedding_client = None

        try:
            genai.configure(api_key=self.api_key)
        except Exception as e:
            logging.error(f"Failed to configure Gemini: {e}")

        self.logger = logging.getLogger(__name__)
        self.enums = GeminiEnums

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id
        self.generation_client = genai.GenerativeModel(self.generation_model_id)

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def process_text(self, text: str):
        return text[:self.default_input_max_characters].strip()

    def generate_text(self, prompt: str, chat_history: list=[], max_output_tokens: int=None,
                            temperature: float = None):

        if not self.generation_client:
            self.logger.error("Generation model for Gemini was not set")
            return None
        
        current_gen_config = self.generation_config.copy()
        if temperature is not None:
            current_gen_config["temperature"] = temperature
        if max_output_tokens is not None:
            current_gen_config["max_output_tokens"] = max_output_tokens

        gemini_history = []
        for msg in chat_history:
            role = self.enums.USER.value if msg["role"] == self.enums.USER.value else self.enums.ASSISTANT.value
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        try:
            chat_session = self.generation_client.start_chat(
                history=gemini_history
            )
            
            response = chat_session.send_message(
                self.process_text(prompt),
                generation_config=genai.types.GenerationConfig(**current_gen_config)
            )
            
            return response.text
        except Exception as e:
            self.logger.error(f"Error while generating text with Gemini: {e}")
            return None

    def embed_text(self, text: str, document_type: str = None):
        if not self.embedding_model_id:
            self.logger.error("Embedding model for Gemini was not set")
            return None

        task_type = "RETRIEVAL_DOCUMENT" if document_type == DocumentTypeEnum.DOCUMENT.value else "RETRIEVAL_QUERY"
        
        try:
            result = genai.embed_content(
                model=self.embedding_model_id,
                content=self.process_text(text),
                task_type=task_type
            )
            return result['embedding']
        except Exception as e:
            self.logger.error(f"Error while embedding text with Gemini: {e}")
            return None

    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "content": self.process_text(prompt)
        }