"""
NSEW Image Stitcher - Setup Configuration
Multi-Electrode Array (MEA) microscopy image stitching application
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="nsew-image-stitcher",
    version="0.1.0",
    author="Image MEA Dulce Team",
    description="GUI application for stitching MEA microscopy images by spatial quadrants (N/S/E/W)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jiang-lab-retina/mea_image_alignment",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Image Processing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "nsew-stitcher=main:main",
        ],
    },
)

