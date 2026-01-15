# Image MEA Alignment - Quadrant Stitching

This project provides tools for aligning and stitching 2×2 quadrant microscopy images (NW, NE, SW, SE) for MEA (Microelectrode Array) imaging.

## Recommended Method: Cellpose-based Alignment

The **Cellpose CLI method** provides the best alignment results by detecting cells in each quadrant and matching cell centers in overlapping regions.

### Installation

```bash
pip install cellpose torch torchvision  # For Apple Silicon (MPS)
# OR
pip install cellpose[gpu]  # For CUDA GPU
```

### Usage

Run from the project root directory:

```bash
# Basic usage with GPU/MPS acceleration
python cellpose/code/align_cellpose.py \
    --input-dir "raw_data/2025.10.22_opnT2" \
    --prefix "2025.10.22-10.34.56-4134-opnT2_" \
    --gpu

# Full options
python cellpose/code/align_cellpose.py \
    --input-dir "raw_data/2025.10.22_opnT2" \
    --prefix "2025.10.22-10.34.56-4134-opnT2_" \
    --output-dir "cellpose/output" \
    --diameter 15 \
    --flow-threshold 0.1 \
    --cellprob-threshold -3.5 \
    --min-size 325 \
    --overlap 70 \
    --zoom \
    --max-zoom 5 \
    --gpu
```

### Optimized Parameters

The following parameters have been tuned for best cell detection:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `--diameter` | `15` | Expected cell diameter (pixels) |
| `--flow-threshold` | `0.1` | Flow threshold for segmentation |
| `--cellprob-threshold` | `-3.5` | Cell probability threshold |
| `--min-size` | `325` | Minimum cell area (pixels) |
| `--overlap` | `70` | Expected overlap between quadrants (%) |

> **Note:** Cellpose v4.x uses **CPSAM** (Cellpose Segment Anything Model) by default and ignores the `--model` parameter. CPSAM provides better accuracy than previous models (cyto, cyto2, cyto3).

### Output Files

| File | Description |
|------|-------------|
| `cellpose_alignment.png` | Visualization of cell detection and alignment |
| `cellpose_stitched.png` | Stitched image (mean projection) |
| `cellpose_stitched_overlay.png` | Stitched image (overlay, NW on top) |
| `cellpose_stitched_comparison.png` | Side-by-side comparison |
| `cellpose_chip_stitched.png` | Chip layer stitched (mean) |
| `cellpose_chip_overlay.png` | Chip layer stitched (overlay) |
| `cellpose_alignment_params.json` | Alignment parameters (dx, dy, zoom) |

### Parameter Testing

To test different Cellpose parameters on a single quadrant:

```bash
python cellpose/code/test_cellpose_params.py \
    --input-dir "raw_data/2025.10.22_opnT2" \
    --prefix "2025.10.22-10.34.56-4134-opnT2_" \
    --gpu

# Test on all quadrants with best parameters
python cellpose/code/test_cellpose_params.py \
    --input-dir "raw_data/2025.10.22_opnT2" \
    --prefix "2025.10.22-10.34.56-4134-opnT2_" \
    --gpu \
    --all-quadrants
```

---

## Alternative CLI Methods

### CV2-based Alignment

Uses OpenCV for alignment via ECC (Enhanced Correlation Coefficient) or feature matching.

```bash
python cv2_alignment/code/align_cv2.py \
    --input-dir "raw_data/2025.10.22_opnT2" \
    --prefix "2025.10.22-10.34.56-4134-opnT2_" \
    --method ecc \
    --max-rotation 5 \
    --max-zoom 5
```

**Note:** CV2 methods are less reliable than Cellpose for cell-dense images.

### Grid Optimization

Grid-based NCC (Normalized Cross-Correlation) optimization methods:

```bash
python grid_optimization/code/optimize_alignment.py \
    --input-dir "raw_data/2025.10.22_opnT2" \
    --prefix "2025.10.22-10.34.56-4134-opnT2_"
```

**Note:** Grid methods work for general image alignment but are less accurate than cell-based matching.

---

## GUI (Deprecated)

⚠️ **The GUI interface is not working well and has been abandoned.**

The GUI code remains in `src/gui/` for reference but is not maintained. Use the CLI methods instead.

---

## Project Structure

```
Image_MEA_Dulce/
├── cellpose/                    # Cellpose-based alignment (RECOMMENDED)
│   ├── code/
│   │   ├── align_cellpose.py    # Main alignment script
│   │   └── test_cellpose_params.py
│   ├── output/                  # Generated plots and results
│   └── logs/
│
├── cv2_alignment/               # OpenCV-based alignment
│   ├── code/
│   │   └── align_cv2.py
│   ├── output/
│   └── logs/
│
├── grid_optimization/           # Grid NCC optimization
│   ├── code/
│   │   ├── optimize_alignment.py
│   │   └── optimize_grid_alignment.py
│   ├── output/
│   └── logs/
│
├── raw_data/                    # Input CZI files
├── src/                         # Core library (GUI deprecated)
├── main.py                      # Legacy entry point
└── requirements.txt
```

---

## Input Format

- **CZI files**: Grayscale Z-stack microscopy images
- **Naming convention**: `{prefix}{quadrant}.czi` (e.g., `2025.10.22-10.34.56-4134-opnT2_NW.czi`)
- **Chip images**: `{prefix}chip{quadrant}.czi`
- **Quadrants**: NW, NE, SW, SE

Z-stacks are automatically mean-projected along the Z-axis before processing.
