"""Image filtering utilities for SD recovery package."""

import os
import glob
import shutil
from PIL import Image
from typing import Tuple, List


def is_image_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff"]


def filter_images_by_resolution(
    root_dir: str, min_width: int, min_height: int, remove: bool = True
) -> List[Tuple[str, Tuple[int, int]]]:
    """
    Scan root_dir recursively, remove or list images below min resolution.
    Returns a list of (filepath, (width, height)) for removed/listed images.
    """
    affected = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if not is_image_file(fname):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with Image.open(fpath) as img:
                    width, height = img.size
                    if width < min_width or height < min_height:
                        affected.append((fpath, (width, height)))
                        if remove:
                            os.remove(fpath)
            except Exception:
                continue
    return affected


def filter_images_by_resolution_multi(
    parent_dir: str,
    min_width: int,
    min_height: int,
    remove: bool = True,
    pattern: str = "recovered*",
) -> List[Tuple[str, Tuple[int, int]]]:
    """
    Scan all peer folders matching pattern in parent_dir, recursively filter images by resolution.
    """
    affected = []
    for folder in glob.glob(os.path.join(parent_dir, pattern)):
        if os.path.isdir(folder):
            affected.extend(
                filter_images_by_resolution(
                    folder, min_width, min_height, remove=remove
                )
            )
    return affected


def group_images_by_resolution(
    root_dirs,
    grouped_dir,
    pattern="recovered*",
    multi=True,
    rename_prefix=None,
    rename_digits=4,
):
    """
    Move images from root_dirs (or all matching peer folders if multi) into grouped_dir/<width>x<height>/.
    Optionally rename files to a pattern like PREFIXxxxx.jpg (sequential per run, digits configurable).
    """
    if multi:
        all_dirs = []
        for root_dir in root_dirs:
            all_dirs.extend(
                [
                    d
                    for d in glob.glob(os.path.join(root_dir, pattern))
                    if os.path.isdir(d)
                ]
            )
    else:
        all_dirs = root_dirs
    grouped_dir = os.path.abspath(grouped_dir)
    os.makedirs(grouped_dir, exist_ok=True)
    moved = 0
    seq = 1
    for dirpath in all_dirs:
        for dirpath2, _, filenames in os.walk(dirpath):
            for fname in filenames:
                if not is_image_file(fname):
                    continue
                fpath = os.path.join(dirpath2, fname)
                try:
                    with Image.open(fpath) as img:
                        width, height = img.size
                    res_folder = os.path.join(grouped_dir, f"{width}x{height}")
                    os.makedirs(res_folder, exist_ok=True)
                    if rename_prefix:
                        ext = os.path.splitext(fname)[1].lower()
                        dest_name = f"{rename_prefix}{seq:0{rename_digits}d}{ext}"
                        seq += 1
                    else:
                        dest_name = fname
                    dest = os.path.join(res_folder, dest_name)
                    # Avoid overwrite
                    base, ext = os.path.splitext(dest_name)
                    i = 1
                    while os.path.exists(dest):
                        dest = os.path.join(res_folder, f"{base}_{i}{ext}")
                        i += 1
                    shutil.move(fpath, dest)
                    moved += 1
                except Exception as e:
                    print(f"[ERROR] Could not move {fpath}: {e}")
                    continue
    return moved
