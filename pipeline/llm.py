import os
import json
import logging
import threading
from llama_cpp import Llama

# Setup logging
logger = logging.getLogger("local-ai")

class LocalAI:
    """
    The 'Brain' of our application.
    
    This class wraps the complex C++ AI engine (llama.cpp) into simple Python functions.
    It manages the computer's memory (RAM) to ensure the AI runs fast without crashing.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """
        Singleton Pattern: This ensures we only ever load the AI model ONCE.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LocalAI, cls).__new__(cls)
                    cls._instance.llm = None
        return cls._instance

    def _load_model(self):
        """
        Loads the 'Gemma 3 270M' model from the hard drive into RAM.
        """
        if self.llm is not None:
            return

        model_path = os.getenv("LOCAL_MODEL_PATH", "/models/gemma-3-270m-it-Q4_K_M.gguf")
        
        if not os.path.exists(model_path):
            # For testing environments, we don't want to crash if the model is missing
            # unless we are actually trying to use it.
            logger.warning(f"Model not found at {model_path}.")
            return

        logger.info("Loading Local AI Model...")
        
        self.llm = Llama(
            model_path=model_path,
            n_ctx=8192,
            n_gpu_layers=0,
            verbose=False
        )
        logger.info("AI Model loaded successfully.")

    def summarize(self, text):
        """
        Reads a long document and writes a 3-bullet executive summary.
        """
        self._load_model()
        if not self.llm:
            # SAFETY CHECK: Return None so the API knows not to save a "failure" result.
            return None

        safe_text = text[:30000]
        prompt = f"<bos><start_of_turn>user\nSummarize these meeting minutes into exactly 3 bullet points:\n{safe_text}<end_of_turn>\n<start_of_turn>model\n"

        # CONCURRENCY LOCK:
        # The AI brain can only think about one thing at a time.
        # We use this lock to make sure requests wait their turn in a polite line.
        with self._lock:
            try:
                # We use the raw __call__ for maximum compatibility
                response = self.llm(
                    prompt,
                    max_tokens=256,
                    temperature=0.2,
                    stop=["<end_of_turn>", "<eos>", "<|end_of_text|>"]
                )
                return response["choices"][0]["text"].strip()
            except Exception as e:
                logger.error(f"AI Summarization failed: {e}")
                return None
            finally:
                self.llm.reset()

    def extract_agenda(self, text):
        """
        Reads a document and finds the list of Agenda Items.
        """
        self._load_model()
        if not self.llm:
            return []

        safe_text = text[:30000]
        # We explicitly ask for a JSON object with an 'items' key.
        # This matches the 'json_object' grammar constraint of the AI engine.
        prompt = f"<bos><start_of_turn>user\nExtract agenda items from this text. Return a JSON object with a key 'items' containing a list of {{'title', 'description', 'classification', 'result'}} objects. 'classification' should be 'Action', 'Discussion', or 'Consent'. 'result' should be 'Passed', 'Failed', or 'Tabled':\n{safe_text}<end_of_turn>\n<start_of_turn>model\n"

        # CONCURRENCY LOCK: 
        # Prevents two users from clobbering the AI's memory at the same time.
        with self._lock:
            try:
                # We call the model and expect a valid JSON block back.
                response = self.llm(
                    prompt,
                    max_tokens=1024,
                    temperature=0.1,
                    stop=["<end_of_turn>", "<eos>", "<|end_of_text|>"]
                )
                content = response["choices"][0]["text"].strip()
                
                # Cleaning: We find the first '{' and last '}' to strip any AI chatter
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end != 0:
                    data = json.loads(content[start:end])
                    # Return the inner list: data['items']
                    return data.get("items", [])
                
                return []
            except Exception as e:
                logger.error(f"AI Segmentation failed to parse JSON: {e}")
                return []
            finally:
                # Wipe the AI's short term memory
                if self.llm:
                    self.llm.reset()