from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="sd-image-recovery",
    version="0.1.0",
    author="SD Recovery Tool",
    description="A tool to recover deleted images from SD cards on macOS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/szelenka/sd-image-recovery",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: System :: Recovery Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: MacOS",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.1.0",
        "Pillow>=10.0.0",
        "tqdm>=4.65.0",
    ],
    entry_points={
        "console_scripts": [
            "sd-recovery=sd_recovery.cli:main",
        ],
    },
)
