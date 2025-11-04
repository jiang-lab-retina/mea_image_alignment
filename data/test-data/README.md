# Test Data Directory

This directory contains test microscopy images for NSEW Image Stitcher development and validation.

## Directory Purpose

- **Unit tests**: Small synthetic test images for fast validation
- **Integration tests**: Real microscopy samples for realistic scenarios
- **Performance tests**: Large images for memory and speed benchmarking

## Obtaining Test Images

### Option 1: Use Existing Project Data
The project contains real microscopy data in `raw_data/` directories:

```
raw_data/2025.10.22_opnT2/
raw_data/2025.10.23_opnT2/
```

**Recommended test files** (smaller, representative samples):
- `raw_data/2025.10.22_opnT2/2025.10.22-09.58.50-4141-opnT2_NE.czi` (North-East)
- `raw_data/2025.10.22_opnT2/2025.10.22-09.58.50-4141-opnT2_NW.czi` (North-West)
- `raw_data/2025.10.22_opnT2/2025.10.22-09.58.50-4141-opnT2_SE.czi` (South-East)
- `raw_data/2025.10.22_opnT2/2025.10.22-09.58.50-4141-opnT2_SW.czi` (South-West)

### Option 2: Create Synthetic Test Images
For unit tests, use the test fixture generators in `tests/fixtures/`:

```python
# Generate synthetic quadrant images
from tests.fixtures.image_generator import create_test_quadrant_set

# Create 4 synthetic images with known overlap
images = create_test_quadrant_set(
    size=(512, 512),
    overlap_px=50,
    pattern="checkerboard"
)
```

### Option 3: Download Public Datasets
For additional validation, download from public repositories:

- **Cell Image Library**: https://www.cellimagelibrary.org/
- **Image Data Resource (IDR)**: https://idr.openmicroscopy.org/
- **Zeiss Sample Images**: https://www.zeiss.com/microscopy/en/products/software/zeiss-zen-lite.html

## File Format Requirements

### Supported Formats
- `.czi` - Carl Zeiss Image (native format)
- `.lsm` - Leica Laser Scanning Microscope
- `.tif` / `.tiff` - Tagged Image File Format

### Naming Conventions for Tests
Include spatial keywords (case-insensitive):
- **North**: `north`, `n`, `top`
- **South**: `south`, `s`, `bottom`
- **East**: `east`, `e`, `right`
- **West**: `west`, `w`, `left`

Examples:
- `test_NE.czi` ✅
- `sample_northwest.lsm` ✅
- `data_SE_channel1.tif` ✅
- `experiment-SW.tiff` ✅

## Test Image Specifications

### Small (Unit Tests)
- **Size**: 256x256 to 512x512 pixels
- **File size**: <5 MB
- **Purpose**: Fast validation of core functions
- **Overlap**: 10-20% with adjacent quadrants

### Medium (Integration Tests)
- **Size**: 1024x1024 to 2048x2048 pixels
- **File size**: 10-50 MB
- **Purpose**: Realistic stitching scenarios
- **Overlap**: 10-15% with adjacent quadrants

### Large (Performance Tests)
- **Size**: 4096x4096+ pixels
- **File size**: >100 MB
- **Purpose**: Memory and performance benchmarking
- **Overlap**: 5-10% with adjacent quadrants

## Directory Structure

```
data/test-data/
├── README.md (this file)
├── unit/
│   ├── synthetic_NE_256x256.tif
│   ├── synthetic_NW_256x256.tif
│   ├── synthetic_SE_256x256.tif
│   └── synthetic_SW_256x256.tif
├── integration/
│   ├── real_sample_NE.czi
│   ├── real_sample_NW.czi
│   ├── real_sample_SE.czi
│   └── real_sample_SW.czi
└── performance/
    └── large_4096x4096_NE.czi
```

## Git Ignore

Test data files (`.czi`, `.lsm`, `.tif`, `.tiff`) are **excluded from git** to avoid repository bloat. Only this README and test fixture scripts are version-controlled.

## Usage in Tests

### Loading Test Data
```python
import pytest
from pathlib import Path

@pytest.fixture
def test_data_dir():
    return Path(__file__).parent.parent / "data" / "test-data"

def test_load_quadrant(test_data_dir):
    image_path = test_data_dir / "unit" / "synthetic_NE_256x256.tif"
    # ... test code
```

### Using Real Project Data
```python
@pytest.fixture
def real_data_dir():
    return Path(__file__).parent.parent / "raw_data" / "2025.10.22_opnT2"

def test_real_stitching(real_data_dir):
    ne_path = real_data_dir / "2025.10.22-09.58.50-4141-opnT2_NE.czi"
    # ... test code
```

## Quality Requirements

Test images should:
- ✅ Have detectable overlap regions (10-20%)
- ✅ Contain distinct features for alignment (edges, patterns)
- ✅ Be free from corruption or encoding errors
- ✅ Match expected file format specifications
- ✅ Include spatial keywords in filenames

## Notes

- Test data is **not committed to git** - keep files local
- For CI/CD, generate synthetic test images on-the-fly
- Use small files (<10MB) for fast test execution
- Document any specific test scenarios in test docstrings

