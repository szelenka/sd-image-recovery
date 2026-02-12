"""Unit tests for PhotoRec wrapper."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from sd_recovery.core.photorec_wrapper import PhotoRecWrapper, PhotoRecResult
from sd_recovery.utils.errors import PhotoRecNotFoundError, PhotoRecExecutionError


class TestPhotoRecWrapper:
    """Test PhotoRec wrapper functionality."""

    @patch('sd_recovery.core.photorec_wrapper.shutil.which')
    def test_find_photorec_success(self, mock_which):
        mock_which.return_value = '/usr/local/bin/photorec'
        wrapper = PhotoRecWrapper()
        assert wrapper.photorec_path == '/usr/local/bin/photorec'

    @patch('sd_recovery.core.photorec_wrapper.shutil.which')
    def test_find_photorec_not_found(self, mock_which):
        mock_which.return_value = None
        with pytest.raises(PhotoRecNotFoundError):
            PhotoRecWrapper()

    def test_build_command_basic(self, temp_dir):
        wrapper = PhotoRecWrapper(photorec_path='/usr/local/bin/photorec')

        cmd = wrapper.build_command(
            device_path='/dev/disk2',
            output_dir=temp_dir
        )

        assert '/usr/local/bin/photorec' in cmd
        assert '/d' in cmd
        assert str(temp_dir) in cmd
        assert '/cmd' in cmd
        assert '/dev/disk2' in cmd
        # Check that 'search' is in the combined options string
        assert any('search' in str(item) for item in cmd)

    def test_build_command_with_paranoid(self, temp_dir):
        wrapper = PhotoRecWrapper(photorec_path='/usr/local/bin/photorec')

        cmd = wrapper.build_command(
            device_path='/dev/disk2',
            output_dir=temp_dir,
            paranoid=True
        )

        # Check that 'options,paranoid' is in the combined options string
        assert any('options,paranoid' in str(item) for item in cmd)

    def test_build_command_with_file_types(self, temp_dir):
        wrapper = PhotoRecWrapper(photorec_path='/usr/local/bin/photorec')

        cmd = wrapper.build_command(
            device_path='/dev/disk2',
            output_dir=temp_dir,
            file_types=['jpg', 'png']
        )

        # Check that jpg and png are enabled
        assert any('fileopt,jpg,enable' in str(item) for item in cmd)
        assert any('fileopt,png,enable' in str(item) for item in cmd)

    @patch('sd_recovery.core.photorec_wrapper.subprocess.Popen')
    def test_execute_success(self, mock_popen, temp_dir):
        wrapper = PhotoRecWrapper(photorec_path='/usr/local/bin/photorec')

        # Create mock recup directory and files
        recup_dir = temp_dir / "recup_dir.1"
        recup_dir.mkdir()
        (recup_dir / "f0000001.jpg").touch()
        (recup_dir / "f0000002.jpg").touch()

        # Mock subprocess
        mock_process = MagicMock()
        mock_process.stdout = [
            "PhotoRec 7.2\n",
            "Pass 1 - Reading sector 0/1000\n",
            "2 files recovered\n"
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        result = wrapper.execute(
            device_path='/dev/disk2',
            output_dir=temp_dir
        )

        assert isinstance(result, PhotoRecResult)
        assert result.files_recovered >= 2

    @patch('sd_recovery.core.photorec_wrapper.subprocess.Popen')
    def test_execute_failure(self, mock_popen, temp_dir):
        wrapper = PhotoRecWrapper(photorec_path='/usr/local/bin/photorec')

        # Mock failed subprocess
        mock_process = MagicMock()
        mock_process.stdout = ["Error occurred\n"]
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process

        with pytest.raises(PhotoRecExecutionError):
            wrapper.execute(
                device_path='/dev/disk2',
                output_dir=temp_dir
            )


class TestPhotoRecResult:
    """Test PhotoRecResult object."""

    def test_photorec_result_creation(self, temp_dir):
        result = PhotoRecResult(
            output_dir=temp_dir,
            recup_dirs=[temp_dir / "recup_dir.1"],
            files_recovered=5,
            recovered_files=[],
            output_lines=["test output"]
        )

        assert result.output_dir == temp_dir
        assert result.files_recovered == 5
        assert len(result.recup_dirs) == 1

    def test_photorec_result_string(self, temp_dir):
        result = PhotoRecResult(
            output_dir=temp_dir,
            recup_dirs=[],
            files_recovered=10,
            recovered_files=[],
            output_lines=[]
        )

        result_str = str(result)
        assert "10" in result_str
        assert "PhotoRecResult" in result_str
