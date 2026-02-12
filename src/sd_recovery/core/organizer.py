"""Output organization and file validation."""

import json
import csv
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from ..utils.validation import validate_jpeg, is_suspicious_jpeg, format_size
from ..utils.progress import ProgressTracker

logger = logging.getLogger(__name__)


@dataclass
class RecoveredFile:
    """Information about a recovered file."""
    original_path: str
    new_path: str
    new_filename: str
    is_valid: bool
    is_suspicious: bool
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    has_exif: bool = False
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    datetime: Optional[str] = None


class RecoveryOrganizer:
    """Organize and validate recovered files."""

    def __init__(self, output_base: Path):
        """Initialize organizer.

        Args:
            output_base: Base directory for organized output
        """
        self.output_base = output_base
        self.images_dir = output_base / "images"
        self.metadata_dir = output_base / "metadata"
        self.validation_dir = output_base / "validation"
        self.valid_dir = self.validation_dir / "valid"
        self.suspicious_dir = self.validation_dir / "suspicious"

        # Create directories
        for directory in [
            self.images_dir,
            self.metadata_dir,
            self.valid_dir,
            self.suspicious_dir
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def organize(
        self,
        source_files: List[Path],
        validate_files: bool = True
    ) -> List[RecoveredFile]:
        """Organize recovered files.

        Args:
            source_files: List of source file paths from PhotoRec
            validate_files: Whether to validate files

        Returns:
            List of RecoveredFile objects
        """
        logger.info(f"Organizing {len(source_files)} files")

        recovered_files = []

        with ProgressTracker(total=len(source_files), desc="Organizing files") as progress:
            for idx, source_file in enumerate(source_files, start=1):
                try:
                    recovered = self._process_file(
                        source_file,
                        idx,
                        validate=validate_files
                    )
                    if recovered:
                        recovered_files.append(recovered)
                except Exception as e:
                    logger.error(f"Failed to process {source_file}: {e}")

                progress.update(1)

        logger.info(f"Successfully organized {len(recovered_files)} files")

        # Generate reports
        self._generate_manifest(recovered_files)
        self._generate_csv(recovered_files)
        self._generate_summary(recovered_files)

        return recovered_files

    def _process_file(
        self,
        source_file: Path,
        index: int,
        validate: bool = True
    ) -> Optional[RecoveredFile]:
        """Process a single file.

        Args:
            source_file: Source file path
            index: File index for naming
            validate: Whether to validate file

        Returns:
            RecoveredFile object or None if processing failed
        """
        # Generate new filename
        new_filename = f"image_{index:05d}.jpg"
        new_path = self.images_dir / new_filename

        # Copy file
        try:
            shutil.copy2(source_file, new_path)
        except Exception as e:
            logger.error(f"Failed to copy {source_file}: {e}")
            return None

        # Get file size
        size_bytes = new_path.stat().st_size

        # Validate if requested
        is_valid = False
        is_suspicious = False
        metadata = None

        if validate:
            is_valid, metadata = validate_jpeg(new_path)
            if metadata:
                is_suspicious = is_suspicious_jpeg(metadata)

        # Create recovered file record
        recovered = RecoveredFile(
            original_path=str(source_file),
            new_path=str(new_path),
            new_filename=new_filename,
            is_valid=is_valid,
            is_suspicious=is_suspicious,
            size_bytes=size_bytes,
        )

        # Extract metadata
        if metadata:
            recovered.width = metadata.get('width')
            recovered.height = metadata.get('height')
            recovered.has_exif = metadata.get('has_exif', False)
            recovered.camera_make = metadata.get('camera_make')
            recovered.camera_model = metadata.get('camera_model')
            recovered.datetime = metadata.get('datetime')

        # Create symlinks for categorization
        self._create_symlinks(recovered)

        return recovered

    def _create_symlinks(self, recovered: RecoveredFile):
        """Create categorization symlinks.

        Args:
            recovered: RecoveredFile object
        """
        target = Path(recovered.new_path)

        try:
            if recovered.is_valid and not recovered.is_suspicious:
                # Valid files
                symlink = self.valid_dir / recovered.new_filename
                if not symlink.exists():
                    symlink.symlink_to(target)
            elif recovered.is_suspicious or not recovered.is_valid:
                # Suspicious or invalid files
                symlink = self.suspicious_dir / recovered.new_filename
                if not symlink.exists():
                    symlink.symlink_to(target)
        except Exception as e:
            logger.debug(f"Could not create symlink for {recovered.new_filename}: {e}")

    def _generate_manifest(self, recovered_files: List[RecoveredFile]):
        """Generate JSON manifest.

        Args:
            recovered_files: List of RecoveredFile objects
        """
        manifest_path = self.metadata_dir / "manifest.json"

        manifest = {
            'recovery_date': datetime.now().isoformat(),
            'total_files': len(recovered_files),
            'valid_files': sum(1 for f in recovered_files if f.is_valid),
            'suspicious_files': sum(1 for f in recovered_files if f.is_suspicious),
            'files': [asdict(f) for f in recovered_files]
        }

        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Manifest written to {manifest_path}")

    def _generate_csv(self, recovered_files: List[RecoveredFile]):
        """Generate CSV file details.

        Args:
            recovered_files: List of RecoveredFile objects
        """
        csv_path = self.metadata_dir / "file_details.csv"

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'filename',
                'size_bytes',
                'size_human',
                'is_valid',
                'is_suspicious',
                'width',
                'height',
                'has_exif',
                'camera_make',
                'camera_model',
                'datetime',
                'path'
            ])

            # Data rows
            for recovered in recovered_files:
                writer.writerow([
                    recovered.new_filename,
                    recovered.size_bytes,
                    format_size(recovered.size_bytes),
                    recovered.is_valid,
                    recovered.is_suspicious,
                    recovered.width or '',
                    recovered.height or '',
                    recovered.has_exif,
                    recovered.camera_make or '',
                    recovered.camera_model or '',
                    recovered.datetime or '',
                    recovered.new_path
                ])

        logger.info(f"CSV written to {csv_path}")

    def _generate_summary(self, recovered_files: List[RecoveredFile]):
        """Generate recovery summary log.

        Args:
            recovered_files: List of RecoveredFile objects
        """
        log_path = self.metadata_dir / "recovery_log.txt"

        valid_files = [f for f in recovered_files if f.is_valid]
        suspicious_files = [f for f in recovered_files if f.is_suspicious]
        invalid_files = [f for f in recovered_files if not f.is_valid]

        total_size = sum(f.size_bytes for f in recovered_files)

        with open(log_path, 'w') as f:
            f.write("SD Card Image Recovery - Summary Report\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Recovery Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("Statistics:\n")
            f.write(f"  Total files recovered: {len(recovered_files)}\n")
            f.write(f"  Valid files: {len(valid_files)}\n")
            f.write(f"  Suspicious files: {len(suspicious_files)}\n")
            f.write(f"  Invalid files: {len(invalid_files)}\n")
            f.write(f"  Total size: {format_size(total_size)}\n\n")

            # Files with EXIF data
            exif_files = [f for f in recovered_files if f.has_exif]
            f.write(f"Files with EXIF data: {len(exif_files)}\n")

            if exif_files:
                cameras = {}
                for file in exif_files:
                    if file.camera_make and file.camera_model:
                        camera = f"{file.camera_make} {file.camera_model}"
                        cameras[camera] = cameras.get(camera, 0) + 1

                if cameras:
                    f.write("\nCamera models detected:\n")
                    for camera, count in sorted(cameras.items()):
                        f.write(f"  {camera}: {count} images\n")

            f.write("\nOutput Structure:\n")
            f.write(f"  Images: {self.images_dir}\n")
            f.write(f"  Metadata: {self.metadata_dir}\n")
            f.write(f"  Valid images: {self.valid_dir}\n")
            f.write(f"  Suspicious images: {self.suspicious_dir}\n")

        logger.info(f"Summary written to {log_path}")

    def cleanup_source(self, source_dir: Path):
        """Clean up PhotoRec source directories.

        Args:
            source_dir: Source directory containing recup_dir.* folders
        """
        logger.info(f"Cleaning up source directory: {source_dir}")

        # Remove recup_dir.* directories
        for recup_dir in source_dir.glob('recup_dir.*'):
            if recup_dir.is_dir():
                try:
                    shutil.rmtree(recup_dir)
                    logger.debug(f"Removed {recup_dir}")
                except Exception as e:
                    logger.warning(f"Could not remove {recup_dir}: {e}")

        # Remove report.xml if exists
        report_xml = source_dir / "report.xml"
        if report_xml.exists():
            try:
                report_xml.unlink()
                logger.debug(f"Removed {report_xml}")
            except Exception as e:
                logger.warning(f"Could not remove {report_xml}: {e}")
