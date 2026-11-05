import base64
import httpx
from typing import Optional


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

PREFERRED_VISION_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]

POLLINATIONS_URL = "https://gen.pollinations.ai/image/"


class ImageToCodeError(Exception):
    pass

async def discover_gemini_models(api_key: str) -> list[str]:
    if not api_key or not api_key.strip():
        raise ImageToCodeError("Please enter your Gemini API key.")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{GEMINI_BASE_URL}/models",
                params={
                    "key": api_key.strip(),
                    "pageSize": 100,
                },
            )

        if response.is_error:
            try:
                detail = response.json().get("error", {}).get("message", "")
            except ValueError:
                detail = ""
            raise ImageToCodeError(
                detail or f"Gemini model discovery failed (HTTP {response.status_code})."
            )

        data = response.json()
        available_models = [
            model.get("name", "").replace("models/", "")
            for model in data.get("models", [])
            if "generateContent" in model.get("supportedGenerationMethods", [])
        ]

        preferred = [
            model for model in PREFERRED_VISION_MODELS
            if model in available_models
        ]

        if preferred:
            return preferred

        gemini_models = [
            model for model in available_models
            if "gemini" in model.lower()
            and "embedding" not in model.lower()
            and "aqa" not in model.lower()
        ]

        if gemini_models:
            return gemini_models

        raise ImageToCodeError(
            "No Gemini models supporting generateContent were found for this API key."
        )

    except httpx.TimeoutException:
        raise ImageToCodeError("Gemini model discovery timed out.")
    except httpx.RequestError:
        raise ImageToCodeError("Could not connect to Gemini. Check your internet connection.")


async def call_gemini(
    api_key: str,
    prompt: str,
    image_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None,
) -> str:

    models = await discover_gemini_models(api_key)

    parts = [{"text": prompt}]

    if image_bytes:
        parts.append({
            "inline_data": {
                "mime_type": mime_type or "image/png",
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }
        })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.15,
            "topP": 0.9,
            "maxOutputTokens": 8192,
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        for model in models:
            try:
                response = await client.post(
                    f"{GEMINI_BASE_URL}/models/{model}:generateContent",
                    params={"key": api_key.strip()},
                    json=payload,
                )

                if response.status_code in (404, 410):
                    continue

                if response.is_error:
                    try:
                        detail = response.json().get("error", {}).get("message", "")
                    except ValueError:
                        detail = ""

                    raise ImageToCodeError(
                        detail or f"Gemini request failed (HTTP {response.status_code})."
                    )

                data = response.json()
                candidates = data.get("candidates", [])

                if not candidates:
                    continue

                result_parts = candidates[0].get("content", {}).get("parts", [])

                result = "\n".join(
                    part.get("text", "")
                    for part in result_parts
                    if part.get("text")
                ).strip()

                if result:
                    return result

            except httpx.TimeoutException:
                raise ImageToCodeError("Gemini request timed out. Please try again.")
            except httpx.RequestError:
                raise ImageToCodeError(
                    "Could not connect to Gemini. Check your internet connection."
                )

    raise ImageToCodeError(
        "None of the available Gemini models returned a response. "
        "Check your API key and model access."
    )
    
async def generate_code_from_image(
    api_key: str,
    prompt: str,
    image_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None,
) -> str:
    if not api_key or not api_key.strip():
        raise ImageToCodeError("Please enter your Gemini API key.")

    parts = [{"text": prompt}]

    if image_bytes:
        parts.append({
            "inline_data": {
                "mime_type": mime_type or "image/png",
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }
        })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                GEMINI_URL,
                params={"key": api_key.strip()},
                json=payload,
            )

        if response.is_error:
            try:
                detail = response.json().get("error", {}).get("message", "")
            except ValueError:
                detail = ""

            raise ImageToCodeError(
                detail or f"Gemini request failed (HTTP {response.status_code})."
            )

        data = response.json()
        candidates = data.get("candidates", [])

        if not candidates:
            raise ImageToCodeError(
                "Gemini did not return a code response. Try another image or prompt."
            )

        result_parts = candidates[0].get("content", {}).get("parts", [])
        result = "\n".join(
            part.get("text", "")
            for part in result_parts
            if part.get("text")
        ).strip()

        if not result:
            raise ImageToCodeError("Gemini returned an empty response.")

        return result

    except httpx.TimeoutException:
        raise ImageToCodeError("Gemini request timed out. Please try again.")
    except httpx.RequestError:
        raise ImageToCodeError("Could not connect to Gemini. Check your internet connection.")


async def generate_code_from_image(
    api_key: str,
    image_bytes: bytes,
    mime_type: str,
    output_type: str = "HTML",
) -> str:
    prompt = f"""
You are an expert frontend developer.

Analyse the supplied image and recreate its visible design as closely as possible.

Requested output format: {output_type}

Requirements:
- Generate working code, not an explanation.
- For HTML, provide a complete standalone HTML document.
- Include CSS and JavaScript inside the HTML document when appropriate.
- Match the layout, colours, typography, spacing, borders, and visible components.
- Use responsive CSS.
- Use placeholders for assets that cannot be extracted from the screenshot.
- Do not claim that unavailable image assets were recovered.
- Do not use Markdown code fences.
- Return only the generated code.
"""
    return await call_gemini(api_key, prompt, image_bytes, mime_type)


async def generate_image_from_prompt(
    prompt: str,
    api_key: str,
    width: int = 1024,
    height: int = 1024,
) -> bytes:
    if not api_key or not api_key.strip():
        raise ImageToCodeError("Please enter your Pollinations API key.")

    if not prompt or not prompt.strip():
        raise ImageToCodeError("Please enter an image description.")

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.get(
                POLLINATIONS_URL + prompt.strip(),
                params={
                    "model": "flux",
                    "width": width,
                    "height": height,
                    "nologo": "true",
                },
                headers={
                    "Authorization": f"Bearer {api_key.strip()}",
                },
            )

        if response.is_error:
            raise ImageToCodeError(
                f"Pollinations image generation failed (HTTP {response.status_code}). "
                "Check your API key and try again."
            )

        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            raise ImageToCodeError("Pollinations did not return a valid image.")

        return response.content

    except httpx.TimeoutException:
        raise ImageToCodeError("Image generation timed out. Please try again.")
    except httpx.RequestError:
        raise ImageToCodeError(
            "Could not connect to Pollinations. Check your internet connection."
        )


async def generate_code_from_generated_image(
    api_key: str,
    image_bytes: bytes,
    output_type: str = "HTML",
) -> str:
    return await generate_code_from_image(
        api_key=api_key,
        image_bytes=image_bytes,
        mime_type="image/png",
        output_type=output_type,
    )


async def improve_generated_code(
    api_key: str,
    code: str,
    instruction: str,
    output_type: str = "HTML",
) -> str:
    prompt = f"""
You are an expert frontend developer.

Improve the following {output_type} code according to the user's instruction.

USER INSTRUCTION:
{instruction}

EXISTING CODE:
{code}

Rules:
- Preserve existing functionality unless the user asks to change it.
- Return the complete updated code.
- Do not return explanations or Markdown code fences.
"""
    return await call_gemini(api_key, prompt)