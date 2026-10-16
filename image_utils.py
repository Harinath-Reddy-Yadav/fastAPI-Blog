import uuid
from io import BytesIO
from PIL import Image, ImageOps
from pathlib import Path


PROFILE_PICS_DIR = Path("media/profile_pics")


def process_profile_picture(contnet: bytes) -> str:
    with Image.open(BytesIO(contnet)) as original:
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
        save_path = PROFILE_PICS_DIR / filename
        PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)
        img.save(save_path, format="jpeg", quality=85, optimize=True)

    return filename

#Delete profile pic
def delete_profile_picture(filename: str | None) -> None:
    if filename is None:
        return
    file_path = PROFILE_PICS_DIR / filename  
    if file_path.exists():
        file_path.unlink()  #pathlib way of deletion

#