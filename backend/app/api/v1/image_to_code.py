import base64
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_verified_tenant
from app.models.tenant import Tenant
from app.services.image_to_code_service import (
    ImageToCodeError,
    generate_code_from_image,
    generate_image_from_prompt,
    generate_code_from_generated_image,
    improve_generated_code,
)

router = APIRouter()

MAX_IMAGE_SIZE = 20 * 1024 * 1024

ALLOWED_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}


def provider_error(error: ImageToCodeError):
    raise HTTPException(status_code=502, detail=str(error))


class TextToImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    gemini_api_key: str = Field(min_length=1)
    pollinations_api_key: str = Field(min_length=1)
    output_type: str = "HTML"


class ImproveCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100000)
    instruction: str = Field(min_length=1, max_length=2000)
    gemini_api_key: str = Field(min_length=1)
    output_type: str = "HTML"


@router.post("/from-image")
async def image_to_code(
    image: UploadFile = File(...),
    gemini_api_key: str = Form(...),
    output_type: str = Form("HTML"),
    tenant: Tenant = Depends(get_verified_tenant),
):
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Upload a PNG, JPG, or WEBP image.",
        )

    image_bytes = await image.read(MAX_IMAGE_SIZE + 1)

    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image size must not exceed 20 MB.",
        )

    try:
        code = await generate_code_from_image(
            api_key=gemini_api_key,
            image_bytes=image_bytes,
            mime_type=image.content_type,
            output_type=output_type,
        )
        return {
            "success": True,
            "code": code,
            "output_type": output_type,
        }
    except ImageToCodeError as error:
        provider_error(error)


@router.post("/from-text")
async def text_to_image_and_code(
    request: TextToImageRequest,
    tenant: Tenant = Depends(get_verified_tenant),
):
    try:
        image_bytes = await generate_image_from_prompt(
            prompt=request.prompt,
            api_key=request.pollinations_api_key,
        )

        code = await generate_code_from_generated_image(
            api_key=request.gemini_api_key,
            image_bytes=image_bytes,
            output_type=request.output_type,
        )

        return {
            "success": True,
            "image": (
                "data:image/png;base64,"
                + base64.b64encode(image_bytes).decode("utf-8")
            ),
            "code": code,
            "output_type": request.output_type,
        }

    except ImageToCodeError as error:
        provider_error(error)


@router.post("/improve")
async def improve_code(
    request: ImproveCodeRequest,
    tenant: Tenant = Depends(get_verified_tenant),
):
    try:
        improved_code = await improve_generated_code(
            api_key=request.gemini_api_key,
            code=request.code,
            instruction=request.instruction,
            output_type=request.output_type,
        )

        return {
            "success": True,
            "code": improved_code,
        }

    except ImageToCodeError as error:
        provider_error(error)
        