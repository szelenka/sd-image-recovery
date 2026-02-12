"""Device detection and safety checks for macOS."""

import subprocess
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

from ..utils.errors import (
    DeviceNotFoundError,
    UnsafeDeviceError,
    MountError,
)
from ..utils.validation import format_size

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """Information about a storage device."""
    device_path: str
    raw_device_path: str
    size_bytes: int
    size_human: str
    filesystem: Optional[str]
    mount_point: Optional[str]
    device_number: int
    is_internal: bool
    is_removable: bool
    volume_name: Optional[str]


def get_all_devices() -> List[DeviceInfo]:
    """Get information about all storage devices.

    Returns:
        List of DeviceInfo objects

    Raises:
        DeviceNotFoundError: If diskutil command fails
    """
    try:
        result = subprocess.run(
            ['diskutil', 'list', '-plist'],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse diskutil output to get device list
        devices = []

        # Get simple list first
        result_simple = subprocess.run(
            ['diskutil', 'list'],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse each disk device
        disk_pattern = re.compile(r'/dev/(disk\d+)')
        for match in disk_pattern.finditer(result_simple.stdout):
            device = match.group(1)
            try:
                device_info = get_device_info(f"/dev/{device}")
                devices.append(device_info)
            except Exception as e:
                logger.debug(f"Could not get info for {device}: {e}")
                continue

        return devices

    except subprocess.CalledProcessError as e:
        raise DeviceNotFoundError(f"Failed to list devices: {e.stderr}")
    except Exception as e:
        raise DeviceNotFoundError(f"Error listing devices: {e}")


def get_device_info(device_path: str) -> DeviceInfo:
    """Get detailed information about a specific device.

    Args:
        device_path: Path to device (e.g., /dev/disk2)

    Returns:
        DeviceInfo object

    Raises:
        DeviceNotFoundError: If device not found
    """
    try:
        # Get device information from diskutil
        result = subprocess.run(
            ['diskutil', 'info', device_path],
            capture_output=True,
            text=True,
            check=True
        )

        info = {}
        for line in result.stdout.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                info[key.strip()] = value.strip()

        # Extract device number (e.g., 2 from /dev/disk2)
        device_match = re.search(r'disk(\d+)', device_path)
        device_number = int(device_match.group(1)) if device_match else -1

        # Determine if device is internal or removable
        is_internal = info.get('Device Location', '').lower() == 'internal'
        is_removable = info.get('Removable Media', '').lower() == 'removable'
        protocol = info.get('Protocol', '').lower()

        # USB devices are considered removable
        if 'usb' in protocol:
            is_removable = True
            is_internal = False

        # Parse size
        size_str = info.get('Disk Size', '0 B')
        size_bytes = parse_size(size_str)

        # Get filesystem and mount point
        filesystem = info.get('File System Personality') or info.get('Type (Bundle)')
        mount_point = info.get('Mount Point')
        volume_name = info.get('Volume Name')

        # Convert to raw device path if needed
        raw_device_path = device_path.replace('/dev/disk', '/dev/rdisk')

        return DeviceInfo(
            device_path=device_path,
            raw_device_path=raw_device_path,
            size_bytes=size_bytes,
            size_human=format_size(size_bytes),
            filesystem=filesystem,
            mount_point=mount_point,
            device_number=device_number,
            is_internal=is_internal,
            is_removable=is_removable,
            volume_name=volume_name,
        )

    except subprocess.CalledProcessError as e:
        raise DeviceNotFoundError(f"Device not found: {device_path}")
    except Exception as e:
        raise DeviceNotFoundError(f"Error getting device info: {e}")


def is_safe_device(device_info: DeviceInfo, max_size_gb: int = 512) -> tuple[bool, Optional[str]]:
    """Check if device is safe to access for recovery.

    Args:
        device_info: DeviceInfo object to check
        max_size_gb: Maximum size in GB for SD card (safety check)

    Returns:
        Tuple of (is_safe, reason_if_unsafe)
    """
    # Block disk0 and disk1 (typically internal disks)
    if device_info.device_number <= 1:
        return False, f"Device {device_info.device_path} appears to be an internal disk (disk0/disk1)"

    # Check if marked as internal
    if device_info.is_internal:
        return False, f"Device {device_info.device_path} is marked as internal"

    # Warn if device is very large (unlikely to be SD card)
    max_size_bytes = max_size_gb * 1024 * 1024 * 1024
    if device_info.size_bytes > max_size_bytes:
        return False, f"Device {device_info.device_path} is larger than {max_size_gb}GB ({device_info.size_human})"

    # Prefer removable devices
    if not device_info.is_removable:
        return False, f"Device {device_info.device_path} is not marked as removable"

    return True, None


def unmount_device(device_path: str) -> bool:
    """Unmount a device.

    Args:
        device_path: Path to device to unmount

    Returns:
        True if successful

    Raises:
        MountError: If unmount fails
    """
    try:
        logger.info(f"Unmounting {device_path}")
        result = subprocess.run(
            ['diskutil', 'unmountDisk', device_path],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Successfully unmounted {device_path}")
        return True

    except subprocess.CalledProcessError as e:
        raise MountError(f"Failed to unmount {device_path}: {e.stderr}")


def mount_device(device_path: str) -> bool:
    """Mount a device.

    Args:
        device_path: Path to device to mount

    Returns:
        True if successful

    Raises:
        MountError: If mount fails
    """
    try:
        logger.info(f"Mounting {device_path}")
        result = subprocess.run(
            ['diskutil', 'mountDisk', device_path],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Successfully mounted {device_path}")
        return True

    except subprocess.CalledProcessError as e:
        # Don't raise error if already mounted
        if "already mounted" in e.stderr.lower():
            logger.info(f"{device_path} is already mounted")
            return True
        raise MountError(f"Failed to mount {device_path}: {e.stderr}")


def parse_size(size_str: str) -> int:
    """Parse a size string to bytes.

    Args:
        size_str: Size string (e.g., "32.0 GB", "500 MB")

    Returns:
        Size in bytes
    """
    # Remove parentheses and extract number and unit
    size_str = size_str.replace('(', '').replace(')', '').strip()

    match = re.search(r'([\d.]+)\s*([KMGTP]?B)', size_str, re.IGNORECASE)
    if not match:
        return 0

    number = float(match.group(1))
    unit = match.group(2).upper()

    units = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 ** 2,
        'GB': 1024 ** 3,
        'TB': 1024 ** 4,
        'PB': 1024 ** 5,
    }

    return int(number * units.get(unit, 1))


def format_device_info(device_info: DeviceInfo) -> str:
    """Format device information for display.

    Args:
        device_info: DeviceInfo object

    Returns:
        Formatted string
    """
    lines = [
        f"Device: {device_info.device_path}",
        f"Raw Device: {device_info.raw_device_path}",
        f"Size: {device_info.size_human}",
    ]

    if device_info.volume_name:
        lines.append(f"Volume Name: {device_info.volume_name}")

    if device_info.filesystem:
        lines.append(f"Filesystem: {device_info.filesystem}")

    if device_info.mount_point:
        lines.append(f"Mount Point: {device_info.mount_point}")

    lines.extend([
        f"Removable: {'Yes' if device_info.is_removable else 'No'}",
        f"Internal: {'Yes' if device_info.is_internal else 'No'}",
    ])

    return '\n'.join(lines)
