#!/bin/bash
# Prepare a real SD card for testing recovery (DESTRUCTIVE!)

set -e

echo "==================================================================="
echo "SD Card Test Preparation Script"
echo "==================================================================="
echo ""
echo "WARNING: This script will FORMAT the specified SD card!"
echo "         All existing data will be DESTROYED!"
echo ""

# Check if device argument provided
if [ -z "$1" ]; then
    echo "Usage: $0 <device>"
    echo "Example: $0 /dev/disk2"
    echo ""
    echo "Available devices:"
    diskutil list | grep -E "^/dev/disk[0-9]+"
    exit 1
fi

DEVICE="$1"

# Safety check - prevent formatting disk0 or disk1
if [[ "$DEVICE" =~ disk[0-1]$ ]]; then
    echo "Error: Cannot format $DEVICE (internal disk protection)"
    exit 1
fi

# Check if device exists
if ! diskutil info "$DEVICE" > /dev/null 2>&1; then
    echo "Error: Device $DEVICE not found"
    exit 1
fi

# Show device info
echo "Device information:"
diskutil info "$DEVICE" | grep -E "(Device Node|Disk Size|Removable Media)"
echo ""

# Final confirmation
read -p "Are you ABSOLUTELY SURE you want to format $DEVICE? [yes/NO]: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted"
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_IMAGES_DIR="$(dirname "$SCRIPT_DIR")/tests/fixtures/test_images"

# Create test images if they don't exist
if [ ! -d "$TEST_IMAGES_DIR" ]; then
    echo "Creating test images directory..."
    mkdir -p "$TEST_IMAGES_DIR"

    python3 - <<EOF
from PIL import Image
import os

test_images_dir = "$TEST_IMAGES_DIR"

for i in range(10):
    img = Image.new('RGB', (1024, 768), color=(i*25, 100, 200))
    img.save(os.path.join(test_images_dir, f'test_photo_{i:02d}.jpg'), 'JPEG', quality=95)

print("Created 10 sample JPEG files")
EOF
fi

echo ""
echo "Step 1: Formatting SD card as FAT32..."
diskutil eraseDisk FAT32 TEST_SD MBRFormat "$DEVICE"

# Wait for mount
sleep 2

MOUNT_POINT="/Volumes/TEST_SD"

if [ ! -d "$MOUNT_POINT" ]; then
    echo "Error: SD card not mounted at $MOUNT_POINT"
    exit 1
fi

echo "Step 2: Copying test images..."
cp "$TEST_IMAGES_DIR"/*.jpg "$MOUNT_POINT/"

# Sync
sync

echo "Step 3: Computing checksums of original files..."
(cd "$MOUNT_POINT" && md5 *.jpg > "$SCRIPT_DIR/checksums_original.txt")

echo "Step 4: Deleting half of the files..."
# Delete every other file
for file in "$MOUNT_POINT"/test_photo_0*.jpg; do
    rm "$file"
    echo "  Deleted: $(basename "$file")"
done

# Sync
sync

echo "Step 5: Unmounting SD card..."
diskutil unmountDisk "$DEVICE"

echo ""
echo "==================================================================="
echo "SD card prepared successfully!"
echo "==================================================================="
echo ""
echo "Remaining files on card:"
echo "  (Card is now unmounted - mount to see files)"
echo ""
echo "Deleted files (should be recoverable):"
ls "$TEST_IMAGES_DIR"/test_photo_0*.jpg 2>/dev/null | xargs -n1 basename
echo ""
echo "Original checksums saved to: $SCRIPT_DIR/checksums_original.txt"
echo ""
echo "To test recovery, run:"
echo "  sudo sd-recovery recover $DEVICE --output ./test_recovered"
echo ""
echo "Then verify checksums of recovered files against originals"
