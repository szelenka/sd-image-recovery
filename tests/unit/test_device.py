"""Unit tests for device detection module."""

import subprocess
import pytest
from unittest.mock import patch, MagicMock
from sd_recovery.core.device import (
    get_device_info,
    is_safe_device,
    parse_size,
    DeviceInfo,
)
from sd_recovery.utils.errors import DeviceNotFoundError


class TestParseSize:
    """Test size parsing function."""

    def test_parse_bytes(self):
        assert parse_size("1024 B") == 1024

    def test_parse_kb(self):
        assert parse_size("1 KB") == 1024

    def test_parse_mb(self):
        assert parse_size("100 MB") == 100 * 1024 * 1024

    def test_parse_gb(self):
        assert parse_size("32 GB") == 32 * 1024 * 1024 * 1024

    def test_parse_with_decimal(self):
        assert parse_size("1.5 GB") == int(1.5 * 1024 * 1024 * 1024)

    def test_parse_invalid(self):
        assert parse_size("invalid") == 0


class TestIsSafeDevice:
    """Test device safety checks."""

    def test_disk0_unsafe(self):
        device = DeviceInfo(
            device_path="/dev/disk0",
            raw_device_path="/dev/rdisk0",
            size_bytes=500 * 1024**3,
            size_human="500 GB",
            filesystem="APFS",
            mount_point=None,
            device_number=0,
            is_internal=True,
            is_removable=False,
            volume_name=None
        )
        is_safe, reason = is_safe_device(device)
        assert not is_safe
        assert "internal disk" in reason.lower()

    def test_disk1_unsafe(self):
        device = DeviceInfo(
            device_path="/dev/disk1",
            raw_device_path="/dev/rdisk1",
            size_bytes=500 * 1024**3,
            size_human="500 GB",
            filesystem="APFS",
            mount_point=None,
            device_number=1,
            is_internal=True,
            is_removable=False,
            volume_name=None
        )
        is_safe, reason = is_safe_device(device)
        assert not is_safe

    def test_internal_device_unsafe(self):
        device = DeviceInfo(
            device_path="/dev/disk2",
            raw_device_path="/dev/rdisk2",
            size_bytes=32 * 1024**3,
            size_human="32 GB",
            filesystem="FAT32",
            mount_point=None,
            device_number=2,
            is_internal=True,  # Marked as internal
            is_removable=False,
            volume_name=None
        )
        is_safe, reason = is_safe_device(device)
        assert not is_safe
        assert "internal" in reason.lower()

    def test_large_device_unsafe(self):
        device = DeviceInfo(
            device_path="/dev/disk2",
            raw_device_path="/dev/rdisk2",
            size_bytes=1024 * 1024**3,  # 1TB
            size_human="1 TB",
            filesystem="FAT32",
            mount_point=None,
            device_number=2,
            is_internal=False,
            is_removable=True,
            volume_name=None
        )
        is_safe, reason = is_safe_device(device)
        assert not is_safe
        assert "larger than" in reason.lower()

    def test_non_removable_unsafe(self):
        device = DeviceInfo(
            device_path="/dev/disk2",
            raw_device_path="/dev/rdisk2",
            size_bytes=32 * 1024**3,
            size_human="32 GB",
            filesystem="FAT32",
            mount_point=None,
            device_number=2,
            is_internal=False,
            is_removable=False,  # Not removable
            volume_name=None
        )
        is_safe, reason = is_safe_device(device)
        assert not is_safe
        assert "not marked as removable" in reason.lower()

    def test_safe_sd_card(self):
        device = DeviceInfo(
            device_path="/dev/disk2",
            raw_device_path="/dev/rdisk2",
            size_bytes=32 * 1024**3,
            size_human="32 GB",
            filesystem="FAT32",
            mount_point=None,
            device_number=2,
            is_internal=False,
            is_removable=True,
            volume_name="SD_CARD"
        )
        is_safe, reason = is_safe_device(device)
        assert is_safe
        assert reason is None


@patch('sd_recovery.core.device.subprocess.run')
class TestGetDeviceInfo:
    """Test device information retrieval."""

    def test_get_device_info_success(self, mock_run):
        # Mock diskutil output
        mock_run.return_value = MagicMock(
            stdout="""
   Device Identifier:        disk2
   Device Node:              /dev/disk2
   Disk Size:                32.0 GB (32017047552 Bytes)
   Device Location:          External
   Removable Media:          Removable
   Protocol:                 USB
   File System Personality:  MS-DOS FAT32
   Volume Name:              SD_CARD
            """,
            returncode=0
        )

        device_info = get_device_info("/dev/disk2")

        assert device_info.device_path == "/dev/disk2"
        assert device_info.raw_device_path == "/dev/rdisk2"
        assert device_info.device_number == 2
        assert not device_info.is_internal
        assert device_info.is_removable
        assert device_info.filesystem == "MS-DOS FAT32"
        assert device_info.volume_name == "SD_CARD"

    def test_get_device_info_not_found(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, 'diskutil', stderr="Device not found")

        with pytest.raises(DeviceNotFoundError):
            get_device_info("/dev/disk99")
