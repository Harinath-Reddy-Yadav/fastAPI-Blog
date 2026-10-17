from boto3 import client
import uuid
from io import BytesIO
from PIL import Image, ImageOps
from config import settings
import boto3
from starlette.concurrency import run_in_threadpool



#S3 client helper function which will create a singleton instance
def _get_s3_client():
    """
    Helper function to get S3 client
    """
    return boto3.client(
        "s3",
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID.get_secret_value() if settings.S3_ACCESS_KEY_ID else None,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY.get_secret_value() if settings.S3_SECRET_ACCESS_KEY else None,
        endpoint_url=settings.s3_endpoint_url
    )

s3_client = _get_s3_client()

def process_profile_picture(content: bytes) -> tuple[bytes, str]:
    with Image.open(BytesIO(content)) as original:
        img = ImageOps.exif_transpose(original)
        img = ImageOps.fit(img, (250, 250), Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert("RGB")

        filename = f"{uuid.uuid4()}.jpg"
        buffer = BytesIO()
        img.save(buffer, format="jpeg", quality=85, optimize=True)
        buffer.seek(0)

    return buffer.read(), filename



#upload to S3 helper function
def _upload_to_s3_object(file_bytes: bytes, file_name: str):
    s3_client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=file_name,
        Body=file_bytes,
        ContentType="image/jpeg"
    )


#Delete from s3 helper function
def _delete_from_s3(file_name: str) -> None:
    s3_client.delete_object (
        Bucket=settings.S3_BUCKET_NAME,
        Key=file_name
    )
    return None

#Create the functions for the async app
async def upload_profile_image(file_bytes: bytes, file_name: str) -> None:
    """
    Upload an image to S3
    """
    key = f"profile_pics/{file_name}"
    await run_in_threadpool(_upload_to_s3_object, file_bytes, key)

async def delete_profile_image(file_name: str) -> None:
    """
    Delete an image from s3
    """
    if file_name is None:
        return None
    key = f"profile_pics/{file_name}"
    await run_in_threadpool(_delete_from_s3, key)