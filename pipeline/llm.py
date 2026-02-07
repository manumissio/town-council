import os
import json
import logging
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

    def __new__(cls):
        """
        Singleton Pattern: This ensures we only ever load the AI model ONCE.
        Loading the model takes 1-2 seconds and uses 200MB of RAM.
        We don't want to do that for every single request!
        """
        if cls._instance is None:
            cls._instance = super(LocalAI, cls).__new__(cls)
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        """
        Loads the 'Gemma 3 270M' model from the hard drive into RAM.
        """
        model_path = "/models/gemma-3-270m-it-Q4_K_M.gguf"
        
        if not os.path.exists(model_path):
            logger.error(f"Model not found at {model_path}. Did the Docker build fail?")
            raise FileNotFoundError("AI Model file is missing.")

        logger.info("Loading Local AI Model... (This happens only once)")
        
        # Initialize the engine
        # n_ctx=8192: The "Short Term Memory" limit. It can read ~15 pages of text at once.
        # n_gpu_layers=0: We run purely on the CPU (no graphics card needed).
        # verbose=False: Hides the scary-looking C++ logs.
        # chat_format=None: We let the library auto-detect the template from the .gguf file.
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
        # Security: Truncate input to prevent memory overflows from massive files.
        # 30,000 characters is roughly 8,000 tokens (our memory limit).
        safe_text = text[:30000]

        prompt = f"""You are a helpful expert civic analyst. 
        Summarize the following meeting minutes into exactly 3 key bullet points.
        Focus on decisions, votes, and financial expenditures.
        
        TEXT:
        {safe_text}
        """

        try:
            response = self.llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256, # Limit the answer length
                temperature=0.2 # Low creativity = more factual
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"AI Summarization failed: {e}")
            return "Error generating summary."
        finally:
            # MEMORY MANAGEMENT: Flush the short-term memory.
            # If we don't do this, the next request might get confused by old data.
            self.llm.reset()

    def extract_agenda(self, text):
        """
        Reads a document and finds the list of Agenda Items.
        Returns a JSON list: [{"title": "...", "description": "..."}]
        """
        safe_text = text[:30000]
        
        prompt = f"""Extract the agenda items from this text.
        Return ONLY a raw JSON list of objects. Each object must have a 'title' and 'description'.
        Do not include markdown formatting.
        
        TEXT:
        {safe_text}
        """

        try:
            response = self.llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.1, # Very strict logic
                response_format={"type": "json_object"} # Force valid JSON output
            )
            content = response["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            logger.error(f"AI Segmentation failed: {e}")
            return []
        finally:
            self.llm.reset()
