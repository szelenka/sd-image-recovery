#!/bin/bash
# Create a test disk image with deleted JPEG files for testing recovery

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_FILE="$SCRIPT_DIR/test_fat32.img"
IMAGE_SIZE_MB=100
MOUNT_NAME="TEST_IMG"

echo "Creating test disk image for SD recovery testing..."

# Check if test images directory exists
TEST_IMAGES_DIR="$SCRIPT_DIR/test_images"
if [ ! -d "$TEST_IMAGES_DIR" ]; then
    echo "Error: Test images directory not found at $TEST_IMAGES_DIR"
    echo "Please create test JPEG files in $TEST_IMAGES_DIR first"
    exit 1
fi

# Check if we have any JPEG files
JPEG_COUNT=$(find "$TEST_IMAGES_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) | wc -l)
if [ "$JPEG_COUNT" -eq 0 ]; then
    echo "Error: No JPEG files found in $TEST_IMAGES_DIR"
    echo "Creating sample JPEG files..."

    # Create sample images using Python
    python3 - <<EOF
from PIL import Image
import os

test_images_dir = "$TEST_IMAGES_DIR"
os.makedirs(test_images_dir, exist_ok=True)

for i in range(5):
    img = Image.new('RGB', (640, 480), color=(i*50, 100, 200))
    img.save(os.path.join(test_images_dir, f'test_photo_{i}.jpg'), 'JPEG')

print("Created 5 sample JPEG files")
EOF
fi

# Clean up old image if exists
if [ -f "$IMAGE_FILE" ]; then
    echo "Removing old test image..."
    rm "$IMAGE_FILE"
fi

# Create blank image file
echo "Creating ${IMAGE_SIZE_MB}MB disk image..."
dd if=/dev/zero of="$IMAGE_FILE" bs=1m count=$IMAGE_SIZE_MB 2>/dev/null

# Attach image to get device
echo "Attaching disk image..."
DEVICE=$(hdiutil attach -nomount "$IMAGE_FILE" | grep '/dev/disk' | awk '{print $1}')

if [ -z "$DEVICE" ]; then
    echo "Error: Failed to attach disk image"
    exit 1
fi

echo "Attached as $DEVICE"

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up..."
    if [ -n "$DEVICE" ]; then
        diskutil unmountDisk "$DEVICE" 2>/dev/null || true
        hdiutil detach "$DEVICE" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Format as FAT32
echo "Formatting as FAT32..."
diskutil eraseDisk FAT32 "$MOUNT_NAME" MBRFormat "$DEVICE"

# Wait for mount
sleep 2

# Find mount point
MOUNT_POINT="/Volumes/$MOUNT_NAME"

if [ ! -d "$MOUNT_POINT" ]; then
    echo "Error: Mount point not found at $MOUNT_POINT"
    exit 1
fi

echo "Mounted at $MOUNT_POINT"

# Copy test images to disk
echo "Copying test images to disk..."
cp "$TEST_IMAGES_DIR"/*.jpg "$MOUNT_POINT/" 2>/dev/null || true
cp "$TEST_IMAGES_DIR"/*.jpeg "$MOUNT_POINT/" 2>/dev/null || true

# Sync to ensure files are written
sync

# List files before deletion
echo "Files on disk:"
ls -lh "$MOUNT_POINT"

# Save checksums of original files
echo "Saving checksums..."
(cd "$MOUNT_POINT" && md5 *.jpg > "$SCRIPT_DIR/checksums_original.txt" 2>/dev/null) || true

# Delete some files to simulate deletion
echo "Deleting files to simulate data loss..."
rm "$MOUNT_POINT"/test_photo_*.jpg 2>/dev/null || true
rm "$MOUNT_POINT"/*.jpg 2>/dev/null || true

# Sync again
sync

echo "Files after deletion:"
ls -lh "$MOUNT_POINT"

# Unmount
echo "Unmounting disk..."
diskutil unmountDisk "$DEVICE"

# Detach
echo "Detaching disk image..."
hdiutil detach "$DEVICE"

echo ""
echo "Test disk image created successfully: $IMAGE_FILE"
echo "Original file checksums saved to: $SCRIPT_DIR/checksums_original.txt"
echo ""
echo "To test recovery, run:"
echo "  sd-recovery recover $IMAGE_FILE --output ./test_recovered"
echo ""
echo "Then compare checksums:"
echo "  cd test_recovered/*/images"
echo "  md5 *.jpg > checksums_recovered.txt"
echo "  diff checksums_recovered.txt $SCRIPT_DIR/checksums_original.txt"
