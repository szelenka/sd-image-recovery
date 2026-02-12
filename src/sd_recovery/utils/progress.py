"""Progress tracking and display utilities."""

from typing import Optional
from tqdm import tqdm
import sys


class ProgressTracker:
    """Track and display progress for recovery operations."""

    def __init__(self, total: Optional[int] = None, desc: str = "Processing"):
        """Initialize progress tracker.

        Args:
            total: Total number of items to process (None for unknown)
            desc: Description to display
        """
        self.total = total
        self.desc = desc
        self.pbar: Optional[tqdm] = None
        self.current = 0

    def start(self):
        """Start progress tracking."""
        if self.pbar is None:
            self.pbar = tqdm(
                total=self.total,
                desc=self.desc,
                unit="files" if self.total else "it",
                disable=None  # Auto-detect if output is terminal
            )

    def update(self, n: int = 1):
        """Update progress by n items.

        Args:
            n: Number of items processed
        """
        if self.pbar:
            self.pbar.update(n)
        self.current += n

    def set_description(self, desc: str):
        """Update the progress description.

        Args:
            desc: New description
        """
        self.desc = desc
        if self.pbar:
            self.pbar.set_description(desc)

    def finish(self):
        """Complete and close progress tracking."""
        if self.pbar:
            self.pbar.close()
            self.pbar = None

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.finish()


def print_status(message: str, status: str = "INFO"):
    """Print a status message.

    Args:
        message: Message to print
        status: Status level (INFO, SUCCESS, WARNING, ERROR)
    """
    colors = {
        "INFO": "\033[94m",      # Blue
        "SUCCESS": "\033[92m",   # Green
        "WARNING": "\033[93m",   # Yellow
        "ERROR": "\033[91m",     # Red
    }
    reset = "\033[0m"

    color = colors.get(status, "")
    prefix = f"[{status}]"

    # Use stderr for non-success messages
    output = sys.stderr if status in ("WARNING", "ERROR") else sys.stdout
    print(f"{color}{prefix}{reset} {message}", file=output)
