"""File validation utilities."""

from pathlib import Path
from typing import Dict, Optional, Tuple
from PIL import Image
import logging

from .errors import ValidationError

logger = logging.getLogger(__name__)


def validate_jpeg(file_path: Path) -> Tuple[bool, Optional[Dict]]:
    """Validate a JPEG file and extract metadata.

    Args:
        file_path: Path to JPEG file

    Returns:
        Tuple of (is_valid, metadata_dict)
        metadata_dict contains: width, height, format, mode, size_bytes
    """
    try:
        with Image.open(file_path) as img:
            # Verify it's actually a JPEG
            if img.format not in ('JPEG', 'JPG'):
                return False, None

            # Extract basic metadata
            metadata = {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode,
                'size_bytes': file_path.stat().st_size,
            }

            # Try to extract EXIF data
            try:
                exif = img.getexif()
                if exif:
                    metadata['has_exif'] = True
                    # Add some common EXIF tags if present
                    # 0x0132: DateTime, 0x010F: Make, 0x0110: Model
                    if 0x0132 in exif:
                        metadata['datetime'] = str(exif[0x0132])
                    if 0x010F in exif:
                        metadata['camera_make'] = str(exif[0x010F])
                    if 0x0110 in exif:
                        metadata['camera_model'] = str(exif[0x0110])
                else:
                    metadata['has_exif'] = False
            except Exception as e:
                logger.debug(f"Could not extract EXIF from {file_path}: {e}")
                metadata['has_exif'] = False

            # Verify image can be loaded (basic corruption check)
            img.verify()

            return True, metadata

    except (IOError, OSError) as e:
        logger.debug(f"Failed to validate {file_path}: {e}")
        return False, None
    except Exception as e:
        logger.warning(f"Unexpected error validating {file_path}: {e}")
        return False, None


def is_suspicious_jpeg(metadata: Optional[Dict]) -> bool:
    """Check if JPEG metadata indicates potential issues.

    Args:
        metadata: Metadata dictionary from validate_jpeg

    Returns:
        True if file seems suspicious/corrupted
    """
    if not metadata:
        return True

    # Check for unusually small images (likely corrupted)
    if metadata.get('width', 0) < 10 or metadata.get('height', 0) < 10:
        return True

    # Check for unusually small file size (less than 1KB)
    if metadata.get('size_bytes', 0) < 1024:
        return True

    # Check for unusual aspect ratios (possible corruption)
    width = metadata.get('width', 1)
    height = metadata.get('height', 1)
    aspect_ratio = max(width, height) / min(width, height)
    if aspect_ratio > 10:  # Extremely tall or wide
        return True

    return False


def validate_device_path(device_path: str) -> Path:
    """Validate and normalize device path.

    Args:
        device_path: Device path string (e.g., /dev/disk2 or /dev/rdisk2)

    Returns:
        Normalized Path object

    Raises:
        ValidationError: If path is invalid
    """
    path = Path(device_path)

    # Check if it's a device path
    if not str(path).startswith('/dev/'):
        raise ValidationError(f"Not a valid device path: {device_path}")

    # For disk images, allow regular files
    if path.suffix in ('.img', '.dmg', '.iso'):
        if not path.exists():
            raise ValidationError(f"Disk image not found: {device_path}")
        return path

    # For real devices, check if it exists
    if not path.exists():
        raise ValidationError(f"Device not found: {device_path}")

    return path


def format_size(size_bytes: int) -> str:
    """Format byte size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"
