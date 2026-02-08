import os
import json
import logging
import threading
import re
from llama_cpp import Llama
from pipeline.config import (
    LLM_CONTEXT_WINDOW,
    LLM_SUMMARY_MAX_TEXT,
    LLM_SUMMARY_MAX_TOKENS,
    LLM_AGENDA_MAX_TEXT,
    LLM_AGENDA_MAX_TOKENS
)

# Setup logging
logger = logging.getLogger("local-ai")

class LocalAI:
    """
    The 'Brain' of our application.

    Uses a singleton pattern to keep the model loaded in RAM.
    What's a singleton? It means only ONE instance of this class ever exists.
    Why? Loading the AI model takes ~5 seconds and uses ~500MB RAM. We don't want
    to load it multiple times!
    """
    _instance = None  # Stores the single instance
    _lock = threading.Lock()  # Prevents race conditions when multiple threads try to create the instance

    def __new__(cls):
        """
        This special method controls how new instances are created.
        Instead of creating a new instance every time, we return the same one.
        """
        # First check: Is there already an instance? (fast path, no lock needed)
        if cls._instance is None:
            # Multiple threads might reach here at the same time, so we need a lock
            with cls._lock:
                # Second check: Now that we have the lock, double-check no one else created it
                if cls._instance is None:
                    cls._instance = super(LocalAI, cls).__new__(cls)
                    cls._instance.llm = None  # Initialize the model as None (we'll load it later)
        return cls._instance

    def _load_model(self):
        """
        Loads the AI model from disk into memory.

        This is wrapped in a lock because:
        1. Loading takes several seconds
        2. If two threads try to load simultaneously, we'd waste RAM and cause errors
        3. The lock ensures only ONE thread loads the model, others wait
        """
        with self._lock:  # Acquire the lock (other threads will wait here)
            # Check if model is already loaded (another thread may have loaded it while we waited)
            if self.llm is not None:
                return  # Already loaded, nothing to do

            # Find where the model file is stored
            model_path = os.getenv("LOCAL_MODEL_PATH", "/models/gemma-3-270m-it-Q4_K_M.gguf")

            # Make sure the file actually exists
            if not os.path.exists(model_path):
                logger.warning(f"Model not found at {model_path}.")
                return  # Can't load what doesn't exist

            logger.info(f"Loading Local AI Model from {model_path}...")
            try:
                # Load the model (this is slow: ~5 seconds, ~500MB RAM)
                self.llm = Llama(
                    model_path=model_path,
                    n_ctx=LLM_CONTEXT_WINDOW,  # Maximum context size (how much text it can process at once)
                    n_gpu_layers=0,  # Don't use GPU (we want this to work on any machine)
                    verbose=False  # Don't print debug info
                )
                logger.info("AI Model loaded successfully.")
            except Exception as e:
                # AI model loading errors: Why keep this broad?
                # llama-cpp-python is an external C++ library that can raise many exception types:
                # - OSError: Model file not found or corrupted
                # - RuntimeError: CUDA/GPU errors, incompatible model format
                # - MemoryError: Model too large for available RAM
                # - ValueError: Invalid parameters (context size, layers)
                # - And potentially others from the underlying C++ code
                # DECISION: Keep broad exception handling here. It's safer to catch everything
                # than to miss a specific error type and crash the entire application.
                logger.error(f"Failed to load AI model: {e}")

    def summarize(self, text):
        """
        Generates a 3-bullet summary of meeting text using the local AI model.

        We truncate the input text to avoid exceeding the model's context window.
        """
        self._load_model()
        if not self.llm: return None

        # Truncate text to fit within model limits
        safe_text = text[:LLM_SUMMARY_MAX_TEXT]
        prompt = f"<start_of_turn>user\nSummarize these meeting minutes into 3 bullet points. No chat, just bullets:\n{safe_text}<end_of_turn>\n<start_of_turn>model\n"

        with self._lock:
            try:
                response = self.llm(prompt, max_tokens=LLM_SUMMARY_MAX_TOKENS, temperature=0.1)
                return response["choices"][0]["text"].strip()
            except Exception as e:
                # AI inference errors: Why keep this broad?
                # During text generation, the model can fail in unpredictable ways:
                # - RuntimeError: Model context overflow, generation timeout
                # - KeyError: Unexpected response format (model behavior changed)
                # - MemoryError: Generated text too large
                # - CUDA errors: GPU issues during generation
                # DECISION: Catch all errors and return None. The caller handles gracefully.
                # Better to skip summarization than crash the entire pipeline.
                logger.error(f"AI Summarization failed: {e}")
                return None
            finally:
                if self.llm: self.llm.reset()

    def extract_agenda(self, text):
        """
        Extracts individual agenda items from meeting text using the local AI model.

        Returns a list of agenda items with titles, page numbers, and descriptions.
        """
        self._load_model()

        items = []
        if self.llm:
            # We increase context slightly to catch more items, focusing on the start
            safe_text = text[:LLM_AGENDA_MAX_TEXT]
            
            # PROMPT: We now ask for Page numbers and a clean list.
            # We explicitly tell it to ignore boilerplate and headers.
            prompt = (
                "<start_of_turn>user\n"
                "Extract ONLY the real agenda items from this meeting document. "
                "Include the page number where each item starts. "
                "Format: ITEM [Order]: [Title] (Page [X]) - [Brief Summary]\n\n"
                f"Text:\n{safe_text}<end_of_turn>\n"
                "<start_of_turn>model\n"
                "ITEM 1:"
            )
            
            with self._lock:
                try:
                    response = self.llm(prompt, max_tokens=LLM_AGENDA_MAX_TOKENS, temperature=0.1)
                    raw_content = response["choices"][0]["text"].strip()
                    content = "ITEM 1:" + raw_content
                    pattern = r"ITEM\s+(\d+):\s*(.*?)\s*\(Page\s*(\d+)\)\s*-\s*(.*)"
                    
                    for line in content.split("\n"):
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            order = int(match.group(1))
                            title = match.group(2).strip()
                            page = int(match.group(3))
                            desc = match.group(4).strip()
                            
                            # Validation: Skip generic items
                            blacklist = ['call to order', 'roll call', 'adjournment', 'pledge of allegiance']
                            if any(b in title.lower() for b in blacklist):
                                continue

                            if len(title) > 5:
                                items.append({
                                    "order": order,
                                    "title": title,
                                    "page_number": page,
                                    "description": desc,
                                    "classification": "Agenda Item",
                                    "result": ""
                                })
                except Exception as e:
                    # AI agenda extraction errors: Same rationale as above
                    # The model can fail during generation, response parsing, or regex matching
                    # DECISION: Log the error but return partial results (items extracted so far)
                    # rather than crashing. The fallback heuristic will catch items anyway.
                    logger.error(f"AI Agenda Extraction failed: {e}")
                finally:
                    if self.llm: self.llm.reset()

        # FALLBACK: If AI fails, use a smarter paragraph splitter that looks for page markers
        if not items:
            # Split by [PAGE X]
            page_splits = re.split(r'\[PAGE (\d+)\]', text)
            
            # page_splits format: [pre-text, "1", page1_text, "2", page2_text...]
            # We skip the first element (pre-text)
            for i in range(1, len(page_splits), 2):
                page_num = int(page_splits[i])
                page_content = page_splits[i+1].strip()
                
                # Look for bold-looking lines or short starting lines
                # We split by double newline and filter for likely headers
                paragraphs = [p.strip() for p in page_content.split("\n\n") if 10 < len(p.strip()) < 1000]
                
                for p in paragraphs:
                    lines = p.split("\n")
                    if not lines: continue
                    title = lines[0].strip()
                    
                    # Heuristic: If it's short, capitalized, or starts with a number, it's likely a title
                    if 10 < len(title) < 150 and not any(b in title.lower() for b in ['page', 'item', 'packet', 'continuing']):
                        items.append({
                            "order": len(items) + 1,
                            "title": title,
                            "page_number": page_num,
                            "description": (p[:500] + "...") if len(p) > 500 else p,
                            "classification": "Agenda Item",
                            "result": ""
                        })
                        # Limit to 3 items per page to reduce noise in fallback
                        if len([it for it in items if it['page_number'] == page_num]) >= 3:
                            break
                            
                if len(items) > 30: break # Cap total items per doc
        
        return items
