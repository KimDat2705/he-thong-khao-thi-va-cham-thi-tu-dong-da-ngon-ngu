import json
import logging
import os
import random
import time
import httpx
from google import genai
from google.genai import types
from google.genai.errors import APIError
from app.core.config import settings

logger = logging.getLogger(__name__)

# Map a recording's file extension to the mime type Gemini expects.
_AUDIO_MIME = {
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".mp3": "audio/mp3",
    ".mp4": "audio/mp4",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
}

class AIGradingService:
    def __init__(self):
        # Initialize Google GenAI if key is present
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self.model = self.client
        else:
            self.client = None
            self.model = None
            logger.warning("GEMINI_API_KEY is not set. AI Grading will run in mock mode.")

    def _call_with_retry(self, fn, *args, **kwargs):
        """
        Calls a model generation function with retry and backoff.
        Only retries on transient errors: HTTP 503 / 429 / "UNAVAILABLE" / "RESOURCE_EXHAUSTED" / timeout.
        Fails fast on permanent errors: HTTP 404, 401, 403, etc.
        """
        max_retries = getattr(settings, "GEMINI_MAX_RETRIES", 4)
        base_delay = getattr(settings, "GEMINI_RETRY_BASE_DELAY", 1.5)
        max_accumulated_delay = 20.0  # Limit total backoff time to 20 seconds
        total_sleep_time = 0.0
        
        attempt = 0
        while True:
            try:
                return fn(*args, **kwargs)
            except (APIError, httpx.TimeoutException) as e:
                # 1. Identify if it's a permanent or transient error
                if isinstance(e, APIError):
                    # We check if it is a transient error: code 503/429, status "UNAVAILABLE"/"RESOURCE_EXHAUSTED"
                    is_transient = False
                    if e.code in (429, 503):
                        is_transient = True
                    elif e.status in ("UNAVAILABLE", "RESOURCE_EXHAUSTED"):
                        is_transient = True
                    elif e.message and any(kw in e.message.upper() for kw in ("UNAVAILABLE", "RESOURCE_EXHAUSTED", "HIGH DEMAND")):
                        is_transient = True
                    
                    if not is_transient:
                        logger.warning(f"Permanent Gemini error {e.code} / {e.status}: {e}. Failing fast.")
                        raise e
                
                # If it's a transient error or httpx.TimeoutException, we retry
                attempt += 1
                if attempt > max_retries:
                    logger.error(f"Gemini API retry limit reached ({max_retries} attempts). Error: {e}")
                    raise e
                
                # Calculate backoff delay = base_delay * 2^(attempt - 1) + jitter
                jitter = random.uniform(0.0, 0.5)
                delay = base_delay * (2 ** (attempt - 1)) + jitter
                
                # Enforce total backoff limit <= 20s
                if total_sleep_time + delay > max_accumulated_delay:
                    remaining_delay = max_accumulated_delay - total_sleep_time
                    if remaining_delay > 0:
                        logger.warning(
                            f"Gemini API transient error: {e}. Delay {delay:.2f}s is capped to {remaining_delay:.2f}s "
                            f"to respect the {max_accumulated_delay}s timeout budget. Attempt {attempt}."
                        )
                        time.sleep(remaining_delay)
                        total_sleep_time += remaining_delay
                    else:
                        logger.error(f"Gemini API time budget exceeded. Cannot retry. Error: {e}")
                        raise e
                else:
                    logger.warning(f"Gemini API transient error: {e}. Retrying in {delay:.2f}s (attempt {attempt}).")
                    time.sleep(delay)
                    total_sleep_time += delay

    def grade_writing(self, essay_text: str, prompt_requirements: str, reference_answer: str = None, language: str = "EN") -> dict:
        """
        Grades an essay using Gemini API based on HSK or VSTEP rubrics.
        """
        if not self.model:
            # Mock grading for local testing
            return {
                "score": 8.0,
                "feedback": "Gemini API key missing. This is a mock feedback. Essay length: " + str(len(essay_text)),
                "grammar_errors": [{"error": "Example typo", "correction": "Example correction", "explanation": "Mock error"}]
            }

        # Build detailed prompt depending on language (English VSTEP or Chinese HSK)
        rubric = "VSTEP Writing B1-C1 Rubric (Coherence, Vocabulary, Grammar, Task Completion)" if language == "EN" else "HSK Writing 1-6 Rubric (Character Correctness, Grammar, Semantic Appropriateness)"
        
        system_instruction = (
            "You are an expert language examiner. Grade the student's essay based on the provided topic/requirements.\n"
            f"Rubric: {rubric}.\n"
            "You must return a JSON response with the following keys:\n"
            "- 'score': float (0.0 to 10.0)\n"
            "- 'feedback': string (general qualitative assessment)\n"
            "- 'grammar_errors': list of objects, each containing:\n"
            "  * 'error': string (original text)\n"
            "  * 'correction': string (suggested correction)\n"
            "  * 'explanation': string (explanation of the rule)\n"
        )
        
        user_prompt = (
            f"Topic/Requirements: {prompt_requirements}\n"
            f"Reference Answer (optional): {reference_answer}\n"
            f"Student's Essay: {essay_text}\n"
        )

        try:
            response = self._call_with_retry(
                self.model.models.generate_content,
                model=settings.GEMINI_MODEL,
                contents=[system_instruction, user_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini Writing Grading failed: {e}")
            return {
                "score": 0.0,
                "feedback": f"Grading failed due to API error: {str(e)}",
                "grammar_errors": []
            }

    def _load_audio_bytes(self, audio_url: str) -> bytes:
        """Load a recording's bytes from either a remote http(s) URL (e.g. S3) or a
        local /static path served by this backend.

        Speaking answers are uploaded to backend/static/uploads and stored as a
        relative path like "/static/uploads/xxx.webm". Calling httpx.get() on a
        relative path raises UnsupportedProtocol, so local paths are read straight
        from disk — robust on single-host deploys (Render) where a self-HTTP-fetch
        would need the public base URL.
        """
        if audio_url.startswith("http://") or audio_url.startswith("https://"):
            with httpx.Client() as client:
                resp = client.get(audio_url)
            if resp.status_code != 200:
                raise Exception(f"Failed to fetch audio file from URL: {audio_url} (status {resp.status_code})")
            return resp.content

        # Local static path -> resolve to backend/static/... on disk.
        backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        local_path = os.path.join(backend_root, *audio_url.lstrip("/").split("/"))
        if not os.path.isfile(local_path):
            raise Exception(f"Audio file not found on disk for {audio_url}")
        with open(local_path, "rb") as f:
            return f.read()

    def grade_speaking(self, audio_url: str, prompt_requirements: str, reference_answer: str = None, language: str = "EN") -> dict:
        """
        Grades spoken audio by fetching the audio file and sending it to Gemini's multimodal API.
        """
        # No recording for this question -> nothing to grade (don't crash in real mode
        # where _load_audio_bytes(None) would fail).
        if not audio_url:
            return {
                "score": 0.0,
                "transcription": "",
                "feedback": "Không có bản ghi âm cho câu này.",
                "pronunciation_issues": [],
            }

        if not self.model:
            # Mock speaking grading
            return {
                "score": 7.5,
                "transcription": "This is a mock transcription of the voice clip.",
                "feedback": "Gemini API key missing. Mock speech evaluation.",
                "pronunciation_issues": []
            }

        try:
            # Load the recording (remote URL or local /static path on disk).
            audio_bytes = self._load_audio_bytes(audio_url)

            # Formulate prompt for Speaking
            rubric = "VSTEP Speaking B1-C1 Rubric (Pronunciation, Fluency, Grammar, Content)" if language == "EN" else "HSK Speaking Rubric (Pronunciation, Tone Accuracy, Vocabulary, Fluency)"

            # Gemini 1.5 Flash supports audio directly as inline mime bytes;
            # derive the mime type from the recording's extension.
            mime_type = _AUDIO_MIME.get(os.path.splitext(audio_url)[1].lower(), "audio/webm")
            audio_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type=mime_type,
            )
            
            prompt = (
                f"You are an expert language examiner. Grade the attached student speaking recording.\n"
                f"Topic/Prompt requirements: {prompt_requirements}\n"
                f"Reference: {reference_answer}\n"
                f"Rubric: {rubric}.\n"
                "Return a JSON response with the keys:\n"
                "- 'score': float (0.0 to 10.0)\n"
                "- 'transcription': string (exact transcription of what the student said)\n"
                "- 'feedback': string (qualitative analysis on fluency, grammar, pronunciation)\n"
                "- 'pronunciation_issues': list of strings detailing specific pronunciation or tone mistakes.\n"
            )
            
            response = self._call_with_retry(
                self.model.models.generate_content,
                model=settings.GEMINI_MODEL,
                contents=[audio_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return json.loads(response.text)
            
        except Exception as e:
            logger.error(f"Gemini Speaking Grading failed: {e}")
            return {
                "score": 0.0,
                "transcription": "",
                "feedback": f"Grading failed due to API/audio download error: {str(e)}",
                "pronunciation_issues": []
            }

ai_grading_service = AIGradingService()
