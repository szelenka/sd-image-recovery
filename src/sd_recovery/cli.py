"""Command-line interface for SD recovery tool."""

import sys
import logging
import click
from pathlib import Path

from . import __version__
from .core.device import get_all_devices, get_device_info, format_device_info, is_safe_device
from .core.recovery import recover
from .core.photorec_wrapper import PhotoRecWrapper
from .utils.errors import SDRecoveryError, PhotoRecNotFoundError
from .utils.progress import print_status


# Configure logging
def setup_logging(verbose: bool = False):
    """Setup logging configuration.

    Args:
        verbose: Enable verbose logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('sd_recovery.log'),
            logging.StreamHandler() if verbose else logging.NullHandler()
        ]
    )


@click.group()
@click.version_option(version=__version__)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def main(ctx, verbose):
    """SD Image Recovery Tool - Recover deleted images from SD cards on macOS.

    This tool wraps PhotoRec to provide a safer, more user-friendly interface
    for recovering deleted JPEG images from SD cards and disk images.
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    setup_logging(verbose)


@main.command()
@click.pass_context
def devices(ctx):
    """List all available storage devices.

    Shows information about all connected storage devices including
    size, filesystem, and whether they pass safety checks.
    """
    try:
        print_status("Scanning for devices", "INFO")
        all_devices = get_all_devices()

        if not all_devices:
            print_status("No devices found", "WARNING")
            return

        print("\nAvailable Devices:")
        print("=" * 80)

        for device_info in all_devices:
            # Check safety
            is_safe, reason = is_safe_device(device_info)

            # Device header
            status_symbol = "✓" if is_safe else "✗"
            status_color = "\033[92m" if is_safe else "\033[91m"
            reset = "\033[0m"

            print(f"\n{status_color}{status_symbol}{reset} {device_info.device_path}")
            print(f"   Size: {device_info.size_human}")

            if device_info.volume_name:
                print(f"   Volume: {device_info.volume_name}")

            if device_info.filesystem:
                print(f"   Filesystem: {device_info.filesystem}")

            if device_info.mount_point:
                print(f"   Mounted at: {device_info.mount_point}")

            print(f"   Removable: {'Yes' if device_info.is_removable else 'No'}")
            print(f"   Internal: {'Yes' if device_info.is_internal else 'No'}")

            if not is_safe:
                print(f"   {status_color}⚠ Safety check failed: {reason}{reset}")
            else:
                print(f"   {status_color}✓ Safe for recovery{reset}")

        print("\n" + "=" * 80)
        print("\nUse 'sd-recovery recover <device>' to recover files from a device.")
        print("Example: sd-recovery recover /dev/disk2 --output ./recovered")

    except SDRecoveryError as e:
        print_status(f"Error: {e}", "ERROR")
        sys.exit(1)


@main.command('recover')
@click.argument('device', type=str)
@click.option(
    '--output', '-o',
    type=click.Path(path_type=Path),
    help='Output directory for recovered files (auto-generated if not specified)'
)
@click.option(
    '--paranoid',
    is_flag=True,
    help='Enable paranoid mode for thorough scanning (slower but finds more files)'
)
@click.option(
    '--no-validate',
    is_flag=True,
    help='Skip validation of recovered files'
)
@click.option(
    '--force',
    is_flag=True,
    help='Skip confirmation and safety checks (dangerous - use with caution)'
)
@click.pass_context
def recover_cmd(ctx, device, output, paranoid, no_validate, force):
    """Recover deleted images from a device or disk image.

    DEVICE can be either:
      - A device path (e.g., /dev/disk2 or /dev/rdisk2)
      - A disk image file (e.g., test_sd.img)

    Examples:

      \b
      # Recover from SD card
      sd-recovery recover /dev/disk2 --output ./recovered

      \b
      # Recover from disk image (for testing)
      sd-recovery recover test.img --output ./test_recovered

      \b
      # Use paranoid mode for thorough scanning
      sd-recovery recover /dev/disk2 --paranoid

    The tool operates in READ-ONLY mode and will never modify or delete
    data on the source device.
    """
    verbose = ctx.obj.get('verbose', False)

    try:
        # Check if PhotoRec is installed
        try:
            wrapper = PhotoRecWrapper()
            version = wrapper.check_version()
            if verbose:
                print_status(f"Using PhotoRec version {version}", "INFO")
        except PhotoRecNotFoundError as e:
            print_status(str(e), "ERROR")
            sys.exit(1)

        # Show warning for force mode
        if force:
            print_status(
                "WARNING: Force mode enabled - skipping safety checks!",
                "WARNING"
            )

        # Run recovery
        validate = not no_validate
        success = recover(
            device_path=device,
            output_dir=str(output) if output else None,
            paranoid=paranoid,
            validate=validate,
            force=force
        )

        if success:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print_status("\nRecovery cancelled by user", "WARNING")
        sys.exit(130)

    except SDRecoveryError as e:
        print_status(f"Recovery failed: {e}", "ERROR")
        sys.exit(1)

    except Exception as e:
        print_status(f"Unexpected error: {e}", "ERROR")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@main.command()
def check():
    """Check if all dependencies are installed.

    Verifies that PhotoRec is installed and accessible.
    """
    try:
        wrapper = PhotoRecWrapper()
        version = wrapper.check_version()
        print_status(f"PhotoRec {version} is installed", "SUCCESS")
        print_status("All dependencies are ready", "SUCCESS")
        sys.exit(0)

    except PhotoRecNotFoundError as e:
        print_status(str(e), "ERROR")
        print_status("\nTo install PhotoRec:", "INFO")
        print("  brew install testdisk")
        sys.exit(1)

    except Exception as e:
        print_status(f"Error checking dependencies: {e}", "ERROR")
        sys.exit(1)


if __name__ == '__main__':
    main()
