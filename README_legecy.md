# Image MEA Dulce

**Image processing program for Multi-Electrode Array (MEA) data alignment with GUI interface**

## Overview

Image MEA Dulce is a scientific image processing tool designed for aligning and analyzing microscopy data from Multi-Electrode Array experiments. The application provides an intuitive graphical user interface that allows researchers to configure key processing parameters and perform reproducible data alignment operations.

## Features

- **Data Alignment**: Advanced image alignment algorithms for MEA microscopy data
- **GUI Interface**: User-friendly interface for parameter configuration and visualization
- **Reproducible Processing**: All processing operations are fully reproducible with saved configurations
- **Data Integrity**: Original raw data is never modified; all processing operates on copies
- **Quality Validation**: Built-in quality metrics and validation for processing results

## Supported Formats

- **Primary**: `.czi` (Carl Zeiss Image format) - native microscopy data format
- **Additional formats**: TBD based on requirements

## Project Status

🚧 **In Development** - Constitution and architectural guidelines established

## Architecture Principles

This project follows strict architectural principles documented in the [Constitution](./.specify/memory/constitution.md):

1. **Data Integrity First**: Preservation of scientific data throughout all processing
2. **User-Friendly GUI**: Intuitive interface with real-time feedback
3. **Reproducible Processing**: Full reproducibility with parameter tracking
4. **Validation & Quality Control**: Automated quality assessment
5. **Modular Architecture**: Separation of processing logic from GUI

## Features

### NSEW Image Stitcher (v0.1.0)
The first feature of Image MEA Dulce is a specialized tool for stitching microscopy images based on spatial quadrants:

- **Quadrant Visualization**: Load and view up to 4 images arranged by N/S/E/W keywords
- **Automatic Keyword Detection**: Intelligently identifies image positions from filenames
- **Multi-Format Support**: Compatible with `.czi`, `.lsm`, `.tif`, and `.tiff` files
- **Advanced Stitching**: High-quality image alignment and blending with configurable parameters
- **Quality Metrics**: Real-time feedback on stitching quality and alignment confidence
- **Large Image Handling**: Automatic downsampling for memory-efficient display of large results

## Getting Started

### Prerequisites
- Python 3.10 or higher
- 4GB RAM minimum (8GB recommended for large images)
- Display with at least 1920x1080 resolution

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/jiang-lab-retina/mea_image_alignment.git
cd mea_image_alignment
```

2. **Create a virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Install the package**:
```bash
pip install -e .
```

### Quick Start

1. **Launch the application**:
```bash
python main.py
```

2. **Load images**:
   - Click "Load Images" button
   - Select 1-4 microscopy images with NSEW keywords in filenames
   - Example: `experiment_NE.czi`, `experiment_SW.czi`

3. **View quadrants**:
   - Images are automatically arranged by spatial position
   - Use zoom and pan controls to inspect details
   - Verify alignment before stitching

4. **Stitch images**:
   - Click "Stitch Images" button
   - Adjust parameters (optional): blend mode, overlap threshold, alignment method
   - Monitor progress in real-time
   - View quality metrics in result window

5. **Save results**:
   - Use "Save As" button in result window
   - Choose format: TIFF (lossless), PNG, or JPEG
   - Full resolution saved to disk, optimized view displayed

### Chip Image Stitching (v0.2.0)

The application now supports stitching chip images using alignment parameters from original stitching, providing ~50% time savings:

1. **Perform original stitching first**:
   - Load and stitch original quadrant images (e.g., `prefix_NE.czi`, `prefix_NW.czi`)
   - Alignment parameters are automatically saved to `.image_mea_alignment_params.json`

2. **Click "Stitch Chip Images"**:
   - Automatically discovers chip images (e.g., `prefix_chipNE.czi`, `prefix_chipNW.czi`)
   - Shows discovery summary with found/missing chips and dimension mismatches

3. **Review and confirm**:
   - Check chip image discovery results
   - Missing chips will use black placeholders
   - Dimension mismatches will be automatically resized

4. **Monitor progress**:
   - Real-time progress updates during chip stitching
   - Bypasses feature detection for faster processing
   - Applies stored alignment from original stitching

5. **View chip results**:
   - Result window displays chip-specific metadata
   - Shows found chips, placeholders, and dimension transformations
   - Includes processing time and quality metrics

**Key Features**:
- **Automatic Discovery**: Finds chip images using `prefix_chipQUADRANT.ext` pattern
- **Missing Chip Handling**: Generates pure black (RGB: 0,0,0) placeholders
- **Dimension Normalization**: Automatically resizes mismatched chip dimensions
- **Alignment Reuse**: Bypasses feature detection by reusing original position shifts
- **Persistent Parameters**: Alignment saved/loaded automatically for workflow continuity

### Example Filenames
The application detects spatial position from keywords:
- `2025.10.22-09.58.50-4141-opnT2_NE.czi` → North-East quadrant
- `sample_northwest_image.lsm` → North-West quadrant
- `data_SE_final.tif` → South-East quadrant
- `experiment-SW.tiff` → South-West quadrant

## Development

For development guidelines and workflow, see:
- [Constitution](./.specify/memory/constitution.md) - Core principles and standards
- [Templates](./.specify/templates/) - Specification and planning templates

## License

*TBD*

## Contributors

*TBD*

