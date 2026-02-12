"""PhotoRec command wrapper and execution."""

import subprocess
import shutil
import logging
from pathlib import Path
from typing import Optional, List, Callable
import re

from ..utils.errors import PhotoRecNotFoundError, PhotoRecExecutionError
from ..utils.progress import ProgressTracker

logger = logging.getLogger(__name__)


class PhotoRecWrapper:
    """Wrapper for PhotoRec recovery tool."""

    def __init__(self, photorec_path: Optional[str] = None):
        """Initialize PhotoRec wrapper.

        Args:
            photorec_path: Path to photorec executable (auto-detected if None)
        """
        self.photorec_path = photorec_path or self._find_photorec()

    def _find_photorec(self) -> str:
        """Find PhotoRec executable.

        Returns:
            Path to photorec

        Raises:
            PhotoRecNotFoundError: If photorec not found
        """
        photorec = shutil.which('photorec')
        if not photorec:
            raise PhotoRecNotFoundError(
                "PhotoRec not found. Install with: brew install testdisk"
            )
        return photorec

    def check_version(self) -> str:
        """Check PhotoRec version.

        Returns:
            Version string

        Raises:
            PhotoRecExecutionError: If version check fails
        """
        try:
            result = subprocess.run(
                [self.photorec_path, '/version'],
                capture_output=True,
                text=True,
                check=True
            )
            # Extract version from output
            version_match = re.search(r'PhotoRec\s+([\d.]+)', result.stdout)
            if version_match:
                return version_match.group(1)
            return "unknown"

        except subprocess.CalledProcessError as e:
            raise PhotoRecExecutionError(f"Failed to check PhotoRec version: {e}")

    def build_command(
        self,
        device_path: str,
        output_dir: Path,
        paranoid: bool = False,
        file_types: Optional[List[str]] = None
    ) -> List[str]:
        """Build PhotoRec command with parameters.

        Args:
            device_path: Path to device or image file
            output_dir: Directory for recovered files
            paranoid: Enable paranoid mode (slower, more thorough)
            file_types: List of file types to recover (defaults to ['jpg'])

        Returns:
            Command as list of strings
        """
        if file_types is None:
            file_types = ['jpg']

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build options list
        options = []

        # Disable all file types first
        options.append('fileopt,everything,disable')

        # Enable selected file types
        for ftype in file_types:
            options.append(f'fileopt,{ftype},enable')

        # Paranoid mode for thorough scanning
        if paranoid:
            options.append('options,paranoid')

        # Start search
        options.append('search')

        # Build command with options combined into single comma-separated argument
        cmd = [
            self.photorec_path,
            '/d', str(output_dir),  # Output directory
            '/cmd', device_path,     # Device or image file
            ','.join(options)        # All options as single comma-separated string
        ]

        return cmd

    def execute(
        self,
        device_path: str,
        output_dir: Path,
        paranoid: bool = False,
        file_types: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> 'PhotoRecResult':
        """Execute PhotoRec recovery.

        Args:
            device_path: Path to device or image file
            output_dir: Directory for recovered files
            paranoid: Enable paranoid mode
            file_types: List of file types to recover
            progress_callback: Optional callback for progress updates

        Returns:
            PhotoRecResult object

        Raises:
            PhotoRecExecutionError: If PhotoRec fails
        """
        cmd = self.build_command(device_path, output_dir, paranoid, file_types)

        logger.info(f"Executing PhotoRec: {' '.join(cmd)}")

        try:
            # Run PhotoRec
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Stream output
            output_lines = []
            if process.stdout:
                for line in process.stdout:
                    line = line.rstrip()
                    output_lines.append(line)
                    logger.debug(f"PhotoRec: {line}")

                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback(line)

            # Wait for completion
            return_code = process.wait()

            if return_code != 0:
                raise PhotoRecExecutionError(
                    f"PhotoRec failed with code {return_code}\n"
                    f"Output: {chr(10).join(output_lines[-20:])}"
                )

            # Parse results
            result = self._parse_results(output_dir, output_lines)
            return result

        except subprocess.SubprocessError as e:
            raise PhotoRecExecutionError(f"Failed to execute PhotoRec: {e}")
        except Exception as e:
            raise PhotoRecExecutionError(f"Unexpected error during recovery: {e}")

    def _parse_results(self, output_dir: Path, output_lines: List[str]) -> 'PhotoRecResult':
        """Parse PhotoRec results.

        Args:
            output_dir: Directory containing recovered files
            output_lines: Output lines from PhotoRec

        Returns:
            PhotoRecResult object
        """
        # Find all recup directories
        recup_dirs = sorted(output_dir.glob('recup_dir.*'))

        # Count recovered files
        recovered_files = []
        for recup_dir in recup_dirs:
            if recup_dir.is_dir():
                recovered_files.extend(recup_dir.glob('*.jpg'))
                recovered_files.extend(recup_dir.glob('*.JPG'))

        # Extract statistics from output
        files_recovered = len(recovered_files)

        # Look for statistics in output
        for line in output_lines:
            # PhotoRec outputs lines like "123 files recovered"
            match = re.search(r'(\d+)\s+files?\s+recovered', line, re.IGNORECASE)
            if match:
                files_recovered = max(files_recovered, int(match.group(1)))

        return PhotoRecResult(
            output_dir=output_dir,
            recup_dirs=recup_dirs,
            files_recovered=files_recovered,
            recovered_files=recovered_files,
            output_lines=output_lines
        )


class PhotoRecResult:
    """Results from PhotoRec execution."""

    def __init__(
        self,
        output_dir: Path,
        recup_dirs: List[Path],
        files_recovered: int,
        recovered_files: List[Path],
        output_lines: List[str]
    ):
        """Initialize PhotoRec result.

        Args:
            output_dir: Output directory
            recup_dirs: List of recup_dir.* directories
            files_recovered: Number of files recovered
            recovered_files: List of recovered file paths
            output_lines: PhotoRec output lines
        """
        self.output_dir = output_dir
        self.recup_dirs = recup_dirs
        self.files_recovered = files_recovered
        self.recovered_files = recovered_files
        self.output_lines = output_lines

    def __str__(self) -> str:
        """String representation."""
        return (
            f"PhotoRecResult(\n"
            f"  output_dir={self.output_dir},\n"
            f"  files_recovered={self.files_recovered},\n"
            f"  recup_dirs={len(self.recup_dirs)}\n"
            f")"
        )
