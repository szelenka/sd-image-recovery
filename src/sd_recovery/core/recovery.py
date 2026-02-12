"""Main recovery orchestration."""

import logging
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime

from .device import (
    get_device_info,
    is_safe_device,
    unmount_device,
    mount_device,
    format_device_info,
    DeviceInfo,
)
from .photorec_wrapper import PhotoRecWrapper, PhotoRecResult
from .organizer import RecoveryOrganizer

from ..utils.errors import (
    SDRecoveryError,
    UnsafeDeviceError,
)
from ..utils.progress import print_status
from ..utils.validation import validate_device_path

logger = logging.getLogger(__name__)


class RecoverySession:
    """Manages a complete recovery session."""

    def __init__(
        self,
        device_path: str,
        output_dir: Optional[Path] = None,
        paranoid: bool = False,
        validate: bool = True
    ):
        """Initialize recovery session.

        Args:
            device_path: Path to device or image file
            output_dir: Output directory (auto-generated if None)
            paranoid: Enable paranoid mode for thorough scanning
            validate: Validate recovered files
        """
        self.device_path = device_path
        self.paranoid = paranoid
        self.validate = validate

        # Generate output directory if not provided
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path.cwd() / f"recovered_{timestamp}"

        self.output_dir = Path(output_dir)
        self.device_info: Optional[DeviceInfo] = None
        self.photorec_wrapper = PhotoRecWrapper()
        self.was_mounted = False
        self.temp_dir: Optional[Path] = None

    def run(self, skip_confirmation: bool = False) -> bool:
        """Run the complete recovery workflow.

        Args:
            skip_confirmation: Skip user confirmation (dangerous)

        Returns:
            True if successful

        Raises:
            SDRecoveryError: If recovery fails
        """
        try:
            # Step 1: Validate and check device
            print_status("Step 1: Validating device", "INFO")
            self._validate_device()

            # Step 2: Safety checks
            print_status("Step 2: Running safety checks", "INFO")
            self._check_safety()

            # Step 3: User confirmation
            if not skip_confirmation:
                print_status("Step 3: Requesting confirmation", "INFO")
                if not self._get_confirmation():
                    print_status("Recovery cancelled by user", "WARNING")
                    return False

            # Step 4: Prepare device
            print_status("Step 4: Preparing device", "INFO")
            self._prepare_device()

            # Step 5: Run PhotoRec
            print_status("Step 5: Running PhotoRec recovery", "INFO")
            photorec_result = self._run_photorec()

            # Step 6: Organize output
            print_status("Step 6: Organizing recovered files", "INFO")
            self._organize_output(photorec_result)

            # Step 7: Cleanup
            print_status("Step 7: Cleaning up", "INFO")
            self._cleanup()

            print_status(f"Recovery complete! Output: {self.output_dir}", "SUCCESS")
            return True

        except KeyboardInterrupt:
            print_status("Recovery interrupted by user", "WARNING")
            self._cleanup()
            raise

        except Exception as e:
            print_status(f"Recovery failed: {e}", "ERROR")
            self._cleanup()
            raise

    def _validate_device(self):
        """Validate device path and get information."""
        # Validate path format
        device_path_obj = validate_device_path(self.device_path)

        # Check if it's a disk image file
        if device_path_obj.suffix in ('.img', '.dmg', '.iso'):
            print_status(f"Using disk image: {self.device_path}", "INFO")
            # For disk images, we don't need device info
            return

        # Get device information
        self.device_info = get_device_info(self.device_path)
        print_status(f"Device detected:\n{format_device_info(self.device_info)}", "INFO")

    def _check_safety(self):
        """Run safety checks on device."""
        # Skip safety checks for disk images
        if self.device_info is None:
            return

        is_safe, reason = is_safe_device(self.device_info)

        if not is_safe:
            raise UnsafeDeviceError(
                f"Device failed safety check: {reason}\n"
                f"Use a disk image file (.img) for testing, or override with --force"
            )

        print_status("Device passed safety checks", "SUCCESS")

    def _get_confirmation(self) -> bool:
        """Get user confirmation to proceed.

        Returns:
            True if user confirms
        """
        print("\n" + "=" * 60)
        print("RECOVERY CONFIRMATION")
        print("=" * 60)

        if self.device_info:
            print(f"\nDevice: {self.device_info.device_path}")
            print(f"Size: {self.device_info.size_human}")
            if self.device_info.volume_name:
                print(f"Volume: {self.device_info.volume_name}")
        else:
            print(f"\nImage file: {self.device_path}")

        print(f"Output directory: {self.output_dir}")
        print(f"Paranoid mode: {'Enabled' if self.paranoid else 'Disabled'}")
        print(f"Validation: {'Enabled' if self.validate else 'Disabled'}")

        print("\nThis operation will:")
        print("  - Read the device/image in READ-ONLY mode")
        print("  - NOT modify or delete any data")
        print("  - Recover deleted JPEG images")
        print("  - Save recovered files to the output directory")

        if self.device_info and self.device_info.mount_point:
            print(f"\nWarning: Device is currently mounted at {self.device_info.mount_point}")
            print("It will be unmounted during recovery and remounted afterward.")

        print("\n" + "=" * 60)

        response = input("\nProceed with recovery? [y/N]: ").strip().lower()
        return response in ('y', 'yes')

    def _prepare_device(self):
        """Prepare device for recovery."""
        # Skip for disk images
        if self.device_info is None:
            return

        # Check if mounted
        if self.device_info.mount_point:
            self.was_mounted = True
            print_status(f"Unmounting {self.device_path}", "INFO")
            unmount_device(self.device_path)
        else:
            self.was_mounted = False

    def _run_photorec(self) -> PhotoRecResult:
        """Run PhotoRec recovery.

        Returns:
            PhotoRecResult object
        """
        # Create temporary directory for PhotoRec output
        self.temp_dir = Path(tempfile.mkdtemp(prefix="photorec_"))
        logger.info(f"PhotoRec temporary directory: {self.temp_dir}")

        # Progress callback
        def progress_callback(line: str):
            # PhotoRec outputs progress lines we can display
            if "Pass" in line or "%" in line:
                print(f"  {line}")

        # Use raw device path if available (faster)
        device_to_scan = self.device_path
        if self.device_info and self.device_info.raw_device_path:
            device_to_scan = self.device_info.raw_device_path
            print_status(f"Using raw device: {device_to_scan}", "INFO")

        # Run PhotoRec
        result = self.photorec_wrapper.execute(
            device_path=device_to_scan,
            output_dir=self.temp_dir,
            paranoid=self.paranoid,
            file_types=['jpg'],
            progress_callback=progress_callback
        )

        print_status(f"PhotoRec recovered {result.files_recovered} files", "SUCCESS")
        return result

    def _organize_output(self, photorec_result: PhotoRecResult):
        """Organize PhotoRec output.

        Args:
            photorec_result: Result from PhotoRec execution
        """
        # Create organizer
        organizer = RecoveryOrganizer(self.output_dir)

        # Organize files
        recovered_files = organizer.organize(
            source_files=photorec_result.recovered_files,
            validate_files=self.validate
        )

        # Print summary
        valid_count = sum(1 for f in recovered_files if f.is_valid)
        suspicious_count = sum(1 for f in recovered_files if f.is_suspicious)

        print_status(
            f"Organized {len(recovered_files)} files "
            f"({valid_count} valid, {suspicious_count} suspicious)",
            "SUCCESS"
        )

    def _cleanup(self):
        """Cleanup after recovery."""
        # Remount device if it was mounted before
        if self.device_info and self.was_mounted:
            try:
                print_status(f"Remounting {self.device_path}", "INFO")
                mount_device(self.device_path)
            except Exception as e:
                print_status(f"Failed to remount device: {e}", "WARNING")

        # Clean up temporary directory
        if self.temp_dir and self.temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Could not remove temporary directory: {e}")


def recover(
    device_path: str,
    output_dir: Optional[str] = None,
    paranoid: bool = False,
    validate: bool = True,
    force: bool = False
) -> bool:
    """Recover deleted images from device.

    Args:
        device_path: Path to device or image file
        output_dir: Output directory
        paranoid: Enable paranoid mode
        validate: Validate recovered files
        force: Skip confirmation and safety checks

    Returns:
        True if successful
    """
    output_path = Path(output_dir) if output_dir else None

    session = RecoverySession(
        device_path=device_path,
        output_dir=output_path,
        paranoid=paranoid,
        validate=validate
    )

    return session.run(skip_confirmation=force)
