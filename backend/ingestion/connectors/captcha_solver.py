"""CAPTCHA solver using 2Captcha service.

Shared by CPPP and all NIC state portal connectors.
Falls back to Tesseract OCR if no API key configured.
"""

import base64
import io
import logging
import tempfile
from typing import Optional

from PIL import Image

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def solve_captcha_image(image_data: bytes) -> Optional[str]:
    """Solve a CAPTCHA image. Returns the solution text or None.
    
    Args:
        image_data: Raw PNG/JPEG bytes of the CAPTCHA image
    
    Returns:
        Solved text string, or None if failed
    """
    api_key = settings.CAPTCHA_API_KEY

    if api_key:
        return _solve_with_2captcha(image_data, api_key)
    else:
        logger.warning("No CAPTCHA_API_KEY set — falling back to Tesseract OCR (low accuracy)")
        return _solve_with_tesseract(image_data)


def _solve_with_2captcha(image_data: bytes, api_key: str) -> Optional[str]:
    """Send CAPTCHA to 2Captcha human/ML workers."""
    try:
        from twocaptcha import TwoCaptcha

        solver = TwoCaptcha(api_key)

        # Save to temp file (2captcha SDK needs file path)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_data)
            tmp_path = f.name

        result = solver.normal(
            tmp_path,
            numeric=0,  # 0=any chars, 1=only digits, 2=only letters
            minLen=4,
            maxLen=10,
            caseSensitive=1,
            lang="en",
        )

        solution = result.get("code", "").strip()
        logger.info(f"2Captcha solved: '{solution}' (id={result.get('captchaId')})")
        return solution if solution else None

    except Exception as e:
        logger.error(f"2Captcha failed: {e}")
        return None


def _solve_with_tesseract(image_data: bytes) -> Optional[str]:
    """Fallback: try Tesseract OCR (low accuracy for NIC CAPTCHAs)."""
    try:
        import pytesseract
        from PIL import ImageFilter, ImageOps, ImageEnhance

        img = Image.open(io.BytesIO(image_data))

        # Best preprocessing strategy from our testing
        g = img.convert("L")
        g = ImageEnhance.Contrast(g).enhance(2.0)
        g = g.point(lambda x: 0 if x < 128 else 255)
        g = g.resize((g.width * 3, g.height * 3), Image.LANCZOS)
        g = g.filter(ImageFilter.MedianFilter(3))

        text = pytesseract.image_to_string(
            g,
            config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        ).strip().replace(" ", "")

        if 4 <= len(text) <= 10:
            logger.info(f"Tesseract OCR: '{text}'")
            return text

        return None

    except Exception as e:
        logger.warning(f"Tesseract fallback failed: {e}")
        return None
