import logging
import gemini_manager
try:
    from google import genai
except ImportError:
    pass

logger = logging.getLogger(__name__)

def generate(prompt: str, response_format: str = "text") -> str:
    """
    Central LLM Router.
    Order: 1) Groq (llama-3.3-70b-versatile) 2) Gemini (gemini-3.5-flash)
    """
    # 1. Try Groq
    total_groq = gemini_manager.get_total_groq_keys()
    last_groq_exc = None
    
    if total_groq > 0:
        for attempt in range(total_groq):
            groq_key = gemini_manager.get_current_groq_key()
            if not groq_key:
                last_groq_exc = Exception("No Groq Key available in .env")
                break
                
            try:
                from groq import Groq
                client = Groq(api_key=groq_key)
                
                # Additional prompt reinforcement for Groq
                groq_prompt = prompt + "\n\nPENTING (KHUSUS MODEL INI): WAJIB balas dalam bahasa Indonesia 100%. DILARANG pakai bahasa Inggris. Gunakan gaya bahasa netizen Threads Indonesia, santai, natural, tidak seperti AI."
                
                kwargs = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": groq_prompt}
                    ],
                    "stream": False,
                    "temperature": 0.8,
                    "max_completion_tokens": 350,
                }
                if response_format == "json":
                    kwargs["response_format"] = {"type": "json_object"}
                    
                completion = client.chat.completions.create(**kwargs)
                return completion.choices[0].message.content.strip()
                
            except Exception as e:
                last_groq_exc = e
                logger.warning(f"[LLM ROUTER] Groq failed (Key {attempt+1}/{total_groq}): {e}")
                gemini_manager.report_groq_key_exhausted()

    logger.warning(f"[LLM ROUTER] All Groq attempts failed: {last_groq_exc}. Falling back to Gemini.")

    # 2. Try Gemini
    total_gemini = gemini_manager.get_total_keys()
    last_gemini_exc = None
    
    if total_gemini > 0:
        for attempt in range(total_gemini):
            gemini_key = gemini_manager.get_current_key()
            if not gemini_key:
                last_gemini_exc = Exception("No Gemini Key available in .env")
                break
                
            try:
                client = genai.Client(api_key=gemini_key)
                
                config = {}
                if response_format == "json":
                    config["response_mime_type"] = "application/json"
                    
                gemini_manager.enforce_cooldown()
                response = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents=prompt,
                    config=config if config else None
                )
                return response.text.strip()
                
            except Exception as e:
                last_gemini_exc = e
                err_msg = str(e).upper()
                
                if gemini_manager.is_rotation_error(err_msg):
                    logger.warning(f"[LLM ROUTER] Gemini rotation error: {e}")
                    gemini_manager.report_key_exhausted()
                else:
                    logger.warning(f"[LLM ROUTER] Gemini error: {e}")
                    break

    raise Exception(f"All LLMs failed. Groq error: {last_groq_exc}. Gemini error: {last_gemini_exc}")
