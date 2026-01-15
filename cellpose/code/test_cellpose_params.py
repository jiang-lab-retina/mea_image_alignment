#!/usr/bin/env python3
"""
Test different Cellpose parameter combinations on a single image (NW quadrant).
Visualizes results in subplots to help find optimal settings.

Usage:
    python test_cellpose_params.py --input-dir "raw_data/2025.10.22_opnT2" --prefix "2025.10.22-10.34.56-4134-opnT2_"
"""

import argparse
import logging
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class CellposeConfig:
    """Configuration for a single Cellpose run."""
    model_type: str
    diameter: Optional[float]
    flow_threshold: float
    cellprob_threshold: float
    min_size: int = 15
    normalize: bool = True
    invert: bool = False
    augment: bool = False
    niter: Optional[int] = None
    
    def __str__(self):
        d = f"d={self.diameter}" if self.diameter else "d=auto"
        extras = []
        if self.min_size != 15:
            extras.append(f"min={self.min_size}")
        if not self.normalize:
            extras.append("no_norm")
        if self.invert:
            extras.append("inv")
        if self.augment:
            extras.append("aug")
        if self.niter:
            extras.append(f"nit={self.niter}")
        extra_str = ", " + ", ".join(extras) if extras else ""
        return f"{self.model_type}, {d}, ft={self.flow_threshold}, cp={self.cellprob_threshold}{extra_str}"


@dataclass
class DetectionResult:
    """Results from a Cellpose detection run."""
    config: CellposeConfig
    masks: np.ndarray
    num_cells: int
    cell_centers: List[Tuple[float, float]]


def load_quadrant_image(input_dir: str, prefix: str, quadrant: str) -> np.ndarray:
    """Load a specific quadrant image (NW, NE, SW, SE)."""
    input_path = Path(input_dir)
    
    # Try CZI first
    czi_pattern = f"{prefix}{quadrant}.czi"
    czi_matches = list(input_path.glob(czi_pattern))
    
    if czi_matches:
        try:
            import czifile
            with czifile.CziFile(str(czi_matches[0])) as czi:
                img_data = czi.asarray()
            
            original_shape = img_data.shape
            original_dtype = img_data.dtype
            
            # Squeeze singleton dimensions
            while img_data.ndim > 2 and img_data.shape[0] == 1:
                img_data = img_data.squeeze(axis=0)
            while img_data.ndim > 2 and img_data.shape[-1] == 1:
                img_data = img_data.squeeze(axis=-1)
            
            before_proj_shape = img_data.shape
            projection_method = "none"
            
            # Handle Z-stack: the two LARGEST dimensions are Y and X (spatial)
            # Smaller dimensions are Z (depth) and/or C (channels)
            if img_data.ndim == 2:
                img = img_data
                projection_method = "already 2D"
            elif img_data.ndim == 3:
                # Find which axis is NOT one of the two largest (that's Z or C)
                shape = img_data.shape
                sorted_dims = sorted(range(3), key=lambda i: shape[i], reverse=True)
                smallest_axis = sorted_dims[2]  # This is Z or C
                
                # Mean project along the smallest axis (Z)
                img = img_data.mean(axis=smallest_axis)
                projection_method = f"mean along axis {smallest_axis} (size={shape[smallest_axis]})"
            elif img_data.ndim == 4:
                # Find the two largest dimensions (Y, X)
                shape = img_data.shape
                sorted_dims = sorted(range(4), key=lambda i: shape[i], reverse=True)
                
                # Mean project along Z (the larger of the two smaller dims), take first of C
                # First, take slice along smallest axis (likely C)
                smallest_axis = sorted_dims[3]
                img_3d = np.take(img_data, 0, axis=smallest_axis)
                
                # Then mean project along the remaining non-spatial axis
                remaining_shape = img_3d.shape
                sorted_remaining = sorted(range(3), key=lambda i: remaining_shape[i], reverse=True)
                z_axis = sorted_remaining[2]  # Smallest remaining is Z
                img = img_3d.mean(axis=z_axis)
                projection_method = f"slice axis {smallest_axis}, mean along axis {z_axis}"
            else:
                # Higher dimensions: collapse to 2D by taking means/slices
                projection_method = "iterative mean"
                while img_data.ndim > 2:
                    smallest_axis = np.argmin(img_data.shape)
                    img_data = img_data.mean(axis=smallest_axis)
                img = img_data
            
            # Normalize based on ORIGINAL dtype (after mean, dtype becomes float64)
            if original_dtype == np.uint16 or img.max() > 255:
                # 16-bit data: normalize to 0-255
                img = (img / 65535.0 * 255).astype(np.float32)
            else:
                img = img.astype(np.float32)
            
            logger.info(f"{quadrant} CZI [{czi_matches[0].name}]: original={original_shape} dtype={original_dtype}, "
                       f"before_proj={before_proj_shape}, method='{projection_method}', "
                       f"final={img.shape}")
            return img
        except ImportError:
            logger.warning("czifile not installed")
    
    # Try TIFF/PNG
    import cv2
    for ext in ['*.tif', '*.tiff', '*.png']:
        pattern = f"{prefix}{quadrant}{ext[1:]}"
        matches = list(input_path.glob(pattern))
        if matches:
            img = cv2.imread(str(matches[0]), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                logger.info(f"Loaded {quadrant}: {matches[0].name}")
                return img.astype(np.float32)
    
    raise FileNotFoundError(f"Could not find {quadrant} image with prefix {prefix}")


def load_nw_image(input_dir: str, prefix: str) -> np.ndarray:
    """Load the NW quadrant image (backwards compatibility)."""
    return load_quadrant_image(input_dir, prefix, "NW")


def run_cellpose(image: np.ndarray, config: CellposeConfig, use_gpu: bool = False) -> DetectionResult:
    """Run Cellpose with a specific configuration."""
    try:
        from cellpose import models
        import cellpose
        version = getattr(cellpose, '__version__', '0.0.0')
        is_v4 = version.startswith('4') or version.startswith('3')
    except ImportError:
        logger.error("Cellpose not installed. Run: pip install cellpose")
        return DetectionResult(config, np.zeros_like(image, dtype=np.int32), 0, [])
    
    # Image should already be normalized to 0-255 range
    img_norm = np.clip(image, 0, 255).astype(np.uint8)
    
    # For Cellpose v4: convert grayscale to 3-channel RGB
    if is_v4 and img_norm.ndim == 2:
        img_norm = np.stack([img_norm, img_norm, img_norm], axis=-1)
    
    # Create model - handle different API versions
    try:
        if is_v4:
            # Cellpose v4 uses CellposeModel with 'model=' parameter
            # Note: v4 uses CPSAM by default, model_type is ignored
            # Try to load specific model, fallback to default
            try:
                model = models.CellposeModel(model=config.model_type, gpu=use_gpu)
            except:
                # v4 default model (CPSAM)
                model = models.CellposeModel(gpu=use_gpu)
        else:
            model = models.CellposeModel(model_type=config.model_type, gpu=use_gpu)
    except (AttributeError, TypeError) as e:
        try:
            # Try alternative
            model = models.Cellpose(model_type=config.model_type, gpu=use_gpu)
        except:
            logger.error(f"Failed to create model: {e}")
            return DetectionResult(config, np.zeros_like(image, dtype=np.int32), 0, [])
    
    # Run segmentation
    try:
        # Build eval kwargs - channels deprecated in v4.x
        eval_kwargs = {
            'diameter': config.diameter,
            'flow_threshold': config.flow_threshold,
            'cellprob_threshold': config.cellprob_threshold,
            'min_size': config.min_size,
            'normalize': config.normalize,
            'invert': config.invert,
            'augment': config.augment,
        }
        
        # Add version-specific parameters
        if is_v4:
            # v4: specify channel_axis for H×W×C format (last axis is channels)
            eval_kwargs['channel_axis'] = -1
        else:
            eval_kwargs['channels'] = [0, 0]  # Only for older versions
        
        if config.niter is not None:
            eval_kwargs['niter'] = config.niter
        
        result = model.eval(img_norm, **eval_kwargs)
        masks = result[0] if isinstance(result, tuple) else result
    except Exception as e:
        logger.error(f"Cellpose failed for {config}: {e}")
        return DetectionResult(config, np.zeros_like(image, dtype=np.int32), 0, [])
    
    # Extract cell centers
    cell_centers = []
    unique_labels = np.unique(masks)
    for label in unique_labels:
        if label == 0:
            continue
        coords = np.where(masks == label)
        if len(coords[0]) > 0:
            cy = np.mean(coords[0])
            cx = np.mean(coords[1])
            cell_centers.append((cx, cy))
    
    return DetectionResult(config, masks, len(cell_centers), cell_centers)


def create_visualization(image: np.ndarray, results: List[DetectionResult], output_path: str):
    """Create visualization with subplots for each configuration."""
    n_results = len(results)
    
    # Calculate grid dimensions
    if n_results <= 4:
        n_cols = 2
    elif n_results <= 9:
        n_cols = 3
    else:
        n_cols = 4
    
    n_rows = (n_results + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 5 * n_rows))
    if n_rows == 1 and n_cols == 1:
        axes = np.array([[axes]])
    elif n_rows == 1:
        axes = axes.reshape(1, -1)
    elif n_cols == 1:
        axes = axes.reshape(-1, 1)
    
    for idx, result in enumerate(results):
        row = idx // n_cols
        col = idx % n_cols
        ax = axes[row, col]
        
        # Show image
        ax.imshow(image, cmap='gray', vmin=0, vmax=255)
        
        # Overlay cell centers
        for cx, cy in result.cell_centers:
            circle = Circle((cx, cy), 8, color='red', fill=False, linewidth=1.5)
            ax.add_patch(circle)
            ax.plot(cx, cy, 'r.', markersize=3)
        
        # Show mask outlines
        if result.num_cells > 0:
            from scipy import ndimage
            for label in np.unique(result.masks):
                if label == 0:
                    continue
                mask = result.masks == label
                # Find contour
                contours = ndimage.find_objects(mask.astype(int))
        
        ax.set_title(f"{result.config}\nCells: {result.num_cells}", fontsize=9)
        ax.axis('off')
    
    # Hide empty subplots
    for idx in range(n_results, n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        axes[row, col].axis('off')
    
    plt.suptitle('Cellpose Parameter Comparison', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved visualization to {output_path}")


def create_mask_visualization(image: np.ndarray, results: List[DetectionResult], output_path: str):
    """Create visualization showing segmentation masks."""
    n_results = len(results)
    
    if n_results <= 4:
        n_cols = 2
    elif n_results <= 9:
        n_cols = 3
    else:
        n_cols = 4
    
    n_rows = (n_results + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 5 * n_rows))
    if n_rows == 1 and n_cols == 1:
        axes = np.array([[axes]])
    elif n_rows == 1:
        axes = axes.reshape(1, -1)
    elif n_cols == 1:
        axes = axes.reshape(-1, 1)
    
    for idx, result in enumerate(results):
        row = idx // n_cols
        col = idx % n_cols
        ax = axes[row, col]
        
        # Create RGB overlay
        rgb = np.stack([image/255, image/255, image/255], axis=-1)
        
        # Color the masks
        if result.num_cells > 0:
            # Create random colors for each cell
            np.random.seed(42)
            colors = np.random.rand(result.num_cells + 1, 3)
            colors[0] = [0, 0, 0]  # Background
            
            mask_rgb = colors[result.masks.astype(int) % len(colors)]
            
            # Blend with original
            alpha = 0.4
            cell_mask = result.masks > 0
            rgb[cell_mask] = (1 - alpha) * rgb[cell_mask] + alpha * mask_rgb[cell_mask]
        
        ax.imshow(rgb)
        ax.set_title(f"{result.config}\nCells: {result.num_cells}", fontsize=9)
        ax.axis('off')
    
    # Hide empty subplots
    for idx in range(n_results, n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        axes[row, col].axis('off')
    
    plt.suptitle('Cellpose Segmentation Masks', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved mask visualization to {output_path}")


def normalize_image(image: np.ndarray) -> np.ndarray:
    """Normalize image to 0-255 range using percentile stretch."""
    if image.max() > 255:
        p1, p99 = np.percentile(image, (1, 99))
        image = np.clip((image - p1) / (p99 - p1 + 1e-6) * 255, 0, 255).astype(np.float32)
    return image


def main():
    parser = argparse.ArgumentParser(description="Test Cellpose parameters")
    parser.add_argument('--input-dir', required=True, help="Directory containing images")
    parser.add_argument('--prefix', required=True, help="File prefix")
    parser.add_argument('--output-dir', default='cellpose/output', help="Output directory")
    parser.add_argument('--gpu', action='store_true', help="Use GPU/MPS")
    parser.add_argument('--all-quadrants', action='store_true', help="Test on all quadrants (NW, NE, SW, SE)")
    
    args = parser.parse_args()
    
    # Best config from parameter tuning
    best_config = CellposeConfig('cyto3', 15, 0.1, -3.5, min_size=325)
    
    quadrants = ['NW', 'NE', 'SW', 'SE'] if args.all_quadrants else ['NW']
    output_dir = Path(args.output_dir)
    
    all_results = {}
    
    for quadrant in quadrants:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {quadrant} quadrant")
        logger.info('='*60)
        
        # Load image
        try:
            image = load_quadrant_image(args.input_dir, args.prefix, quadrant)
        except FileNotFoundError as e:
            logger.warning(f"Could not load {quadrant}: {e}")
            continue
        
        # Normalize
        logger.info(f"Raw image stats: min={image.min():.1f}, max={image.max():.1f}")
        image = normalize_image(image)
        logger.info(f"Normalized stats: min={image.min():.1f}, max={image.max():.1f}")
        
        # Run Cellpose
        logger.info(f"Running Cellpose with: {best_config}")
        result = run_cellpose(image, best_config, use_gpu=args.gpu)
        logger.info(f"  -> Detected {result.num_cells} cells")
        
        all_results[quadrant] = {
            'image': image,
            'result': result
        }
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("RESULTS SUMMARY")
    logger.info("="*60)
    total_cells = 0
    for quadrant, data in all_results.items():
        logger.info(f"  {quadrant}: {data['result'].num_cells} cells")
        total_cells += data['result'].num_cells
    logger.info(f"  TOTAL: {total_cells} cells")
    
    # Create visualization for all quadrants
    if len(all_results) > 1:
        fig, axes = plt.subplots(2, 2, figsize=(16, 16))
        quadrant_positions = {'NW': (0, 0), 'NE': (0, 1), 'SW': (1, 0), 'SE': (1, 1)}
        
        for quadrant, (row, col) in quadrant_positions.items():
            ax = axes[row, col]
            if quadrant in all_results:
                data = all_results[quadrant]
                ax.imshow(data['image'], cmap='gray', vmin=0, vmax=255)
                
                # Draw cell centers
                for cx, cy in data['result'].cell_centers:
                    circle = Circle((cx, cy), 10, fill=False, color='red', linewidth=2)
                    ax.add_patch(circle)
                
                ax.set_title(f"{quadrant}: {data['result'].num_cells} cells", fontsize=14, fontweight='bold')
            else:
                ax.set_title(f"{quadrant}: Not loaded", fontsize=14)
                ax.axis('off')
            ax.set_xticks([])
            ax.set_yticks([])
        
        plt.suptitle(f'All Quadrants - {best_config}\nTotal: {total_cells} cells', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.savefig(str(output_dir / "cellpose_all_quadrants.png"), dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved all quadrants visualization to cellpose_all_quadrants.png")
    else:
        # Single quadrant visualization
        for quadrant, data in all_results.items():
            results = [data['result']]
            create_visualization(data['image'], results, str(output_dir / "cellpose_params_centers.png"))
            create_mask_visualization(data['image'], results, str(output_dir / "cellpose_params_masks.png"))
    
    # Save results to JSON
    import json
    results_data = {
        "config": {
            "model": best_config.model_type,
            "diameter": best_config.diameter,
            "flow_threshold": best_config.flow_threshold,
            "cellprob_threshold": best_config.cellprob_threshold,
            "min_size": best_config.min_size
        },
        "quadrants": {
            q: {"num_cells": d['result'].num_cells}
            for q, d in all_results.items()
        },
        "total_cells": total_cells
    }
    
    with open(output_dir / "cellpose_params_results.json", 'w') as f:
        json.dump(results_data, f, indent=2)
    logger.info(f"Saved results to cellpose_params_results.json")
    
    logger.info("\n*** TESTING COMPLETE ***")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
