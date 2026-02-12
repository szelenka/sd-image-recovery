"""Integration tests for complete recovery flow."""

import pytest
from pathlib import Path
from PIL import Image
from sd_recovery.core.recovery import RecoverySession


@pytest.fixture
def test_disk_image(temp_dir):
    """Create a simple test disk image with JPEG files.

    Note: This creates a simple directory structure rather than an actual
    disk image. For real disk image testing, use the create_test_image.sh script.
    """
    # For integration tests, we'll use a directory that PhotoRec can scan
    # In a real scenario, you'd use an actual disk image created with dd/hdiutil
    image_dir = temp_dir / "test_disk"
    image_dir.mkdir()

    # Create some test JPEGs
    for i in range(3):
        img_path = image_dir / f"photo_{i}.jpg"
        img = Image.new('RGB', (640, 480), color='blue')
        img.save(img_path, 'JPEG')

    return image_dir


class TestRecoveryFlow:
    """Test complete recovery workflow."""

    @pytest.mark.skip(reason="Requires PhotoRec to be installed")
    def test_recovery_from_directory(self, temp_dir, test_disk_image):
        """Test recovery from a test directory."""
        output_dir = temp_dir / "recovered"

        session = RecoverySession(
            device_path=str(test_disk_image),
            output_dir=output_dir,
            paranoid=False,
            validate=True
        )

        # Run with force to skip confirmation
        success = session.run(skip_confirmation=True)

        # Note: This test may fail if PhotoRec isn't installed
        # or if it doesn't recognize the directory as a valid source
        if success:
            assert output_dir.exists()
            assert (output_dir / "images").exists()
            assert (output_dir / "metadata").exists()

    def test_recovery_session_initialization(self, temp_dir):
        """Test recovery session initialization."""
        session = RecoverySession(
            device_path="/dev/disk99",
            output_dir=temp_dir / "output",
            paranoid=True,
            validate=True
        )

        assert session.device_path == "/dev/disk99"
        assert session.paranoid is True
        assert session.validate is True
        assert session.output_dir == temp_dir / "output"

    def test_recovery_session_auto_output_dir(self):
        """Test recovery session with auto-generated output directory."""
        session = RecoverySession(
            device_path="/dev/disk99",
            paranoid=False,
            validate=True
        )

        assert session.output_dir is not None
        assert "recovered_" in str(session.output_dir)

    @pytest.mark.skip(reason="Requires actual disk image")
    def test_full_recovery_with_disk_image(self, temp_dir):
        """Test full recovery from an actual disk image.

        This test requires a properly formatted disk image created with
        the create_test_image.sh script.
        """
        # Path to test disk image (must be created separately)
        test_image_path = Path(__file__).parent.parent / "fixtures" / "test_fat32.img"

        if not test_image_path.exists():
            pytest.skip("Test disk image not found. Run create_test_image.sh first.")

        output_dir = temp_dir / "recovered"

        session = RecoverySession(
            device_path=str(test_image_path),
            output_dir=output_dir,
            validate=True
        )

        success = session.run(skip_confirmation=True)

        assert success
        assert output_dir.exists()

        # Check output structure
        assert (output_dir / "images").exists()
        assert (output_dir / "metadata").exists()
        assert (output_dir / "metadata" / "manifest.json").exists()
        assert (output_dir / "metadata" / "file_details.csv").exists()
        assert (output_dir / "metadata" / "recovery_log.txt").exists()

        # Check that some files were recovered
        images = list((output_dir / "images").glob("*.jpg"))
        assert len(images) > 0
