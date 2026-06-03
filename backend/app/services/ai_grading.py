import json
import logging
import httpx
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)

class AIGradingService:
    def __init__(self):
        # Initialize Google GenAI if key is present
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None
            logger.warning("GEMINI_API_KEY is not set. AI Grading will run in mock mode.")

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
            response = self.model.generate_content(
                contents=[system_instruction, user_prompt],
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini Writing Grading failed: {e}")
            return {
                "score": 0.0,
                "feedback": f"Grading failed due to API error: {str(e)}",
                "grammar_errors": []
            }

    def grade_speaking(self, audio_url: str, prompt_requirements: str, reference_answer: str = None, language: str = "EN") -> dict:
        """
        Grades spoken audio by fetching the audio file and sending it to Gemini's multimodal API.
        """
        if not self.model:
            # Mock speaking grading
            return {
                "score": 7.5,
                "transcription": "This is a mock transcription of the voice clip.",
                "feedback": "Gemini API key missing. Mock speech evaluation.",
                "pronunciation_issues": []
            }

        try:
            # Download audio file from the storage URL (e.g. S3, local storage)
            async_client = httpx.Client()
            audio_response = async_client.get(audio_url)
            if audio_response.status_code != 200:
                raise Exception(f"Failed to fetch audio file from URL: {audio_url}")
            
            audio_bytes = audio_response.content
            
            # Formulate prompt for Speaking
            rubric = "VSTEP Speaking B1-C1 Rubric (Pronunciation, Fluency, Grammar, Content)" if language == "EN" else "HSK Speaking Rubric (Pronunciation, Tone Accuracy, Vocabulary, Fluency)"
            
            # Gemini 1.5 Flash supports audio directly as inline mime bytes
            audio_part = {
                "mime_type": "audio/webm",  # Or audio/wav, audio/mp3 based on recording format
                "data": audio_bytes
            }
            
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
            
            response = self.model.generate_content(
                contents=[audio_part, prompt],
                generation_config={"response_mime_type": "application/json"}
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
