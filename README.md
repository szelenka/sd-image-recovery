# SD Image Recovery Tool

A safe, user-friendly tool for recovering deleted JPEG images from SD cards on macOS. This tool wraps PhotoRec with better UX, safety checks, and organized output.

## Features

- **Read-Only Operation**: Never modifies the source device
- **Safety Checks**: Multiple layers of protection against internal disk access
- **macOS Native**: Integrates with diskutil for device management
- **Organized Output**: Recovered files organized with metadata and validation reports
- **JPEG Validation**: Automatically validates and categorizes recovered images
- **Progress Tracking**: Real-time progress display during recovery
- **Testable**: Comprehensive test suite with disk image support

## Requirements

- macOS 10.13+ (High Sierra or later)
- Python 3.8+
- PhotoRec (via Homebrew: `brew install testdisk`)
- Admin/sudo access for raw device access

## Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/szelenka/sd-image-recovery.git
cd sd-image-recovery

# Run installation script
bash scripts/install_dependencies.sh

# Activate virtual environment
source venv/bin/activate
```

### Manual Install

```bash
# Install PhotoRec
brew install testdisk

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install package
pip install -e .
```

### Verify Installation

```bash
sd-recovery check
```

## Usage

### List Available Devices

```bash
sd-recovery devices
```

This will show all connected storage devices with safety information:

```
Available Devices:
================================================================================

✓ /dev/disk2
   Size: 32.0 GB
   Volume: SD_CARD
   Filesystem: FAT32
   Mounted at: /Volumes/SD_CARD
   Removable: Yes
   Internal: No
   ✓ Safe for recovery

✗ /dev/disk0
   Size: 500.0 GB
   ...
   ⚠ Safety check failed: Device appears to be an internal disk
```

### Recover from SD Card

```bash
# Basic recovery
sudo sd-recovery recover /dev/disk2 --output ./recovered

# With paranoid mode (slower but more thorough)
sudo sd-recovery recover /dev/disk2 --output ./recovered --paranoid

# Skip validation (faster)
sudo sd-recovery recover /dev/disk2 --output ./recovered --no-validate
```

### Recover from Disk Image

For testing or working with disk image backups:

```bash
sd-recovery recover path/to/image.img --output ./recovered
```

## Safety Features

The tool includes multiple safety mechanisms:

1. **Device Number Check**: Blocks disk0 and disk1 (typically internal disks)
2. **Removable Flag**: Requires device to be marked as removable
3. **Size Check**: Warns if device is unusually large for SD card (>512GB)
4. **User Confirmation**: Requires explicit approval before scanning
5. **Read-Only Mode**: PhotoRec operates in read-only mode by default
6. **Unmount Protection**: Device is unmounted during scan to prevent OS writes

## Output Structure

Recovered files are organized in a timestamped directory:

```
recovered_20240115_143022/
├── images/
│   ├── image_00001.jpg
│   ├── image_00002.jpg
│   └── ...
│
├── metadata/
│   ├── manifest.json          # Detailed recovery information
│   ├── file_details.csv       # Spreadsheet-compatible file list
│   └── recovery_log.txt       # Human-readable summary
│
└── validation/
    ├── valid/                 # Symlinks to validated images
    └── suspicious/            # Symlinks to questionable images
```

### Manifest JSON

The `manifest.json` file contains detailed information about each recovered file:

```json
{
  "recovery_date": "2024-01-15T14:30:22",
  "total_files": 150,
  "valid_files": 145,
  "suspicious_files": 5,
  "files": [
    {
      "new_filename": "image_00001.jpg",
      "is_valid": true,
      "is_suspicious": false,
      "size_bytes": 2456789,
      "width": 4032,
      "height": 3024,
      "has_exif": true,
      "camera_make": "Canon",
      "camera_model": "EOS 5D Mark IV",
      "datetime": "2024:01:10 15:23:45"
    }
  ]
}
```

## Testing

### Run Unit Tests

```bash
pytest tests/unit/ -v
```

### Test with Disk Image

Create a test disk image with deleted files:

```bash
# Create test JPEG files first
mkdir -p tests/fixtures/test_images
# Add some JPEG files to this directory

# Create disk image
bash tests/fixtures/create_test_image.sh

# Test recovery
sd-recovery recover tests/fixtures/test_fat32.img --output ./test_recovered

# Verify results
diff tests/fixtures/checksums_original.txt test_recovered/*/metadata/checksums_recovered.txt
```

### Test with Real SD Card (DESTRUCTIVE!)

**WARNING**: This will format the SD card and destroy all data!

```bash
# Prepare test SD card (replace disk2 with your SD card)
bash scripts/create_test_sd.sh /dev/disk2

# Run recovery
sudo sd-recovery recover /dev/disk2 --output ./test_recovered

# Verify checksums
cd test_recovered/*/images
md5 *.jpg > checksums_recovered.txt
diff checksums_recovered.txt ../../../scripts/checksums_original.txt
```

## Development

### Project Structure

```
sd-image-recovery/
├── src/sd_recovery/
│   ├── core/
│   │   ├── device.py          # Device detection and safety
│   │   ├── photorec_wrapper.py # PhotoRec integration
│   │   ├── recovery.py        # Main orchestration
│   │   └── organizer.py       # Output organization
│   │
│   ├── utils/
│   │   ├── errors.py          # Custom exceptions
│   │   ├── progress.py        # Progress tracking
│   │   └── validation.py     # File validation
│   │
│   └── cli.py                 # CLI interface
│
├── tests/
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── fixtures/              # Test fixtures
│
└── scripts/                   # Helper scripts
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/sd_recovery --cov-report=html

# Specific test file
pytest tests/unit/test_device.py -v

# Skip integration tests
pytest -m "not integration"
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/
```

## Troubleshooting

### PhotoRec Not Found

```bash
# Install PhotoRec
brew install testdisk

# Verify installation
photorec /version
```

### Permission Denied

Raw device access requires sudo:

```bash
sudo sd-recovery recover /dev/disk2
```

### Device Not Recognized

Check device path:

```bash
# List all devices
diskutil list

# Get device info
diskutil info /dev/disk2
```

### No Files Recovered

- **Overwritten Data**: If the SD card has been used since deletion, files may be overwritten
- **File System**: Ensure the SD card uses a supported filesystem (FAT32, exFAT work well)
- **Try Paranoid Mode**: Use `--paranoid` for more thorough scanning

### Recovery Interrupted

If recovery is interrupted:

1. The device will be automatically remounted
2. Partial results are saved in the output directory
3. You can safely restart the recovery process

## How It Works

1. **Device Detection**: Uses `diskutil` to enumerate and identify devices
2. **Safety Validation**: Checks device number, removable flag, and size
3. **Device Preparation**: Unmounts device to prevent OS writes during scan
4. **PhotoRec Execution**: Runs PhotoRec to scan for deleted file signatures
5. **Output Organization**: Collects, renames, and validates recovered files
6. **Metadata Generation**: Creates manifest, CSV, and summary reports
7. **Cleanup**: Remounts device and cleans up temporary files

## Limitations

- **macOS Only**: Uses macOS-specific tools (diskutil, hdiutil)
- **JPEG Only**: Currently only recovers JPEG files (extensible to other formats)
- **Fragmentation**: May not fully recover fragmented files
- **Overwritten Data**: Cannot recover data that has been overwritten

## Future Enhancements

- Support for additional image formats (PNG, RAW, etc.)
- GUI application
- Duplicate detection using perceptual hashing
- Thumbnail preview in recovery reports
- Linux and Windows support
- Deep scan mode for heavily overwritten drives

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Credits

- Built by [szelenka](https://github.com/szelenka)
- Powered by [PhotoRec](https://www.cgsecurity.org/wiki/PhotoRec) by Christophe Grenier
- Uses [Pillow](https://python-pillow.org/) for image validation
- CLI built with [Click](https://click.palletsprojects.com/)

## Support

For issues, questions, or feature requests, please open an issue on GitHub:
https://github.com/szelenka/sd-image-recovery/issues

## Acknowledgments

This tool was created to help recover accidentally deleted photos from a camera SD card. It wraps the powerful but complex PhotoRec tool with a safer, more user-friendly interface specifically designed for macOS users.

Special thanks to the PhotoRec/TestDisk project for creating such a reliable recovery tool.
