#!/usr/bin/env python3
"""
Cellpose-based Image Alignment for 2x2 Quadrant Stitching

Uses Cellpose 3 to identify cells, extracts cell center coordinates,
and aligns quadrants based on matching cell centers in overlap regions.

All quadrants (NE, SW, SE) are aligned relative to NW.

Author: Image MEA Alignment Project
"""

import argparse
import logging
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import numpy as np
import cv2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CellInfo:
    """Information about a detected cell."""
    center_x: float
    center_y: float
    area: float
    label: int


@dataclass
class QuadrantAlignment:
    """Alignment parameters for a single quadrant relative to NW."""
    dx: float = 0.0
    dy: float = 0.0
    rotation_deg: float = 0.0
    zoom: float = 1.0
    num_matched_cells: int = 0
    match_quality: float = 0.0
    method: str = "cellpose"


@dataclass 
class AlignmentResult:
    """Complete alignment result for all quadrants."""
    quadrants: Dict[str, QuadrantAlignment] = field(default_factory=dict)
    consistency_error: float = 0.0
    total_cells_detected: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            'quadrants': {
                q: {
                    'dx': float(qa.dx),
                    'dy': float(qa.dy),
                    'rotation_deg': float(qa.rotation_deg),
                    'zoom': float(qa.zoom),
                    'num_matched_cells': qa.num_matched_cells,
                    'match_quality': float(qa.match_quality),
                    'method': qa.method
                }
                for q, qa in self.quadrants.items()
            },
            'consistency_error': float(self.consistency_error),
            'total_cells_detected': self.total_cells_detected
        }


def load_images(input_dir: str, prefix: str) -> Dict[str, np.ndarray]:
    """Load quadrant images from CZI or TIFF files."""
    images = {}
    input_path = Path(input_dir)
    
    for quadrant in ['NW', 'NE', 'SW', 'SE']:
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
                    
                    img = img_data.mean(axis=smallest_axis)
                    projection_method = f"mean along axis {smallest_axis} (size={shape[smallest_axis]})"
                elif img_data.ndim == 4:
                    # Find the two largest dimensions (Y, X)
                    shape = img_data.shape
                    sorted_dims = sorted(range(4), key=lambda i: shape[i], reverse=True)
                    
                    # Take slice along smallest axis (likely C), then mean along Z
                    smallest_axis = sorted_dims[3]
                    img_3d = np.take(img_data, 0, axis=smallest_axis)
                    
                    remaining_shape = img_3d.shape
                    sorted_remaining = sorted(range(3), key=lambda i: remaining_shape[i], reverse=True)
                    z_axis = sorted_remaining[2]
                    img = img_3d.mean(axis=z_axis)
                    projection_method = f"slice axis {smallest_axis}, mean along axis {z_axis}"
                else:
                    # Higher dimensions: collapse to 2D
                    projection_method = "iterative mean"
                    while img_data.ndim > 2:
                        smallest_axis = np.argmin(img_data.shape)
                        img_data = img_data.mean(axis=smallest_axis)
                    img = img_data
                
                # Normalize based on ORIGINAL dtype (after mean, dtype becomes float64)
                if original_dtype == np.uint16 or img.max() > 255:
                    img = (img / 65535.0 * 255).astype(np.float32)
                else:
                    img = img.astype(np.float32)
                
                images[quadrant] = img
                logger.info(f"{quadrant} CZI [{czi_matches[0].name}]: original={original_shape} dtype={original_dtype}, "
                           f"before_proj={before_proj_shape}, method='{projection_method}', "
                           f"final={img.shape}")
                continue
            except ImportError:
                logger.warning("czifile not installed")
        
        # Try TIFF/PNG
        for ext in ['*.tif', '*.tiff', '*.png']:
            pattern = f"{prefix}{quadrant}{ext[1:]}"
            matches = list(input_path.glob(pattern))
            if matches:
                img = cv2.imread(str(matches[0]), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    images[quadrant] = img.astype(np.float32)
                    logger.info(f"Loaded {quadrant}: {matches[0].name}")
                    break
    
    return images


def load_chip_images(input_dir: str, prefix: str) -> Dict[str, np.ndarray]:
    """Load chip quadrant images."""
    images = {}
    input_path = Path(input_dir)
    
    for quadrant in ['NW', 'NE', 'SW', 'SE']:
        patterns = [f"{prefix}chip{quadrant}.czi", f"{prefix}_chip{quadrant}.czi"]
        
        for pattern in patterns:
            matches = list(input_path.glob(pattern))
            if matches:
                try:
                    import czifile
                    with czifile.CziFile(str(matches[0])) as czi:
                        img_data = czi.asarray()
                    
                    while img_data.ndim > 2 and img_data.shape[0] == 1:
                        img_data = img_data.squeeze(axis=0)
                    
                    if img_data.ndim == 4:
                        img_data = img_data[img_data.shape[0] // 2]
                    
                    original_dtype = img_data.dtype
                    
                    if img_data.ndim == 3:
                        if img_data.shape[0] < img_data.shape[-1]:
                            img = img_data[0]
                        else:
                            img = img_data[:, :, 0]
                    else:
                        img = img_data
                    
                    # Normalize based on ORIGINAL dtype
                    if original_dtype == np.uint16 or img.max() > 255:
                        img = (img / 65535.0 * 255).astype(np.float32)
                    else:
                        img = img.astype(np.float32)
                    
                    images[quadrant] = img
                    logger.info(f"Loaded chip {quadrant}: {matches[0].name}")
                    break
                except ImportError:
                    pass
    
    return images


def normalize_image(image: np.ndarray) -> np.ndarray:
    """Normalize image to 0-255 range using percentile stretch."""
    if image.max() > 255:
        p1, p99 = np.percentile(image, (1, 99))
        image = np.clip((image - p1) / (p99 - p1 + 1e-6) * 255, 0, 255).astype(np.float32)
    return image


def detect_cells_cellpose(image: np.ndarray,
                           model_type: str = 'cyto3',
                           diameter: Optional[float] = 15,
                           flow_threshold: float = 0.1,
                           cellprob_threshold: float = -3.5,
                           min_size: int = 325,
                           use_gpu: bool = False) -> Tuple[np.ndarray, List[CellInfo]]:
    """
    Detect cells using Cellpose 3.
    
    Args:
        image: Input image (grayscale)
        model_type: Cellpose model type ('cyto3', 'nuclei', 'cyto2', etc.)
        diameter: Expected cell diameter (default: 15)
        flow_threshold: Flow threshold for cell detection (default: 0.1)
        cellprob_threshold: Cell probability threshold (default: -3.5)
        min_size: Minimum cell size in pixels (default: 325)
        use_gpu: Use GPU/MPS acceleration (default: False)
        
    Returns:
        (masks, cell_infos): Segmentation masks and list of cell info
    """
    try:
        from cellpose import models
        import cellpose
        version = getattr(cellpose, '__version__', '0.0.0')
        is_v4 = version.startswith('4') or version.startswith('3')
    except ImportError:
        logger.error("Cellpose not installed. Run: pip install cellpose")
        return np.zeros_like(image, dtype=np.int32), []
    
    # Normalize image to 0-255 uint8
    img_norm = np.clip(image, 0, 255).astype(np.uint8)
    
    # For Cellpose v4: convert grayscale to 3-channel RGB
    if is_v4 and img_norm.ndim == 2:
        img_norm = np.stack([img_norm, img_norm, img_norm], axis=-1)
    
    # Create model - handle different API versions
    try:
        if is_v4:
            # Cellpose 3.x/4.x API: use model= instead of model_type=
            model = models.CellposeModel(model=model_type, gpu=use_gpu)
        else:
            model = models.CellposeModel(model_type=model_type, gpu=use_gpu)
    except (AttributeError, TypeError):
        try:
            # Fallback to older API
            model = models.Cellpose(model_type=model_type, gpu=use_gpu)
        except:
            logger.error("Failed to create Cellpose model")
            return np.zeros_like(image, dtype=np.int32), []
    
    # Run segmentation
    try:
        # Build eval kwargs - channels deprecated in v4.x
        eval_kwargs = {
            'diameter': diameter,
            'flow_threshold': flow_threshold,
            'cellprob_threshold': cellprob_threshold,
            'min_size': min_size,
        }
        
        # Add version-specific parameters
        if is_v4:
            # v4: specify channel_axis for H×W×C format (last axis is channels)
            eval_kwargs['channel_axis'] = -1
        else:
            eval_kwargs['channels'] = [0, 0]  # Only for older versions
        
        result = model.eval(img_norm, **eval_kwargs)
        masks = result[0] if isinstance(result, tuple) else result
    except Exception as e:
        logger.error(f"Cellpose eval failed: {e}")
        return np.zeros_like(image, dtype=np.int32), []
    
    # Extract cell information
    cell_infos = []
    unique_labels = np.unique(masks)
    
    for label in unique_labels:
        if label == 0:  # Skip background
            continue
        
        # Get cell mask
        cell_mask = masks == label
        
        # Calculate centroid
        coords = np.where(cell_mask)
        if len(coords[0]) == 0:
            continue
        
        center_y = np.mean(coords[0])
        center_x = np.mean(coords[1])
        area = np.sum(cell_mask)
        
        cell_infos.append(CellInfo(
            center_x=center_x,
            center_y=center_y,
            area=area,
            label=label
        ))
    
    logger.info(f"Detected {len(cell_infos)} cells")
    return masks, cell_infos


def extract_cells_in_region(cells: List[CellInfo],
                             x_min: float, x_max: float,
                             y_min: float, y_max: float) -> List[CellInfo]:
    """Extract cells within a specified region."""
    return [
        c for c in cells
        if x_min <= c.center_x <= x_max and y_min <= c.center_y <= y_max
    ]


def match_cells_by_position(cells1: List[CellInfo],
                             cells2: List[CellInfo],
                             offset: Tuple[float, float],
                             max_distance: float = 30.0) -> List[Tuple[CellInfo, CellInfo, float]]:
    """
    Match cells between two sets based on position after applying offset.
    
    Args:
        cells1: Cells from reference image
        cells2: Cells from target image
        offset: Expected (dx, dy) offset of cells2 relative to cells1
        max_distance: Maximum distance for a valid match
        
    Returns:
        List of (cell1, cell2, distance) tuples for matched pairs
    """
    if not cells1 or not cells2:
        return []
    
    dx, dy = offset
    matches = []
    used_cells2 = set()
    
    for c1 in cells1:
        best_match = None
        best_dist = float('inf')
        
        for i, c2 in enumerate(cells2):
            if i in used_cells2:
                continue
            
            # Expected position of c2 in c1's coordinate system
            c2_transformed_x = c2.center_x + dx
            c2_transformed_y = c2.center_y + dy
            
            # Distance
            dist = np.sqrt((c1.center_x - c2_transformed_x)**2 + 
                          (c1.center_y - c2_transformed_y)**2)
            
            if dist < best_dist and dist < max_distance:
                best_dist = dist
                best_match = (i, c2)
        
        if best_match is not None:
            used_cells2.add(best_match[0])
            matches.append((c1, best_match[1], best_dist))
    
    return matches


def compute_alignment_from_cells(cells1: List[CellInfo],
                                  cells2: List[CellInfo],
                                  expected_offset: Tuple[float, float],
                                  search_range: int = 50,
                                  max_match_distance: float = 30.0) -> Tuple[float, float, int, float]:
    """
    Compute alignment by matching cell centers.
    
    Args:
        cells1: Cells from reference overlap region
        cells2: Cells from target overlap region
        expected_offset: Expected (dx, dy) offset
        search_range: Search range around expected offset
        max_match_distance: Maximum distance for valid cell match
        
    Returns:
        (dx, dy, num_matches, avg_distance)
    """
    if len(cells1) < 3 or len(cells2) < 3:
        logger.warning(f"Not enough cells for alignment: {len(cells1)}, {len(cells2)}")
        return expected_offset[0], expected_offset[1], 0, 0.0
    
    best_dx, best_dy = expected_offset
    best_matches = 0
    best_avg_dist = float('inf')
    
    # Grid search around expected offset
    for ddx in range(-search_range, search_range + 1, 5):
        for ddy in range(-search_range, search_range + 1, 5):
            test_dx = expected_offset[0] + ddx
            test_dy = expected_offset[1] + ddy
            
            matches = match_cells_by_position(
                cells1, cells2, (test_dx, test_dy), max_match_distance
            )
            
            if len(matches) > best_matches:
                best_matches = len(matches)
                best_dx = test_dx
                best_dy = test_dy
                best_avg_dist = np.mean([m[2] for m in matches]) if matches else float('inf')
            elif len(matches) == best_matches and matches:
                avg_dist = np.mean([m[2] for m in matches])
                if avg_dist < best_avg_dist:
                    best_dx = test_dx
                    best_dy = test_dy
                    best_avg_dist = avg_dist
    
    # Fine-tune with finer grid
    if best_matches > 0:
        for ddx in range(-5, 6, 1):
            for ddy in range(-5, 6, 1):
                test_dx = best_dx + ddx
                test_dy = best_dy + ddy
                
                matches = match_cells_by_position(
                    cells1, cells2, (test_dx, test_dy), max_match_distance
                )
                
                if len(matches) >= best_matches and matches:
                    avg_dist = np.mean([m[2] for m in matches])
                    if len(matches) > best_matches or avg_dist < best_avg_dist:
                        best_matches = len(matches)
                        best_dx = test_dx
                        best_dy = test_dy
                        best_avg_dist = avg_dist
    
    return best_dx, best_dy, best_matches, best_avg_dist


def compute_alignment_with_rotation_zoom(cells1: List[CellInfo],
                                          cells2: List[CellInfo],
                                          initial_offset: Tuple[float, float],
                                          use_rotation: bool = True,
                                          max_rotation: float = 5.0,
                                          rotation_step: float = 0.5,
                                          use_zoom: bool = True,
                                          max_zoom_percent: float = 5.0,
                                          zoom_step: float = 1.0,
                                          image_center: Tuple[float, float] = None) -> Tuple[float, float, float, float, int, float]:
    """
    Compute alignment including rotation and zoom search.
    
    Args:
        cells1: Cells from reference
        cells2: Cells from target
        initial_offset: Initial (dx, dy)
        use_rotation: Whether to search rotation
        max_rotation: Maximum rotation to search (degrees)
        rotation_step: Rotation search step
        use_zoom: Whether to search zoom
        max_zoom_percent: Maximum zoom to search (±percent)
        zoom_step: Zoom search step (percent)
        image_center: Center of rotation/zoom
        
    Returns:
        (dx, dy, rotation_deg, zoom, num_matches, avg_distance)
    """
    if image_center is None:
        # Use centroid of cells2
        if cells2:
            image_center = (
                np.mean([c.center_x for c in cells2]),
                np.mean([c.center_y for c in cells2])
            )
        else:
            image_center = (512, 512)
    
    best_dx, best_dy = initial_offset
    best_rot = 0.0
    best_zoom = 1.0
    best_matches = 0
    best_avg_dist = float('inf')
    
    # Generate rotation values
    if use_rotation:
        rotations = np.arange(-max_rotation, max_rotation + rotation_step, rotation_step)
    else:
        rotations = [0.0]
    
    # Generate zoom values
    if use_zoom:
        zooms = [1.0 + z/100.0 for z in np.arange(-max_zoom_percent, max_zoom_percent + zoom_step, zoom_step)]
    else:
        zooms = [1.0]
    
    cx, cy = image_center
    
    for rot in rotations:
        rot_rad = np.radians(rot)
        cos_r, sin_r = np.cos(rot_rad), np.sin(rot_rad)
        
        for zoom in zooms:
            # Transform cell centers with rotation and zoom
            transformed_cells2 = []
            for c in cells2:
                # Apply zoom around center
                zx = (c.center_x - cx) * zoom + cx
                zy = (c.center_y - cy) * zoom + cy
                
                # Apply rotation around center
                rx = cos_r * (zx - cx) - sin_r * (zy - cy) + cx
                ry = sin_r * (zx - cx) + cos_r * (zy - cy) + cy
                
                transformed_cells2.append(CellInfo(rx, ry, c.area * zoom * zoom, c.label))
            
            # Compute alignment with transformed cells
            dx, dy, num_matches, avg_dist = compute_alignment_from_cells(
                cells1, transformed_cells2, initial_offset, search_range=30
            )
            
            if num_matches > best_matches or (num_matches == best_matches and avg_dist < best_avg_dist):
                best_dx, best_dy = dx, dy
                best_rot = rot
                best_zoom = zoom
                best_matches = num_matches
                best_avg_dist = avg_dist
    
    return best_dx, best_dy, best_rot, best_zoom, best_matches, best_avg_dist


def align_quadrant_to_nw(nw_cells: List[CellInfo],
                          target_cells: List[CellInfo],
                          nw_shape: Tuple[int, int],
                          direction: str,
                          overlap_percent: float = 70,
                          use_rotation: bool = False,
                          max_rotation: float = 5.0,
                          use_zoom: bool = True,
                          max_zoom_percent: float = 5.0) -> QuadrantAlignment:
    """
    Align a quadrant to NW using cell centers.
    
    Args:
        nw_cells: Cells detected in NW image
        target_cells: Cells detected in target image
        nw_shape: Shape of NW image (h, w)
        direction: 'horizontal' (NE) or 'vertical' (SW)
        overlap_percent: Expected overlap percentage
        use_rotation: Whether to search for rotation
        max_rotation: Maximum rotation to search
        use_zoom: Whether to search for zoom
        max_zoom_percent: Maximum zoom to search (±percent)
        
    Returns:
        QuadrantAlignment
    """
    h, w = nw_shape
    
    if direction == 'horizontal':
        # NE is to the right of NW
        overlap_w = int(w * overlap_percent / 100)
        
        # Cells in NW right edge
        nw_overlap_cells = extract_cells_in_region(
            nw_cells, w - overlap_w, w, 0, h
        )
        
        # Cells in target left edge
        target_overlap_cells = extract_cells_in_region(
            target_cells, 0, overlap_w, 0, h
        )
        
        # Expected offset
        expected_dx = w - overlap_w
        expected_dy = 0
        
    else:  # vertical
        # SW is below NW
        overlap_h = int(h * overlap_percent / 100)
        
        # Cells in NW bottom edge
        nw_overlap_cells = extract_cells_in_region(
            nw_cells, 0, w, h - overlap_h, h
        )
        
        # Cells in target top edge
        target_overlap_cells = extract_cells_in_region(
            target_cells, 0, w, 0, overlap_h
        )
        
        expected_dx = 0
        expected_dy = h - overlap_h
    
    logger.info(f"Overlap cells: NW={len(nw_overlap_cells)}, target={len(target_overlap_cells)}")
    
    if len(nw_overlap_cells) < 3 or len(target_overlap_cells) < 3:
        logger.warning("Not enough cells in overlap region, using expected offset")
        return QuadrantAlignment(
            dx=expected_dx, dy=expected_dy,
            num_matched_cells=0, match_quality=0.0
        )
    
    # Use combined rotation+zoom search if either is enabled
    if use_rotation or use_zoom:
        dx, dy, rot, zoom, num_matches, avg_dist = compute_alignment_with_rotation_zoom(
            nw_overlap_cells, target_overlap_cells,
            (expected_dx, expected_dy),
            use_rotation=use_rotation,
            max_rotation=max_rotation,
            use_zoom=use_zoom,
            max_zoom_percent=max_zoom_percent,
            image_center=(w/2, h/2)
        )
    else:
        dx, dy, num_matches, avg_dist = compute_alignment_from_cells(
            nw_overlap_cells, target_overlap_cells,
            (expected_dx, expected_dy)
        )
        rot = 0.0
        zoom = 1.0
    
    # Match quality: ratio of matched cells to available cells
    min_cells = min(len(nw_overlap_cells), len(target_overlap_cells))
    match_quality = num_matches / min_cells if min_cells > 0 else 0.0
    
    return QuadrantAlignment(
        dx=dx, dy=dy,
        rotation_deg=rot,
        zoom=zoom,
        num_matched_cells=num_matches,
        match_quality=match_quality,
        method="cellpose"
    )


def align_se_via_chain(all_cells: Dict[str, List[CellInfo]],
                        image_shape: Tuple[int, int],
                        ne_alignment: QuadrantAlignment,
                        sw_alignment: QuadrantAlignment,
                        overlap_percent: float = 70,
                        use_rotation: bool = False,
                        max_rotation: float = 5.0,
                        use_zoom: bool = True,
                        max_zoom_percent: float = 5.0) -> QuadrantAlignment:
    """
    Align SE quadrant via NE or SW chain.
    """
    h, w = image_shape
    overlap_h = int(h * overlap_percent / 100)
    overlap_w = int(w * overlap_percent / 100)
    
    # Path 1: SE via NE (SE is below NE)
    ne_cells = all_cells.get('NE', [])
    se_cells = all_cells.get('SE', [])
    
    # NE bottom overlap
    ne_overlap = extract_cells_in_region(ne_cells, 0, w, h - overlap_h, h)
    # SE top overlap
    se_overlap_ne = extract_cells_in_region(se_cells, 0, w, 0, overlap_h)
    
    se_via_ne_zoom = 1.0
    se_via_ne_rot = 0.0
    
    if len(ne_overlap) >= 3 and len(se_overlap_ne) >= 3:
        expected_dy_from_ne = h - overlap_h
        if use_rotation or use_zoom:
            dx1, dy1, rot1, zoom1, num1, dist1 = compute_alignment_with_rotation_zoom(
                ne_overlap, se_overlap_ne, (0, expected_dy_from_ne),
                use_rotation=use_rotation, max_rotation=max_rotation,
                use_zoom=use_zoom, max_zoom_percent=max_zoom_percent,
                image_center=(w/2, h/2)
            )
            se_via_ne_rot = rot1
            se_via_ne_zoom = zoom1
        else:
            dx1, dy1, num1, dist1 = compute_alignment_from_cells(
                ne_overlap, se_overlap_ne, (0, expected_dy_from_ne)
            )
        # Convert to NW frame
        se_via_ne_dx = ne_alignment.dx + dx1
        se_via_ne_dy = ne_alignment.dy + dy1
        score1 = num1
    else:
        se_via_ne_dx = ne_alignment.dx
        se_via_ne_dy = ne_alignment.dy + h - overlap_h
        score1 = 0
    
    # Path 2: SE via SW (SE is to the right of SW)
    sw_cells = all_cells.get('SW', [])
    
    # SW right overlap
    sw_overlap = extract_cells_in_region(sw_cells, w - overlap_w, w, 0, h)
    # SE left overlap
    se_overlap_sw = extract_cells_in_region(se_cells, 0, overlap_w, 0, h)
    
    se_via_sw_zoom = 1.0
    se_via_sw_rot = 0.0
    
    if len(sw_overlap) >= 3 and len(se_overlap_sw) >= 3:
        expected_dx_from_sw = w - overlap_w
        if use_rotation or use_zoom:
            dx2, dy2, rot2, zoom2, num2, dist2 = compute_alignment_with_rotation_zoom(
                sw_overlap, se_overlap_sw, (expected_dx_from_sw, 0),
                use_rotation=use_rotation, max_rotation=max_rotation,
                use_zoom=use_zoom, max_zoom_percent=max_zoom_percent,
                image_center=(w/2, h/2)
            )
            se_via_sw_rot = rot2
            se_via_sw_zoom = zoom2
        else:
            dx2, dy2, num2, dist2 = compute_alignment_from_cells(
                sw_overlap, se_overlap_sw, (expected_dx_from_sw, 0)
            )
        # Convert to NW frame
        se_via_sw_dx = sw_alignment.dx + dx2
        se_via_sw_dy = sw_alignment.dy + dy2
        score2 = num2
    else:
        se_via_sw_dx = sw_alignment.dx + w - overlap_w
        se_via_sw_dy = sw_alignment.dy
        score2 = 0
    
    logger.info(f"SE via NE: dx={se_via_ne_dx:.1f}, dy={se_via_ne_dy:.1f}, matches={score1}")
    logger.info(f"SE via SW: dx={se_via_sw_dx:.1f}, dy={se_via_sw_dy:.1f}, matches={score2}")
    
    # Use path with more matched cells
    if score1 >= score2 and score1 > 0:
        logger.info("SE: Using NE path")
        return QuadrantAlignment(
            dx=se_via_ne_dx, dy=se_via_ne_dy,
            rotation_deg=se_via_ne_rot,
            zoom=se_via_ne_zoom,
            num_matched_cells=score1,
            match_quality=score1 / max(len(ne_overlap), 1),
            method="cellpose_via_NE"
        )
    else:
        logger.info("SE: Using SW path")
        return QuadrantAlignment(
            dx=se_via_sw_dx, dy=se_via_sw_dy,
            rotation_deg=se_via_sw_rot,
            zoom=se_via_sw_zoom,
            num_matched_cells=score2,
            match_quality=score2 / max(len(sw_overlap), 1),
            method="cellpose_via_SW"
        )


def stitch_images(images: Dict[str, np.ndarray],
                  result: AlignmentResult) -> np.ndarray:
    """Stitch images using alignment result with rotation and zoom."""
    h, w = images['NW'].shape[:2]
    
    positions = {'NW': (0, 0)}
    for q in ['NE', 'SW', 'SE']:
        if q in result.quadrants:
            qa = result.quadrants[q]
            positions[q] = (qa.dx, qa.dy)
    
    min_x = min(pos[0] for pos in positions.values())
    max_x = max(pos[0] + w for pos in positions.values())
    min_y = min(pos[1] for pos in positions.values())
    max_y = max(pos[1] + h for pos in positions.values())
    
    canvas_w = int(max_x - min_x) + 10
    canvas_h = int(max_y - min_y) + 10
    ox, oy = -min_x + 5, -min_y + 5
    
    canvas = np.zeros((canvas_h, canvas_w), dtype=np.float64)
    count = np.zeros((canvas_h, canvas_w), dtype=np.int32)
    
    for q in ['NW', 'NE', 'SW', 'SE']:
        if q not in images:
            continue
        
        img = images[q].astype(np.float64)
        img_h, img_w = img.shape[:2]
        
        if q in result.quadrants:
            qa = result.quadrants[q]
            # Apply rotation and zoom if needed
            rot = qa.rotation_deg
            zoom = qa.zoom
            if abs(rot) > 0.001 or abs(zoom - 1.0) > 0.001:
                center = (img_w / 2, img_h / 2)
                M = cv2.getRotationMatrix2D(center, rot, zoom)
                img = cv2.warpAffine(img, M, (img_w, img_h), flags=cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_REFLECT)
        
        dx, dy = positions.get(q, (0, 0))
        x = int(dx + ox)
        y = int(dy + oy)
        
        src_x0 = max(0, -x)
        src_y0 = max(0, -y)
        src_x1 = min(w, canvas_w - x)
        src_y1 = min(h, canvas_h - y)
        
        dst_x0 = max(0, x)
        dst_y0 = max(0, y)
        dst_x1 = min(canvas_w, x + w)
        dst_y1 = min(canvas_h, y + h)
        
        if dst_x1 > dst_x0 and dst_y1 > dst_y0:
            canvas[dst_y0:dst_y1, dst_x0:dst_x1] += img[src_y0:src_y1, src_x0:src_x1]
            count[dst_y0:dst_y1, dst_x0:dst_x1] += 1
    
    valid = count > 0
    canvas[valid] /= count[valid]
    
    return canvas.astype(np.float32)


def stitch_images_overlay(images: Dict[str, np.ndarray],
                          result: AlignmentResult,
                          order: List[str] = None) -> np.ndarray:
    """
    Stitch images by overlaying (not averaging).
    Later images in the order list are placed on top.
    
    Args:
        images: Dictionary of quadrant images
        result: Alignment result
        order: Order to place images (first = bottom, last = top)
               Default: ['SE', 'SW', 'NE', 'NW'] (NW on top)
    """
    if order is None:
        order = ['SE', 'SW', 'NE', 'NW']  # NW ends up on top
    
    h, w = images['NW'].shape[:2]
    
    positions = {'NW': (0, 0)}
    for q in ['NE', 'SW', 'SE']:
        if q in result.quadrants:
            qa = result.quadrants[q]
            positions[q] = (qa.dx, qa.dy)
    
    min_x = min(pos[0] for pos in positions.values())
    max_x = max(pos[0] + w for pos in positions.values())
    min_y = min(pos[1] for pos in positions.values())
    max_y = max(pos[1] + h for pos in positions.values())
    
    canvas_w = int(max_x - min_x) + 10
    canvas_h = int(max_y - min_y) + 10
    ox, oy = -min_x + 5, -min_y + 5
    
    canvas = np.zeros((canvas_h, canvas_w), dtype=np.float64)
    
    # Place images in order (first = bottom, last = top)
    for q in order:
        if q not in images:
            continue
        
        img = images[q].astype(np.float64)
        img_h, img_w = img.shape[:2]
        
        if q in result.quadrants:
            qa = result.quadrants[q]
            rot = qa.rotation_deg
            zoom = qa.zoom
            if abs(rot) > 0.001 or abs(zoom - 1.0) > 0.001:
                center = (img_w / 2, img_h / 2)
                M = cv2.getRotationMatrix2D(center, rot, zoom)
                img = cv2.warpAffine(img, M, (img_w, img_h), flags=cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_REFLECT)
        
        dx, dy = positions.get(q, (0, 0))
        x = int(dx + ox)
        y = int(dy + oy)
        
        src_x0 = max(0, -x)
        src_y0 = max(0, -y)
        src_x1 = min(w, canvas_w - x)
        src_y1 = min(h, canvas_h - y)
        
        dst_x0 = max(0, x)
        dst_y0 = max(0, y)
        dst_x1 = min(canvas_w, x + w)
        dst_y1 = min(canvas_h, y + h)
        
        if dst_x1 > dst_x0 and dst_y1 > dst_y0:
            # Overwrite (not add) - later images cover earlier ones
            canvas[dst_y0:dst_y1, dst_x0:dst_x1] = img[src_y0:src_y1, src_x0:src_x1]
    
    return canvas.astype(np.float32)


def visualize_cells_and_alignment(images: Dict[str, np.ndarray],
                                   all_masks: Dict[str, np.ndarray],
                                   all_cells: Dict[str, List[CellInfo]],
                                   chip_images: Dict[str, np.ndarray],
                                   result: AlignmentResult,
                                   output_path: str):
    """Create visualization with cell detection and alignment."""
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Circle
    except ImportError:
        logger.warning("Matplotlib not available")
        return
    
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    
    # Row 1: Original images with detected cells
    for i, q in enumerate(['NW', 'NE', 'SW', 'SE']):
        ax = axes[0, i]
        if q in images:
            ax.imshow(images[q], cmap='gray')
            
            # Overlay cell centers
            if q in all_cells:
                for cell in all_cells[q]:
                    circle = Circle((cell.center_x, cell.center_y), 5,
                                   color='red', fill=False, linewidth=1)
                    ax.add_patch(circle)
            
            num_cells = len(all_cells.get(q, []))
            if q in result.quadrants:
                qa = result.quadrants[q]
                ax.set_title(f'{q}: {num_cells} cells\n'
                            f'dx={qa.dx:.1f}, dy={qa.dy:.1f}\n'
                            f'matched={qa.num_matched_cells}', fontsize=9)
            else:
                ax.set_title(f'{q}: {num_cells} cells (ref)', fontsize=9)
        ax.axis('off')
    
    # Row 2: Stitched results
    stitched = stitch_images(images, result)
    axes[1, 0].imshow(stitched, cmap='gray')
    axes[1, 0].set_title(f'Original Stitched\nConsistency: {result.consistency_error:.1f}px', fontsize=10)
    axes[1, 0].axis('off')
    
    # Chip stitched
    if len(chip_images) == 4:
        chip_stitched = stitch_images(chip_images, result)
        axes[1, 1].imshow(chip_stitched, cmap='gray')
        axes[1, 1].set_title('Chip Stitched', fontsize=10)
    else:
        axes[1, 1].text(0.5, 0.5, 'No chip images', ha='center', va='center',
                        transform=axes[1, 1].transAxes)
        axes[1, 1].set_title('Chip Stitched', fontsize=10)
    axes[1, 1].axis('off')
    
    # Segmentation masks overlay
    combined_mask = np.zeros_like(stitched)
    h, w = images['NW'].shape[:2]
    positions = {'NW': (0, 0)}
    for q in ['NE', 'SW', 'SE']:
        if q in result.quadrants:
            qa = result.quadrants[q]
            positions[q] = (qa.dx, qa.dy)
    
    min_x = min(pos[0] for pos in positions.values())
    min_y = min(pos[1] for pos in positions.values())
    ox, oy = -min_x + 5, -min_y + 5
    
    for q in ['NW', 'NE', 'SW', 'SE']:
        if q not in all_masks:
            continue
        mask = all_masks[q]
        dx, dy = positions.get(q, (0, 0))
        x, y = int(dx + ox), int(dy + oy)
        
        mask_h, mask_w = mask.shape
        dst_x0, dst_y0 = max(0, x), max(0, y)
        dst_x1 = min(combined_mask.shape[1], x + mask_w)
        dst_y1 = min(combined_mask.shape[0], y + mask_h)
        
        src_x0, src_y0 = max(0, -x), max(0, -y)
        src_x1 = src_x0 + (dst_x1 - dst_x0)
        src_y1 = src_y0 + (dst_y1 - dst_y0)
        
        if dst_x1 > dst_x0 and dst_y1 > dst_y0:
            combined_mask[dst_y0:dst_y1, dst_x0:dst_x1] = np.maximum(
                combined_mask[dst_y0:dst_y1, dst_x0:dst_x1],
                (mask[src_y0:src_y1, src_x0:src_x1] > 0).astype(float) * 255
            )
    
    axes[1, 2].imshow(combined_mask, cmap='viridis')
    axes[1, 2].set_title('Cell Masks (combined)', fontsize=10)
    axes[1, 2].axis('off')
    
    # Info text
    info = "Cellpose Alignment Results:\n\n"
    total_cells = sum(result.total_cells_detected.values())
    info += f"Total cells detected: {total_cells}\n\n"
    
    for q in ['NE', 'SW', 'SE']:
        if q in result.quadrants:
            qa = result.quadrants[q]
            info += f"{q}: dx={qa.dx:+.1f}, dy={qa.dy:+.1f}"
            if abs(qa.rotation_deg) > 0.001:
                info += f", rot={qa.rotation_deg:+.2f}°"
            if abs(qa.zoom - 1.0) > 0.001:
                info += f", zoom={qa.zoom:.3f}"
            info += f"\n   matched={qa.num_matched_cells}, quality={qa.match_quality:.2f}\n"
    
    axes[1, 3].text(0.1, 0.9, info, fontsize=9, fontfamily='monospace',
                    verticalalignment='top', transform=axes[1, 3].transAxes)
    axes[1, 3].set_title('Alignment Info', fontsize=10)
    axes[1, 3].axis('off')
    
    plt.suptitle('Cellpose-based Alignment (All → NW)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved visualization to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Cellpose-based Image Alignment")
    parser.add_argument('--input-dir', required=True, help="Directory containing images")
    parser.add_argument('--prefix', required=True, help="File prefix")
    parser.add_argument('--output-dir', default='cellpose/output', help="Output directory")
    parser.add_argument('--overlap', type=float, default=70, help="Expected overlap %%")
    parser.add_argument('--model', default='cyto3', 
                        choices=['cyto3', 'cyto2', 'cyto', 'nuclei'],
                        help="Cellpose model type")
    parser.add_argument('--diameter', type=float, default=15,
                        help="Expected cell diameter (default: 15)")
    parser.add_argument('--rotation', action='store_true',
                        help="Enable rotation search")
    parser.add_argument('--max-rotation', type=float, default=5.0,
                        help="Maximum rotation (degrees)")
    parser.add_argument('--zoom', action='store_true', default=True,
                        help="Enable zoom search (default: enabled)")
    parser.add_argument('--no-zoom', dest='zoom', action='store_false',
                        help="Disable zoom search")
    parser.add_argument('--max-zoom', type=float, default=5.0,
                        help="Maximum zoom (±percent, default: 5)")
    parser.add_argument('--flow-threshold', type=float, default=0.1,
                        help="Cellpose flow threshold (default: 0.1)")
    parser.add_argument('--cellprob-threshold', type=float, default=-3.5,
                        help="Cellpose cell probability threshold (default: -3.5)")
    parser.add_argument('--min-size', type=int, default=325,
                        help="Minimum cell size in pixels (default: 325)")
    parser.add_argument('--gpu', action='store_true',
                        help="Use GPU/MPS acceleration (Apple Silicon uses MPS)")
    
    args = parser.parse_args()
    
    # Load images
    logger.info(f"Loading images from {args.input_dir}")
    images = load_images(args.input_dir, args.prefix)
    
    if len(images) < 4:
        logger.error(f"Only found {len(images)} images, need 4")
        return 1
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Cellpose Alignment: model={args.model}, diameter={args.diameter}")
    logger.info(f"  flow_threshold={args.flow_threshold}, cellprob_threshold={args.cellprob_threshold}")
    logger.info(f"  min_size={args.min_size}, overlap={args.overlap}%")
    logger.info(f"GPU/MPS: {args.gpu}")
    logger.info(f"Rotation search: {args.rotation} (max ±{args.max_rotation}°)")
    logger.info(f"Zoom search: {args.zoom} (max ±{args.max_zoom}%)")
    logger.info(f"{'='*60}")
    
    # Detect cells in all quadrants
    logger.info("\nDetecting cells with Cellpose...")
    logger.info(f"Parameters: model={args.model}, diameter={args.diameter}, "
               f"flow_threshold={args.flow_threshold}, cellprob_threshold={args.cellprob_threshold}, "
               f"min_size={args.min_size}")
    all_masks = {}
    all_cells = {}
    
    for q in ['NW', 'NE', 'SW', 'SE']:
        if q not in images:
            continue
        logger.info(f"\nProcessing {q}...")
        
        # Normalize image using percentile stretch (same as test_cellpose_params.py)
        img = images[q]
        logger.info(f"  Raw image stats: min={img.min():.1f}, max={img.max():.1f}")
        img = normalize_image(img)
        logger.info(f"  Normalized stats: min={img.min():.1f}, max={img.max():.1f}")
        
        masks, cells = detect_cells_cellpose(
            img,
            model_type=args.model,
            diameter=args.diameter,
            flow_threshold=args.flow_threshold,
            cellprob_threshold=args.cellprob_threshold,
            min_size=args.min_size,
            use_gpu=args.gpu
        )
        all_masks[q] = masks
        all_cells[q] = cells
        
        # Store normalized image for stitching
        images[q] = img
    
    result = AlignmentResult()
    result.total_cells_detected = {q: len(cells) for q, cells in all_cells.items()}
    
    image_shape = images['NW'].shape[:2]
    
    # Align NE to NW
    logger.info("\nAligning NE to NW...")
    ne_align = align_quadrant_to_nw(
        all_cells['NW'], all_cells['NE'],
        image_shape, 'horizontal',
        args.overlap, args.rotation, args.max_rotation,
        args.zoom, args.max_zoom
    )
    result.quadrants['NE'] = ne_align
    zoom_str = f", zoom={ne_align.zoom:.3f}" if abs(ne_align.zoom - 1.0) > 0.001 else ""
    logger.info(f"NE: dx={ne_align.dx:.2f}, dy={ne_align.dy:.2f}{zoom_str}, "
               f"matched={ne_align.num_matched_cells}, quality={ne_align.match_quality:.2f}")
    
    # Align SW to NW
    logger.info("\nAligning SW to NW...")
    sw_align = align_quadrant_to_nw(
        all_cells['NW'], all_cells['SW'],
        image_shape, 'vertical',
        args.overlap, args.rotation, args.max_rotation,
        args.zoom, args.max_zoom
    )
    result.quadrants['SW'] = sw_align
    zoom_str = f", zoom={sw_align.zoom:.3f}" if abs(sw_align.zoom - 1.0) > 0.001 else ""
    logger.info(f"SW: dx={sw_align.dx:.2f}, dy={sw_align.dy:.2f}{zoom_str}, "
               f"matched={sw_align.num_matched_cells}, quality={sw_align.match_quality:.2f}")
    
    # Align SE via chain
    logger.info("\nAligning SE via NE/SW chain...")
    se_align = align_se_via_chain(
        all_cells, image_shape,
        ne_align, sw_align,
        args.overlap, args.rotation, args.max_rotation,
        args.zoom, args.max_zoom
    )
    result.quadrants['SE'] = se_align
    logger.info(f"SE: dx={se_align.dx:.2f}, dy={se_align.dy:.2f}, "
               f"matched={se_align.num_matched_cells}")
    
    # Consistency error
    expected_se_dx = ne_align.dx
    expected_se_dy = sw_align.dy
    result.consistency_error = abs(se_align.dx - expected_se_dx) + abs(se_align.dy - expected_se_dy)
    
    logger.info(f"\nExpected SE: ({expected_se_dx:.1f}, {expected_se_dy:.1f})")
    logger.info(f"Actual SE: ({se_align.dx:.1f}, {se_align.dy:.1f})")
    logger.info(f"Consistency error: {result.consistency_error:.2f}px")
    
    # Load chip images
    logger.info("\nLoading chip images...")
    chip_images = load_chip_images(args.input_dir, args.prefix)
    if len(chip_images) == 4:
        logger.info("Found all 4 chip images")
    
    # Save outputs
    output_dir = Path(args.output_dir)
    
    # Visualization
    viz_path = output_dir / "cellpose_alignment.png"
    visualize_cells_and_alignment(images, all_masks, all_cells, chip_images, result, str(viz_path))
    
    # Stitched images (mean projection)
    stitched = stitch_images(images, result)
    stitched_path = output_dir / "cellpose_stitched.png"
    cv2.imwrite(str(stitched_path), np.clip(stitched, 0, 255).astype(np.uint8))
    logger.info(f"Saved original stitched (mean) to {stitched_path}")
    
    # Stitched images (overlay, NW on top)
    stitched_overlay = stitch_images_overlay(images, result, order=['SE', 'SW', 'NE', 'NW'])
    overlay_path = output_dir / "cellpose_stitched_overlay.png"
    cv2.imwrite(str(overlay_path), np.clip(stitched_overlay, 0, 255).astype(np.uint8))
    logger.info(f"Saved original stitched (overlay, NW on top) to {overlay_path}")
    
    # Create comparison figure: mean vs overlay
    try:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(16, 8))
        
        axes[0].imshow(stitched, cmap='gray', vmin=0, vmax=255)
        axes[0].set_title('Mean Projection\n(overlapping regions averaged)', fontsize=12)
        axes[0].axis('off')
        
        axes[1].imshow(stitched_overlay, cmap='gray', vmin=0, vmax=255)
        axes[1].set_title('Overlay (NW on top)\n(layer order: SE → SW → NE → NW)', fontsize=12)
        axes[1].axis('off')
        
        plt.suptitle('Original Image Stitching Comparison', fontsize=14, fontweight='bold')
        plt.tight_layout()
        comparison_path = output_dir / "cellpose_stitched_comparison.png"
        plt.savefig(str(comparison_path), dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved stitching comparison to {comparison_path}")
    except ImportError:
        pass
    
    if len(chip_images) == 4:
        # Chip stitched (mean projection)
        chip_stitched = stitch_images(chip_images, result)
        chip_path = output_dir / "cellpose_chip_stitched.png"
        cv2.imwrite(str(chip_path), np.clip(chip_stitched, 0, 255).astype(np.uint8))
        logger.info(f"Saved chip stitched (mean) to {chip_path}")
        
        # Chip stitched (overlay)
        chip_overlay = stitch_images_overlay(chip_images, result, order=['SE', 'SW', 'NE', 'NW'])
        chip_overlay_path = output_dir / "cellpose_chip_overlay.png"
        cv2.imwrite(str(chip_overlay_path), np.clip(chip_overlay, 0, 255).astype(np.uint8))
        logger.info(f"Saved chip stitched (overlay) to {chip_overlay_path}")
        
        # Create chip comparison figure
        try:
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(1, 2, figsize=(16, 8))
            
            axes[0].imshow(chip_stitched, cmap='gray', vmin=0, vmax=255)
            axes[0].set_title('Chip - Mean Projection', fontsize=12)
            axes[0].axis('off')
            
            axes[1].imshow(chip_overlay, cmap='gray', vmin=0, vmax=255)
            axes[1].set_title('Chip - Overlay (NW on top)', fontsize=12)
            axes[1].axis('off')
            
            plt.suptitle('Chip Image Stitching Comparison', fontsize=14, fontweight='bold')
            plt.tight_layout()
            chip_comparison_path = output_dir / "cellpose_chip_comparison.png"
            plt.savefig(str(chip_comparison_path), dpi=150, bbox_inches='tight')
            plt.close()
            logger.info(f"Saved chip comparison to {chip_comparison_path}")
        except ImportError:
            pass
    
    # Parameters JSON
    params_path = output_dir / "cellpose_alignment_params.json"
    with open(params_path, 'w') as f:
        json.dump(result.to_dict(), f, indent=2)
    logger.info(f"Saved parameters to {params_path}")
    
    logger.info(f"\n*** CELLPOSE ALIGNMENT COMPLETE ***")
    logger.info(f"Total cells detected: {sum(result.total_cells_detected.values())}")
    logger.info(f"Consistency error: {result.consistency_error:.2f}px")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
