"""Unit tests for output organizer."""

import pytest
from pathlib import Path
import json
import csv
from PIL import Image
from sd_recovery.core.organizer import RecoveryOrganizer, RecoveredFile


@pytest.fixture
def test_jpeg(temp_dir):
    """Create a test JPEG file."""
    img_path = temp_dir / "test.jpg"
    # Create larger image to avoid "suspicious" flag (size > 1KB)
    img = Image.new('RGB', (640, 480), color='red')
    img.save(img_path, 'JPEG', quality=95)
    return img_path


class TestRecoveryOrganizer:
    """Test recovery organizer functionality."""

    def test_organizer_initialization(self, temp_dir):
        organizer = RecoveryOrganizer(temp_dir)

        assert organizer.output_base == temp_dir
        assert organizer.images_dir.exists()
        assert organizer.metadata_dir.exists()
        assert organizer.validation_dir.exists()
        assert organizer.valid_dir.exists()
        assert organizer.suspicious_dir.exists()

    def test_organize_single_file(self, temp_dir, test_jpeg):
        organizer = RecoveryOrganizer(temp_dir)

        recovered_files = organizer.organize(
            source_files=[test_jpeg],
            validate_files=True
        )

        assert len(recovered_files) == 1
        assert recovered_files[0].is_valid
        assert not recovered_files[0].is_suspicious
        assert recovered_files[0].width == 640
        assert recovered_files[0].height == 480

    def test_organize_multiple_files(self, temp_dir):
        # Create multiple test JPEGs
        source_dir = temp_dir / "source"
        source_dir.mkdir()

        source_files = []
        for i in range(5):
            img_path = source_dir / f"test_{i}.jpg"
            img = Image.new('RGB', (200, 150), color='blue')
            img.save(img_path, 'JPEG')
            source_files.append(img_path)

        organizer = RecoveryOrganizer(temp_dir / "output")

        recovered_files = organizer.organize(
            source_files=source_files,
            validate_files=True
        )

        assert len(recovered_files) == 5

        # Check sequential naming
        for i, recovered in enumerate(recovered_files, start=1):
            expected_name = f"image_{i:05d}.jpg"
            assert recovered.new_filename == expected_name

    def test_manifest_generation(self, temp_dir, test_jpeg):
        organizer = RecoveryOrganizer(temp_dir)

        recovered_files = organizer.organize(
            source_files=[test_jpeg],
            validate_files=True
        )

        manifest_path = organizer.metadata_dir / "manifest.json"
        assert manifest_path.exists()

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest['total_files'] == 1
        assert manifest['valid_files'] == 1
        assert len(manifest['files']) == 1

    def test_csv_generation(self, temp_dir, test_jpeg):
        organizer = RecoveryOrganizer(temp_dir)

        recovered_files = organizer.organize(
            source_files=[test_jpeg],
            validate_files=True
        )

        csv_path = organizer.metadata_dir / "file_details.csv"
        assert csv_path.exists()

        with open(csv_path, newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Should have header + 1 data row
        assert len(rows) == 2
        assert rows[0][0] == 'filename'  # Header

    def test_summary_generation(self, temp_dir, test_jpeg):
        organizer = RecoveryOrganizer(temp_dir)

        recovered_files = organizer.organize(
            source_files=[test_jpeg],
            validate_files=True
        )

        log_path = organizer.metadata_dir / "recovery_log.txt"
        assert log_path.exists()

        with open(log_path) as f:
            content = f.read()

        assert "Summary Report" in content
        assert "Total files recovered" in content

    def test_symlink_creation_valid(self, temp_dir, test_jpeg):
        organizer = RecoveryOrganizer(temp_dir)

        recovered_files = organizer.organize(
            source_files=[test_jpeg],
            validate_files=True
        )

        # Valid file should have symlink in valid directory
        valid_symlinks = list(organizer.valid_dir.glob("*.jpg"))
        assert len(valid_symlinks) == 1

    def test_organize_without_validation(self, temp_dir, test_jpeg):
        organizer = RecoveryOrganizer(temp_dir)

        recovered_files = organizer.organize(
            source_files=[test_jpeg],
            validate_files=False
        )

        assert len(recovered_files) == 1
        # Without validation, is_valid will be False
        assert not recovered_files[0].is_valid


class TestRecoveredFile:
    """Test RecoveredFile dataclass."""

    def test_recovered_file_creation(self):
        recovered = RecoveredFile(
            original_path="/tmp/f0000001.jpg",
            new_path="/output/image_00001.jpg",
            new_filename="image_00001.jpg",
            is_valid=True,
            is_suspicious=False,
            size_bytes=12345,
            width=1920,
            height=1080
        )

        assert recovered.original_path == "/tmp/f0000001.jpg"
        assert recovered.width == 1920
        assert recovered.height == 1080
        assert recovered.is_valid
        assert not recovered.is_suspicious
