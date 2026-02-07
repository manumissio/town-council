import os
import json
import logging
import threading
import re
from llama_cpp import Llama

# Setup logging
logger = logging.getLogger("local-ai")

class LocalAI:
    """
    The 'Brain' of our application.
    Uses a singleton pattern to keep the model loaded in RAM.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LocalAI, cls).__new__(cls)
                    cls._instance.llm = None
        return cls._instance

    def _load_model(self):
        if self.llm is not None:
            return

        model_path = os.getenv("LOCAL_MODEL_PATH", "/models/gemma-3-270m-it-Q4_K_M.gguf")
        
        if not os.path.exists(model_path):
            logger.warning(f"Model not found at {model_path}.")
            return

        logger.info(f"Loading Local AI Model from {model_path}...")
        try:
            self.llm = Llama(
                model_path=model_path,
                n_ctx=2048,
                n_gpu_layers=0,
                verbose=False
            )
            logger.info("AI Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load AI model: {e}")

    def summarize(self, text):
        self._load_model()
        if not self.llm: return None

        safe_text = text[:4000]
        prompt = f"<start_of_turn>user\nSummarize these meeting minutes into 3 bullet points. No chat, just bullets:\n{safe_text}<end_of_turn>\n<start_of_turn>model\n"

        with self._lock:
            try:
                response = self.llm(prompt, max_tokens=256, temperature=0.1)
                return response["choices"][0]["text"].strip()
            except Exception as e:
                logger.error(f"AI Summarization failed: {e}")
                return None
            finally:
                if self.llm: self.llm.reset()

    def extract_agenda(self, text):
        self._load_model()
        
        items = []
        if self.llm:
            safe_text = text[:3000]
            prompt = f"<start_of_turn>user\nExtract meeting topics. Format each as '* Title - Description'. No extra chat.\nText: {safe_text}<end_of_turn>\n<start_of_turn>model\n* "
            
            with self._lock:
                try:
                    response = self.llm(prompt, max_tokens=1024, temperature=0.1)
                    content = "* " + response["choices"][0]["text"].strip()
                    
                    for line in content.split("\n"):
                        if line.startswith("*"):
                            # Strip markdown artifacts
                            clean_line = line.replace("**", "").replace("__", "")
                            parts = clean_line[1:].split("-", 1)
                            title = parts[0].strip()
                            # Extra cleaning for the '*' if it was caught in the split
                            if title.startswith("*"): title = title[1:].strip()
                            
                            desc = parts[1].strip() if len(parts) > 1 else ""
                            if len(title) > 5:
                                items.append({
                                    "title": title,
                                    "description": desc,
                                    "classification": "Discussion",
                                    "result": ""
                                })
                except Exception as e:
                    logger.error(f"AI Extraction failed: {e}")
                finally:
                    if self.llm: self.llm.reset()

        if not items:
            paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 20]
            for p in paragraphs[:10]:
                lines = p.split("\n")
                title = lines[0].replace("**", "").replace("__", "")[:100]
                items.append({
                    "title": title,
                    "description": p,
                    "classification": "Discussion",
                    "result": ""
                })
        
        return items
