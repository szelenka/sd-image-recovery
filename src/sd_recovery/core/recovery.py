"""Main recovery orchestration."""

import logging
import subprocess
from pathlib import Path
from typing import Optional
from datetime import datetime
import os

from .device import (
    get_device_info,
    is_safe_device,
    unmount_device,
    mount_device,
    format_device_info,
    DeviceInfo,
)
from .organizer import RecoveryOrganizer

from ..utils.errors import SDRecoveryError, UnsafeDeviceError
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
        validate: bool = True,
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
        self.was_mounted = False
        self.temp_dir: Optional[Path] = None

    def run(
        self,
        skip_confirmation: bool = False,
        rename_prefix: str = "PICT",
        rename_digits: int = 4,
    ) -> bool:
        """Run the complete recovery workflow.

        Args:
            skip_confirmation: Skip user confirmation (dangerous)
            rename_prefix: Prefix for renaming grouped images
            rename_digits: Number of digits for sequential filenames

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

            # Step 5: Run PhotoRec interactively
            print_status("Step 5: Launching PhotoRec (interactive)", "INFO")
            self.run_photorec_interactive()

            # Step 6: Group images by resolution after recovery
            print_status("Step 6: Grouping images by resolution", "INFO")
            from ..utils.image_filter import group_images_by_resolution
            import shutil

            grouped_dir = self.output_dir.parent / "grouped"
            moved = group_images_by_resolution(
                [str(self.output_dir)],
                grouped_dir=str(grouped_dir),
                multi=True,
                rename_prefix=rename_prefix,
                rename_digits=rename_digits,
            )
            print_status(
                f"Moved {moved} images into grouped folders under {grouped_dir}",
                "SUCCESS",
            )

            # Failsafe: Move any files not grouped to a 'failed_to_group' folder inside grouped_dir
            failed_dir = grouped_dir / "failed_to_group"
            files_left = []
            for dirpath, _, filenames in os.walk(self.output_dir):
                for fname in filenames:
                    files_left.append(Path(dirpath) / fname)
            if files_left:
                failed_dir.mkdir(parents=True, exist_ok=True)
                for f in files_left:
                    try:
                        shutil.move(str(f), str(failed_dir / f.name))
                    except Exception as e:
                        print_status(
                            f"Could not move {f} to failsafe folder: {e}", "WARNING"
                        )
                print_status(
                    f"{len(files_left)} files could not be grouped and were moved to {failed_dir}",
                    "WARNING",
                )

            # Replace output_dir with grouped_dir
            try:
                if self.output_dir.exists():
                    shutil.rmtree(self.output_dir)
                grouped_dir.rename(self.output_dir)
                print_status(f"Grouped images are now in {self.output_dir}", "SUCCESS")
            except Exception as e:
                print_status(
                    f"Failed to move grouped images to output directory: {e}", "ERROR"
                )

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
        if device_path_obj.suffix in (".img", ".dmg", ".iso"):
            print_status(f"Using disk image: {self.device_path}", "INFO")
            # For disk images, we don't need device info
            return

        # Get device information
        self.device_info = get_device_info(self.device_path)
        print_status(
            f"Device detected:\n{format_device_info(self.device_info)}", "INFO"
        )

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
            print(
                f"\nWarning: Device is currently mounted at {self.device_info.mount_point}"
            )
            print("It will be unmounted during recovery and remounted afterward.")

        print("\n" + "=" * 60)

        response = input("\nProceed with recovery? [y/N]: ").strip().lower()
        return response in ("y", "yes")

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

    def run_photorec_interactive(self):
        """Run PhotoRec in interactive mode."""
        print("Launching PhotoRec for interactive recovery...")
        print("Please select the correct partition and output directory when prompted.")
        cmd = ["sudo", "photorec", "/d", str(self.output_dir), self.device_path]
        subprocess.run(cmd)


def recover(
    device_path: str,
    output_dir: Optional[str] = None,
    paranoid: bool = False,
    validate: bool = True,
    force: bool = False,
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
        validate=validate,
    )

    return session.run(skip_confirmation=force)
