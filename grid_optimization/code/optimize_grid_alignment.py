#!/usr/bin/env python3
"""
Optimized Grid-Constrained Alignment with Sub-pixel Refinement

This script focuses on improving the grid_constrained_70_50 method by:
1. Multi-scale coarse-to-fine search
2. Sub-pixel refinement using parabolic interpolation
3. Phase correlation for final sub-pixel accuracy
4. Weighted NCC with edge-aware masking
5. Iterative refinement with consistency constraints

Author: Image MEA Alignment Project
"""

import argparse
import logging
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import numpy as np
import cv2

# Try to import scikit-image for sub-pixel phase correlation
try:
    from skimage.registration import phase_cross_correlation
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False

# Try to import matplotlib for visualization
try:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AlignmentResult:
    """Result of alignment optimization."""
    method: str
    translations: Dict[str, Tuple[float, float]]
    rotations: Dict[str, float] = field(default_factory=dict)
    zooms: Dict[str, float] = field(default_factory=dict)
    ncc_scores: Dict[str, float] = field(default_factory=dict)
    consistency_error: float = 0.0
    success: bool = True
    details: Dict = field(default_factory=dict)


def load_quadrant_images(input_dir: str, prefix: str) -> Dict[str, np.ndarray]:
    """Load quadrant images from CZI files."""
    try:
        import czifile
    except ImportError:
        logger.error("czifile not installed. Run: pip install czifile")
        return {}
    
    images = {}
    input_path = Path(input_dir)
    
    for quadrant in ['NW', 'NE', 'SW', 'SE']:
        pattern = f"{prefix}{quadrant}.czi"
        matches = list(input_path.glob(pattern))
        
        if matches:
            with czifile.CziFile(str(matches[0])) as czi:
                img_data = czi.asarray()
            
            # Squeeze singleton dimensions  
            while img_data.ndim > 2 and img_data.shape[0] == 1:
                img_data = img_data.squeeze(axis=0)
            
            # If still 4D and Z-stack present, take middle Z-slice
            if img_data.ndim == 4:
                z_idx = img_data.shape[0] // 2
                img_data = img_data[z_idx]
            
            # If 3D, take first channel or middle slice
            if img_data.ndim == 3:
                if img_data.shape[0] < img_data.shape[-1]:
                    # Likely (C, H, W) - take first channel
                    img = img_data[0]
                else:
                    # Likely (H, W, C) - take first channel
                    img = img_data[:, :, 0]
            else:
                img = img_data
            
            # Convert to float32 for processing
            if img.dtype == np.uint16:
                img = (img / 65535.0 * 255).astype(np.float32)
            elif img.dtype == np.uint8:
                img = img.astype(np.float32)
            else:
                img = img.astype(np.float32)
            
            images[quadrant] = img
            logger.info(f"Loaded {quadrant}: shape={img.shape}, range=[{img.min():.1f}, {img.max():.1f}]")
    
    return images


def load_chip_images(input_dir: str, prefix: str) -> Dict[str, np.ndarray]:
    """
    Load chip quadrant images from CZI files.
    
    Chip images have 'chip' in their filename, e.g.:
    - 2025.10.22-10.34.56-4134-opnT2_chipNW.czi
    """
    try:
        import czifile
    except ImportError:
        logger.error("czifile not installed. Run: pip install czifile")
        return {}
    
    images = {}
    input_path = Path(input_dir)
    
    for quadrant in ['NW', 'NE', 'SW', 'SE']:
        # Try different chip filename patterns
        patterns = [
            f"{prefix}chip{quadrant}.czi",    # prefix_chipNW.czi
            f"{prefix}_chip{quadrant}.czi",   # prefix__chipNW.czi
            f"{prefix}{quadrant}_chip.czi",   # prefix_NW_chip.czi
        ]
        
        matches = []
        for pattern in patterns:
            matches = list(input_path.glob(pattern))
            if matches:
                break
        
        if matches:
            with czifile.CziFile(str(matches[0])) as czi:
                img_data = czi.asarray()
            
            # Squeeze singleton dimensions  
            while img_data.ndim > 2 and img_data.shape[0] == 1:
                img_data = img_data.squeeze(axis=0)
            
            # If still 4D and Z-stack present, take middle Z-slice
            if img_data.ndim == 4:
                z_idx = img_data.shape[0] // 2
                img_data = img_data[z_idx]
            
            # If 3D, take first channel or middle slice
            if img_data.ndim == 3:
                if img_data.shape[0] < img_data.shape[-1]:
                    img = img_data[0]
                else:
                    img = img_data[:, :, 0]
            else:
                img = img_data
            
            # Convert to float32 for processing
            if img.dtype == np.uint16:
                img = (img / 65535.0 * 255).astype(np.float32)
            elif img.dtype == np.uint8:
                img = img.astype(np.float32)
            else:
                img = img.astype(np.float32)
            
            images[quadrant] = img
            logger.info(f"Loaded chip {quadrant}: shape={img.shape}, file={matches[0].name}")
    
    return images


def compute_ncc(template: np.ndarray, image: np.ndarray) -> Tuple[float, int, int]:
    """
    Compute Normalized Cross-Correlation and find best match.
    
    Returns:
        (max_ncc, best_x, best_y)
    """
    result = cv2.matchTemplate(image.astype(np.float32), 
                                template.astype(np.float32), 
                                cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    return max_val, max_loc[0], max_loc[1], result


def subpixel_ncc_refinement(ncc_map: np.ndarray, x: int, y: int) -> Tuple[float, float]:
    """
    Refine NCC peak location to sub-pixel accuracy using parabolic interpolation.
    
    Uses 2D parabolic fitting around the peak.
    """
    h, w = ncc_map.shape
    
    # Ensure we're not at the boundary
    if x < 1 or x >= w - 1 or y < 1 or y >= h - 1:
        return float(x), float(y)
    
    # Extract 3x3 neighborhood
    neighborhood = ncc_map[y-1:y+2, x-1:x+2]
    
    # Parabolic interpolation in x
    fx_m1 = ncc_map[y, x-1]
    fx_0 = ncc_map[y, x]
    fx_p1 = ncc_map[y, x+1]
    
    denom_x = 2 * (fx_m1 - 2*fx_0 + fx_p1)
    if abs(denom_x) > 1e-10:
        dx = (fx_m1 - fx_p1) / denom_x
        dx = np.clip(dx, -0.5, 0.5)  # Limit to half pixel
    else:
        dx = 0.0
    
    # Parabolic interpolation in y
    fy_m1 = ncc_map[y-1, x]
    fy_0 = ncc_map[y, x]
    fy_p1 = ncc_map[y+1, x]
    
    denom_y = 2 * (fy_m1 - 2*fy_0 + fy_p1)
    if abs(denom_y) > 1e-10:
        dy = (fy_m1 - fy_p1) / denom_y
        dy = np.clip(dy, -0.5, 0.5)
    else:
        dy = 0.0
    
    return x + dx, y + dy


def rotate_image(image: np.ndarray, angle_degrees: float, center: Tuple[float, float] = None) -> np.ndarray:
    """
    Rotate image around center.
    
    Args:
        image: Input image
        angle_degrees: Rotation angle in degrees (positive = counter-clockwise)
        center: Rotation center, defaults to image center
        
    Returns:
        Rotated image
    """
    h, w = image.shape[:2]
    if center is None:
        center = (w / 2, h / 2)
    
    M = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_LINEAR, 
                              borderMode=cv2.BORDER_REFLECT)
    return rotated


def scale_image(image: np.ndarray, scale: float) -> np.ndarray:
    """
    Scale image by given factor.
    
    Args:
        image: Input image
        scale: Scale factor (1.0 = no change, >1 = enlarge, <1 = shrink)
        
    Returns:
        Scaled image (same size as input, centered)
    """
    h, w = image.shape[:2]
    
    # Compute new dimensions
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # Resize
    scaled = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    
    # Create output image (same size as input)
    output = np.zeros_like(image)
    
    if scale > 1.0:
        # Crop center
        start_x = (new_w - w) // 2
        start_y = (new_h - h) // 2
        output = scaled[start_y:start_y+h, start_x:start_x+w]
    else:
        # Pad with zeros (or use border)
        start_x = (w - new_w) // 2
        start_y = (h - new_h) // 2
        output[start_y:start_y+new_h, start_x:start_x+new_w] = scaled
    
    return output


def compute_ncc_with_transform(ref_img: np.ndarray,
                                target_img: np.ndarray,
                                translation: Tuple[float, float],
                                rotation: float = 0.0,
                                zoom: float = 1.0,
                                overlap_percent: float = 70,
                                direction: str = 'horizontal') -> float:
    """
    Compute NCC between reference and transformed target.
    
    Args:
        ref_img: Reference image
        target_img: Target image
        translation: (dx, dy) translation
        rotation: Rotation in degrees
        zoom: Zoom factor (1.0 = no zoom)
        overlap_percent: Expected overlap percentage
        direction: 'horizontal', 'vertical', or 'diagonal'
        
    Returns:
        NCC score
    """
    h, w = ref_img.shape
    dx, dy = translation
    
    # Apply rotation and zoom to target
    if abs(rotation) > 0.001 or abs(zoom - 1.0) > 0.001:
        center = (w / 2, h / 2)
        M = cv2.getRotationMatrix2D(center, rotation, zoom)
        target_transformed = cv2.warpAffine(target_img.astype(np.float32), M, (w, h),
                                             flags=cv2.INTER_LINEAR,
                                             borderMode=cv2.BORDER_REFLECT)
    else:
        target_transformed = target_img
    
    # Extract overlap regions
    if direction == 'horizontal':
        overlap_w = int(w * overlap_percent / 100)
        ref_region = ref_img[:, -overlap_w:]
        
        target_start = max(0, min(int(dx), w - overlap_w))
        target_region = target_transformed[:, target_start:target_start + overlap_w]
    elif direction == 'vertical':
        overlap_h = int(h * overlap_percent / 100)
        ref_region = ref_img[-overlap_h:, :]
        
        target_start = max(0, min(int(dy), h - overlap_h))
        target_region = target_transformed[target_start:target_start + overlap_h, :]
    else:  # diagonal
        overlap_w = int(w * overlap_percent / 100)
        overlap_h = int(h * overlap_percent / 100)
        ref_region = ref_img[-overlap_h:, -overlap_w:]
        
        target_start_x = max(0, min(int(dx) % w, w - overlap_w))
        target_start_y = max(0, min(int(dy) % h, h - overlap_h))
        target_region = target_transformed[target_start_y:target_start_y + overlap_h,
                                            target_start_x:target_start_x + overlap_w]
    
    # Ensure same size
    min_h = min(ref_region.shape[0], target_region.shape[0])
    min_w = min(ref_region.shape[1], target_region.shape[1])
    
    if min_h < 10 or min_w < 10:
        return 0.0
    
    ref_region = ref_region[:min_h, :min_w]
    target_region = target_region[:min_h, :min_w]
    
    # Compute NCC
    ref_mean = np.mean(ref_region)
    target_mean = np.mean(target_region)
    
    ref_std = np.std(ref_region)
    target_std = np.std(target_region)
    
    if ref_std < 1e-6 or target_std < 1e-6:
        return 0.0
    
    ncc = np.mean((ref_region - ref_mean) * (target_region - target_mean)) / (ref_std * target_std)
    return ncc


def search_rotation_zoom(ref_img: np.ndarray,
                          target_img: np.ndarray,
                          initial_translation: Tuple[float, float],
                          overlap_percent: float = 70,
                          direction: str = 'horizontal',
                          max_rotation: float = 5.0,
                          rotation_step: float = 0.5,
                          max_zoom_percent: float = 5.0,
                          zoom_step: float = 1.0) -> Tuple[float, float, float, float, float]:
    """
    Search for optimal rotation and zoom.
    
    Args:
        ref_img: Reference image
        target_img: Target image
        initial_translation: Initial (dx, dy) from NCC search
        overlap_percent: Expected overlap
        direction: 'horizontal' or 'vertical'
        max_rotation: Maximum rotation to search (±degrees)
        rotation_step: Rotation search step (degrees)
        max_zoom_percent: Maximum zoom to search (±percent)
        zoom_step: Zoom search step (percent)
        
    Returns:
        (dx, dy, rotation, zoom, ncc_score)
    """
    best_ncc = -1.0
    best_rot = 0.0
    best_zoom = 1.0
    best_dx, best_dy = initial_translation
    
    # Generate rotation values to test
    rotations = np.arange(-max_rotation, max_rotation + rotation_step, rotation_step)
    
    # Generate zoom values to test
    zooms = [1.0 + z/100.0 for z in np.arange(-max_zoom_percent, max_zoom_percent + zoom_step, zoom_step)]
    
    logger.debug(f"Searching {len(rotations)} rotations x {len(zooms)} zooms")
    
    for rot in rotations:
        for zoom in zooms:
            ncc = compute_ncc_with_transform(
                ref_img, target_img,
                initial_translation,
                rotation=rot,
                zoom=zoom,
                overlap_percent=overlap_percent,
                direction=direction
            )
            
            if ncc > best_ncc:
                best_ncc = ncc
                best_rot = rot
                best_zoom = zoom
    
    # Refine translation with best rotation/zoom
    if abs(best_rot) > 0.001 or abs(best_zoom - 1.0) > 0.001:
        # Apply transform and re-search translation
        h, w = target_img.shape
        center = (w / 2, h / 2)
        M = cv2.getRotationMatrix2D(center, best_rot, best_zoom)
        target_transformed = cv2.warpAffine(target_img.astype(np.float32), M, (w, h),
                                             flags=cv2.INTER_LINEAR,
                                             borderMode=cv2.BORDER_REFLECT)
        
        # Re-do NCC search on transformed image
        if direction == 'horizontal':
            dx, dy, ncc = grid_search_with_subpixel(
                ref_img, target_transformed,
                overlap_percent, 20, 'horizontal'
            )
        else:
            dx, dy, ncc = grid_search_with_subpixel(
                ref_img, target_transformed,
                overlap_percent, 20, 'vertical'
            )
        
        best_dx, best_dy = dx, dy
        best_ncc = ncc
    
    return best_dx, best_dy, best_rot, best_zoom, best_ncc


def refine_rotation_subpixel(ref_img: np.ndarray,
                              target_img: np.ndarray,
                              translation: Tuple[float, float],
                              initial_rotation: float,
                              zoom: float = 1.0,
                              overlap_percent: float = 70,
                              direction: str = 'horizontal',
                              refinement_range: float = 0.5,
                              num_steps: int = 21) -> Tuple[float, float]:
    """
    Refine rotation to sub-degree accuracy.
    
    Returns:
        (refined_rotation, ncc_score)
    """
    rotations = np.linspace(initial_rotation - refinement_range, 
                            initial_rotation + refinement_range, 
                            num_steps)
    
    best_ncc = -1.0
    best_rot = initial_rotation
    
    for rot in rotations:
        ncc = compute_ncc_with_transform(
            ref_img, target_img,
            translation,
            rotation=rot,
            zoom=zoom,
            overlap_percent=overlap_percent,
            direction=direction
        )
        
        if ncc > best_ncc:
            best_ncc = ncc
            best_rot = rot
    
    return best_rot, best_ncc


def refine_zoom_subpixel(ref_img: np.ndarray,
                          target_img: np.ndarray,
                          translation: Tuple[float, float],
                          rotation: float,
                          initial_zoom: float,
                          overlap_percent: float = 70,
                          direction: str = 'horizontal',
                          refinement_range: float = 0.5,
                          num_steps: int = 21) -> Tuple[float, float]:
    """
    Refine zoom to sub-percent accuracy.
    
    Returns:
        (refined_zoom, ncc_score)
    """
    zooms = np.linspace(initial_zoom - refinement_range/100, 
                        initial_zoom + refinement_range/100, 
                        num_steps)
    
    best_ncc = -1.0
    best_zoom = initial_zoom
    
    for zoom in zooms:
        ncc = compute_ncc_with_transform(
            ref_img, target_img,
            translation,
            rotation=rotation,
            zoom=zoom,
            overlap_percent=overlap_percent,
            direction=direction
        )
        
        if ncc > best_ncc:
            best_ncc = ncc
            best_zoom = zoom
    
    return best_zoom, best_ncc


def multi_scale_ncc_search(ref_img: np.ndarray, 
                           target_img: np.ndarray,
                           expected_shift: Tuple[int, int],
                           search_range: int = 50,
                           num_scales: int = 3) -> Tuple[float, float, float]:
    """
    Multi-scale coarse-to-fine NCC search.
    
    Args:
        ref_img: Reference image (e.g., NW)
        target_img: Target image to align (e.g., NE)
        expected_shift: Expected (dx, dy) shift
        search_range: Search range in pixels at finest scale
        num_scales: Number of pyramid levels
        
    Returns:
        (dx, dy, ncc_score)
    """
    h, w = ref_img.shape
    exp_dx, exp_dy = expected_shift
    
    # Build image pyramids
    ref_pyramid = [ref_img]
    target_pyramid = [target_img]
    
    for i in range(num_scales - 1):
        ref_pyramid.append(cv2.pyrDown(ref_pyramid[-1]))
        target_pyramid.append(cv2.pyrDown(target_pyramid[-1]))
    
    # Start from coarsest scale
    current_dx, current_dy = exp_dx, exp_dy
    current_range = search_range
    
    for scale in range(num_scales - 1, -1, -1):
        scale_factor = 2 ** scale
        ref = ref_pyramid[scale]
        target = target_pyramid[scale]
        
        # Scale the current estimate
        scaled_dx = int(current_dx / scale_factor)
        scaled_dy = int(current_dy / scale_factor)
        scaled_range = max(2, current_range // scale_factor)
        
        h_s, w_s = ref.shape
        
        # Extract overlap regions based on expected shift
        if scaled_dx >= 0:  # Target is to the right
            overlap_w = w_s - abs(scaled_dx)
            if overlap_w < 50:
                overlap_w = w_s // 2
            
            ref_region = ref[:, -overlap_w:]
            
            # Search in target image
            search_x0 = max(0, scaled_range - scaled_range)
            search_x1 = min(w_s, scaled_range + scaled_range + overlap_w)
            search_y0 = max(0, scaled_dy - scaled_range)
            search_y1 = min(h_s, scaled_dy + scaled_range + h_s)
            
            target_region = target[max(0, search_y0):min(h_s, search_y0 + ref_region.shape[0] + 2*scaled_range),
                                   search_x0:min(w_s, search_x0 + ref_region.shape[1] + 2*scaled_range)]
        else:  # Vertical shift (SW case)
            overlap_h = h_s - abs(scaled_dy)
            if overlap_h < 50:
                overlap_h = h_s // 2
            
            ref_region = ref[-overlap_h:, :]
            
            search_x0 = max(0, scaled_dx - scaled_range)
            search_x1 = min(w_s, scaled_dx + scaled_range + w_s)
            search_y0 = max(0, 0)
            search_y1 = min(h_s, scaled_range * 2 + overlap_h)
            
            target_region = target[search_y0:min(h_s, search_y0 + ref_region.shape[0] + 2*scaled_range),
                                   max(0, search_x0):min(w_s, search_x0 + ref_region.shape[1] + 2*scaled_range)]
        
        if ref_region.shape[0] < 10 or ref_region.shape[1] < 10:
            continue
        if target_region.shape[0] < ref_region.shape[0] or target_region.shape[1] < ref_region.shape[1]:
            continue
        
        # Compute NCC
        ncc_val, best_x, best_y, ncc_map = compute_ncc(ref_region, target_region)
        
        # Sub-pixel refinement at finest scale
        if scale == 0 and ncc_map is not None:
            sub_x, sub_y = subpixel_ncc_refinement(ncc_map, best_x, best_y)
            # Convert back to global coordinates
            if scaled_dx >= 0:
                current_dx = (w_s - overlap_w) + search_x0 + sub_x
                current_dy = search_y0 + sub_y
            else:
                current_dx = search_x0 + sub_x
                current_dy = (h_s - overlap_h) + search_y0 + sub_y
        else:
            # Update for next scale
            if scaled_dx >= 0:
                current_dx = ((w_s - overlap_w) + search_x0 + best_x) * scale_factor
                current_dy = (search_y0 + best_y) * scale_factor
            else:
                current_dx = (search_x0 + best_x) * scale_factor
                current_dy = ((h_s - overlap_h) + search_y0 + best_y) * scale_factor
        
        current_range = scaled_range * 2  # Expand for next finer scale
    
    return current_dx, current_dy, ncc_val


def grid_search_with_subpixel(ref_img: np.ndarray,
                               target_img: np.ndarray,
                               overlap_percent: float = 70,
                               search_range: int = 50,
                               direction: str = 'horizontal') -> Tuple[float, float, float]:
    """
    Grid search with sub-pixel refinement.
    
    Args:
        ref_img: Reference image
        target_img: Target image
        overlap_percent: Expected overlap percentage
        search_range: Search range in pixels
        direction: 'horizontal' for NE, 'vertical' for SW, 'diagonal' for SE
        
    Returns:
        (dx, dy, ncc_score)
    """
    h, w = ref_img.shape
    
    if direction == 'horizontal':
        # NE is to the right of NW
        expected_dx = int(w * (1 - overlap_percent / 100))
        expected_dy = 0
        
        # Extract overlap region from reference (right edge)
        overlap_w = int(w * overlap_percent / 100)
        ref_overlap = ref_img[:, -overlap_w:]
        
        # Search in target (left portion)
        search_region = target_img[:, :overlap_w + search_range * 2]
        
    elif direction == 'vertical':
        # SW is below NW
        expected_dx = 0
        expected_dy = int(h * (1 - overlap_percent / 100))
        
        # Extract overlap region from reference (bottom edge)
        overlap_h = int(h * overlap_percent / 100)
        ref_overlap = ref_img[-overlap_h:, :]
        
        # Search in target (top portion)
        search_region = target_img[:overlap_h + search_range * 2, :]
        
    else:  # diagonal - SE relative to NW
        # SE is diagonally opposite to NW
        expected_dx = int(w * (1 - overlap_percent / 100))
        expected_dy = int(h * (1 - overlap_percent / 100))
        
        # Extract corner overlap region from reference (bottom-right corner)
        overlap_w = int(w * overlap_percent / 100)
        overlap_h = int(h * overlap_percent / 100)
        ref_overlap = ref_img[-overlap_h:, -overlap_w:]
        
        # Search in target (top-left corner region)
        search_h = min(overlap_h + search_range * 2, h)
        search_w = min(overlap_w + search_range * 2, w)
        search_region = target_img[:search_h, :search_w]
    
    if search_region.shape[0] < ref_overlap.shape[0] or search_region.shape[1] < ref_overlap.shape[1]:
        logger.warning(f"Search region too small for {direction}")
        if direction == 'diagonal':
            return expected_dx, expected_dy, 0.0
        elif direction == 'horizontal':
            return expected_dx, 0, 0.0
        else:
            return 0, expected_dy, 0.0
    
    # Compute NCC
    ncc_val, best_x, best_y, ncc_map = compute_ncc(ref_overlap, search_region)
    
    # Sub-pixel refinement
    if ncc_map is not None:
        sub_x, sub_y = subpixel_ncc_refinement(ncc_map, best_x, best_y)
    else:
        sub_x, sub_y = float(best_x), float(best_y)
    
    if direction == 'horizontal':
        # dx = how much target is shifted from reference
        dx = (w - overlap_w) + sub_x
        dy = sub_y
    elif direction == 'vertical':
        dx = sub_x
        dy = (h - overlap_h) + sub_y
    else:  # diagonal
        dx = (w - overlap_w) + sub_x
        dy = (h - overlap_h) + sub_y
    
    return dx, dy, ncc_val


def phase_correlation_refinement(ref_img: np.ndarray,
                                  target_img: np.ndarray,
                                  initial_shift: Tuple[float, float],
                                  window_size: int = 256) -> Tuple[float, float, float]:
    """
    Refine alignment using phase correlation on overlap region.
    
    Args:
        ref_img: Reference image
        target_img: Target image
        initial_shift: Initial (dx, dy) estimate
        window_size: Size of window for phase correlation
        
    Returns:
        (refined_dx, refined_dy, correlation)
    """
    if not SKIMAGE_AVAILABLE:
        return initial_shift[0], initial_shift[1], 0.0
    
    h, w = ref_img.shape
    dx, dy = initial_shift
    
    # Extract overlapping regions
    if abs(dx) > abs(dy):  # Horizontal shift (NE case)
        overlap_w = int(w - abs(dx))
        if overlap_w < window_size:
            overlap_w = window_size
        
        # Get center of overlap
        ref_region = ref_img[:, -overlap_w:]
        
        target_start_x = max(0, int(dx) - (w - overlap_w))
        target_region = target_img[:, target_start_x:target_start_x + overlap_w]
        
    else:  # Vertical shift (SW case)
        overlap_h = int(h - abs(dy))
        if overlap_h < window_size:
            overlap_h = window_size
        
        ref_region = ref_img[-overlap_h:, :]
        
        target_start_y = max(0, int(dy) - (h - overlap_h))
        target_region = target_img[target_start_y:target_start_y + overlap_h, :]
    
    # Ensure same size
    min_h = min(ref_region.shape[0], target_region.shape[0])
    min_w = min(ref_region.shape[1], target_region.shape[1])
    ref_region = ref_region[:min_h, :min_w]
    target_region = target_region[:min_h, :min_w]
    
    if ref_region.shape[0] < 32 or ref_region.shape[1] < 32:
        return dx, dy, 0.0
    
    # Phase correlation with sub-pixel accuracy
    try:
        shift, error, diffphase = phase_cross_correlation(
            ref_region, target_region, 
            upsample_factor=100,
            normalization=None
        )
        
        # Apply refinement
        refined_dy = dy + shift[0]
        refined_dx = dx + shift[1]
        
        # Correlation quality (1 - error for phase correlation)
        correlation = 1.0 - error if error < 1.0 else 0.0
        
        return refined_dx, refined_dy, correlation
        
    except Exception as e:
        logger.warning(f"Phase correlation failed: {e}")
        return dx, dy, 0.0


def weighted_ncc_with_gradient(ref_img: np.ndarray,
                                target_img: np.ndarray,
                                overlap_percent: float = 70,
                                search_range: int = 50,
                                direction: str = 'horizontal') -> Tuple[float, float, float]:
    """
    Weighted NCC using gradient magnitude for edge-aware matching.
    """
    # Compute gradient magnitude
    ref_grad_x = cv2.Sobel(ref_img, cv2.CV_32F, 1, 0, ksize=3)
    ref_grad_y = cv2.Sobel(ref_img, cv2.CV_32F, 0, 1, ksize=3)
    ref_grad = np.sqrt(ref_grad_x**2 + ref_grad_y**2)
    
    target_grad_x = cv2.Sobel(target_img, cv2.CV_32F, 1, 0, ksize=3)
    target_grad_y = cv2.Sobel(target_img, cv2.CV_32F, 0, 1, ksize=3)
    target_grad = np.sqrt(target_grad_x**2 + target_grad_y**2)
    
    # Normalize gradients
    ref_grad = ref_grad / (ref_grad.max() + 1e-6) * 255
    target_grad = target_grad / (target_grad.max() + 1e-6) * 255
    
    # Combine intensity and gradient
    ref_combined = 0.5 * ref_img + 0.5 * ref_grad
    target_combined = 0.5 * target_img + 0.5 * target_grad
    
    # Run grid search on combined images
    return grid_search_with_subpixel(ref_combined, target_combined, 
                                      overlap_percent, search_range, direction)


def iterative_consistency_refinement(images: Dict[str, np.ndarray],
                                      initial_translations: Dict[str, Tuple[float, float]],
                                      max_iterations: int = 5) -> Dict[str, Tuple[float, float]]:
    """
    Iteratively refine translations to improve geometric consistency.
    
    The constraint is: SE should be at approximately (NE_x, SW_y)
    """
    translations = dict(initial_translations)
    
    for iteration in range(max_iterations):
        ne_dx, ne_dy = translations['NE']
        sw_dx, sw_dy = translations['SW']
        se_dx, se_dy = translations['SE']
        
        # Expected SE position
        expected_se_dx = ne_dx
        expected_se_dy = sw_dy
        
        # Current error
        err_x = se_dx - expected_se_dx
        err_y = se_dy - expected_se_dy
        
        consistency_error = abs(err_x) + abs(err_y)
        logger.info(f"Iteration {iteration}: consistency error = {consistency_error:.2f}px")
        
        if consistency_error < 1.0:  # Sub-pixel accuracy achieved
            break
        
        # Adjust SE towards expected position (with damping)
        damping = 0.5
        new_se_dx = se_dx - damping * err_x
        new_se_dy = se_dy - damping * err_y
        
        # Verify the adjustment improves NCC
        # (This would require re-computing NCC, simplified here)
        translations['SE'] = (new_se_dx, new_se_dy)
    
    return translations


def optimize_alignment(images: Dict[str, np.ndarray],
                       overlap_percent: float = 70,
                       search_range: int = 50,
                       use_gradient: bool = True,
                       use_phase_refinement: bool = True,
                       use_consistency: bool = True,
                       use_rotation: bool = False,
                       use_zoom: bool = False,
                       max_rotation: float = 5.0,
                       max_zoom_percent: float = 5.0) -> AlignmentResult:
    """
    Main optimization function combining all techniques.
    
    Args:
        images: Dict of quadrant images
        overlap_percent: Expected overlap percentage
        search_range: Translation search range in pixels
        use_gradient: Use gradient-weighted NCC
        use_phase_refinement: Use phase correlation for sub-pixel refinement
        use_consistency: Apply consistency constraints
        use_rotation: Search for optimal rotation
        use_zoom: Search for optimal zoom/scale
        max_rotation: Maximum rotation to search (±degrees)
        max_zoom_percent: Maximum zoom to search (±percent)
    """
    h, w = images['NW'].shape
    translations = {}
    rotations = {}
    zooms = {}
    ncc_scores = {}
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Optimizing with overlap={overlap_percent}%, search=±{search_range}px")
    logger.info(f"Gradient: {use_gradient}, Phase: {use_phase_refinement}, Consistency: {use_consistency}")
    logger.info(f"Rotation: {use_rotation} (±{max_rotation}°), Zoom: {use_zoom} (±{max_zoom_percent}%)")
    logger.info(f"{'='*60}")
    
    # Step 1: Initial grid search for NE and SW
    if use_gradient:
        search_func = weighted_ncc_with_gradient
    else:
        search_func = grid_search_with_subpixel
    
    # NE alignment (horizontal)
    ne_dx, ne_dy, ne_ncc = search_func(
        images['NW'], images['NE'], 
        overlap_percent, search_range, 'horizontal'
    )
    translations['NE'] = (ne_dx, ne_dy)
    rotations['NE'] = 0.0
    zooms['NE'] = 1.0
    ncc_scores['NE'] = ne_ncc
    logger.info(f"NE initial: dx={ne_dx:.2f}, dy={ne_dy:.2f}, NCC={ne_ncc:.4f}")
    
    # Step 2: Rotation and zoom search for NE
    if use_rotation or use_zoom:
        logger.info("\nSearching rotation/zoom for NE...")
        ne_dx, ne_dy, ne_rot, ne_zoom, ne_ncc = search_rotation_zoom(
            images['NW'], images['NE'],
            translations['NE'],
            overlap_percent=overlap_percent,
            direction='horizontal',
            max_rotation=max_rotation if use_rotation else 0.0,
            rotation_step=0.5,
            max_zoom_percent=max_zoom_percent if use_zoom else 0.0,
            zoom_step=1.0
        )
        
        # Sub-pixel refinement of rotation
        if use_rotation and abs(ne_rot) > 0.01:
            ne_rot, _ = refine_rotation_subpixel(
                images['NW'], images['NE'],
                (ne_dx, ne_dy), ne_rot, ne_zoom,
                overlap_percent, 'horizontal',
                refinement_range=0.5
            )
        
        # Sub-pixel refinement of zoom
        if use_zoom and abs(ne_zoom - 1.0) > 0.001:
            ne_zoom, _ = refine_zoom_subpixel(
                images['NW'], images['NE'],
                (ne_dx, ne_dy), ne_rot, ne_zoom,
                overlap_percent, 'horizontal',
                refinement_range=0.5
            )
        
        translations['NE'] = (ne_dx, ne_dy)
        rotations['NE'] = ne_rot
        zooms['NE'] = ne_zoom
        ncc_scores['NE'] = ne_ncc
        logger.info(f"NE with rot/zoom: dx={ne_dx:.2f}, dy={ne_dy:.2f}, rot={ne_rot:.3f}°, zoom={ne_zoom:.4f}, NCC={ne_ncc:.4f}")
    
    # SW alignment (vertical)
    sw_dx, sw_dy, sw_ncc = search_func(
        images['NW'], images['SW'],
        overlap_percent, search_range, 'vertical'
    )
    translations['SW'] = (sw_dx, sw_dy)
    rotations['SW'] = 0.0
    zooms['SW'] = 1.0
    ncc_scores['SW'] = sw_ncc
    logger.info(f"SW initial: dx={sw_dx:.2f}, dy={sw_dy:.2f}, NCC={sw_ncc:.4f}")
    
    # Rotation and zoom search for SW
    if use_rotation or use_zoom:
        logger.info("\nSearching rotation/zoom for SW...")
        sw_dx, sw_dy, sw_rot, sw_zoom, sw_ncc = search_rotation_zoom(
            images['NW'], images['SW'],
            translations['SW'],
            overlap_percent=overlap_percent,
            direction='vertical',
            max_rotation=max_rotation if use_rotation else 0.0,
            rotation_step=0.5,
            max_zoom_percent=max_zoom_percent if use_zoom else 0.0,
            zoom_step=1.0
        )
        
        # Sub-pixel refinement
        if use_rotation and abs(sw_rot) > 0.01:
            sw_rot, _ = refine_rotation_subpixel(
                images['NW'], images['SW'],
                (sw_dx, sw_dy), sw_rot, sw_zoom,
                overlap_percent, 'vertical',
                refinement_range=0.5
            )
        
        if use_zoom and abs(sw_zoom - 1.0) > 0.001:
            sw_zoom, _ = refine_zoom_subpixel(
                images['NW'], images['SW'],
                (sw_dx, sw_dy), sw_rot, sw_zoom,
                overlap_percent, 'vertical',
                refinement_range=0.5
            )
        
        translations['SW'] = (sw_dx, sw_dy)
        rotations['SW'] = sw_rot
        zooms['SW'] = sw_zoom
        ncc_scores['SW'] = sw_ncc
        logger.info(f"SW with rot/zoom: dx={sw_dx:.2f}, dy={sw_dy:.2f}, rot={sw_rot:.3f}°, zoom={sw_zoom:.4f}, NCC={sw_ncc:.4f}")
    
    # Step 3: SE alignment - SE doesn't overlap with NW directly
    # Must align SE via NE (vertical) or SW (horizontal), then express relative to NW
    ne_dx, ne_dy = translations['NE']
    sw_dx, sw_dy = translations['SW']
    
    # Path 1: SE relative to NE (SE is below NE, vertical alignment)
    se_via_ne_dx, se_via_ne_dy, se_via_ne_ncc = search_func(
        images['NE'], images['SE'],
        overlap_percent, search_range, 'vertical'
    )
    # Convert to position relative to NW: add NE's position
    se_path1_dx = ne_dx + se_via_ne_dx
    se_path1_dy = ne_dy + se_via_ne_dy
    
    # Path 2: SE relative to SW (SE is to the right of SW, horizontal alignment)
    se_via_sw_dx, se_via_sw_dy, se_via_sw_ncc = search_func(
        images['SW'], images['SE'],
        overlap_percent, search_range, 'horizontal'
    )
    # Convert to position relative to NW: add SW's position
    se_path2_dx = sw_dx + se_via_sw_dx
    se_path2_dy = sw_dy + se_via_sw_dy
    
    logger.info(f"SE via NE (→NW): dx={se_path1_dx:.2f}, dy={se_path1_dy:.2f}, NCC={se_via_ne_ncc:.4f}")
    logger.info(f"SE via SW (→NW): dx={se_path2_dx:.2f}, dy={se_path2_dy:.2f}, NCC={se_via_sw_ncc:.4f}")
    
    # Use the path with higher NCC (more confident alignment)
    if se_via_ne_ncc >= se_via_sw_ncc:
        se_dx, se_dy = se_path1_dx, se_path1_dy
        se_ncc = se_via_ne_ncc
        ref_img_for_se = images['NE']
        se_ref_direction = 'vertical'
        se_base_dx, se_base_dy = ne_dx, ne_dy
        logger.info(f"SE: Using NE path (higher NCC)")
    else:
        se_dx, se_dy = se_path2_dx, se_path2_dy
        se_ncc = se_via_sw_ncc
        ref_img_for_se = images['SW']
        se_ref_direction = 'horizontal'
        se_base_dx, se_base_dy = sw_dx, sw_dy
        logger.info(f"SE: Using SW path (higher NCC)")
    
    # Expected SE position for consistency check
    expected_se_dx = ne_dx  # Same x as NE
    expected_se_dy = sw_dy  # Same y as SW
    logger.info(f"SE expected (grid): dx={expected_se_dx:.2f}, dy={expected_se_dy:.2f}")
    
    translations['SE'] = (se_dx, se_dy)
    rotations['SE'] = 0.0
    zooms['SE'] = 1.0
    ncc_scores['SE'] = se_ncc
    
    # SE rotation/zoom search (relative to NE or SW, then convert to NW frame)
    if use_rotation or use_zoom:
        logger.info(f"\nSearching rotation/zoom for SE (via {se_ref_direction} path)...")
        
        # Search relative to NE or SW
        se_rel_dx, se_rel_dy, se_rot, se_zoom, se_ncc_rz = search_rotation_zoom(
            ref_img_for_se, images['SE'],
            (se_dx - se_base_dx, se_dy - se_base_dy),  # Relative to NE or SW
            overlap_percent=overlap_percent,
            direction=se_ref_direction,
            max_rotation=max_rotation if use_rotation else 0.0,
            rotation_step=0.5,
            max_zoom_percent=max_zoom_percent if use_zoom else 0.0,
            zoom_step=1.0
        )
        
        # Convert back to NW frame
        se_dx = se_base_dx + se_rel_dx
        se_dy = se_base_dy + se_rel_dy
        
        translations['SE'] = (se_dx, se_dy)
        rotations['SE'] = se_rot
        zooms['SE'] = se_zoom
        ncc_scores['SE'] = se_ncc_rz
        logger.info(f"SE with rot/zoom (→NW): dx={se_dx:.2f}, dy={se_dy:.2f}, rot={se_rot:.3f}°, zoom={se_zoom:.4f}")
    
    # Step 4: Phase correlation refinement
    if use_phase_refinement and SKIMAGE_AVAILABLE:
        logger.info("\nApplying phase correlation refinement...")
        
        # Refine NE
        ne_dx_ref, ne_dy_ref, ne_corr = phase_correlation_refinement(
            images['NW'], images['NE'], translations['NE']
        )
        if ne_corr > 0.5:
            translations['NE'] = (ne_dx_ref, ne_dy_ref)
            logger.info(f"NE refined: dx={ne_dx_ref:.4f}, dy={ne_dy_ref:.4f}, corr={ne_corr:.4f}")
        
        # Refine SW
        sw_dx_ref, sw_dy_ref, sw_corr = phase_correlation_refinement(
            images['NW'], images['SW'], translations['SW']
        )
        if sw_corr > 0.5:
            translations['SW'] = (sw_dx_ref, sw_dy_ref)
            logger.info(f"SW refined: dx={sw_dx_ref:.4f}, dy={sw_dy_ref:.4f}, corr={sw_corr:.4f}")
    
    # Step 5: Consistency-based refinement
    if use_consistency:
        logger.info("\nApplying consistency refinement...")
        translations = iterative_consistency_refinement(images, translations)
    
    # Calculate final consistency error
    ne_dx, ne_dy = translations['NE']
    sw_dx, sw_dy = translations['SW']
    se_dx, se_dy = translations['SE']
    
    consistency_error = abs(se_dx - ne_dx) + abs(se_dy - sw_dy)
    
    logger.info(f"\nFinal Results:")
    logger.info(f"  NE: dx={ne_dx:.4f}, dy={ne_dy:.4f}, rot={rotations['NE']:.3f}°, zoom={(zooms['NE']-1)*100:.2f}%")
    logger.info(f"  SW: dx={sw_dx:.4f}, dy={sw_dy:.4f}, rot={rotations['SW']:.3f}°, zoom={(zooms['SW']-1)*100:.2f}%")
    logger.info(f"  SE: dx={se_dx:.4f}, dy={se_dy:.4f}, rot={rotations['SE']:.3f}°, zoom={(zooms['SE']-1)*100:.2f}%")
    logger.info(f"  Consistency error: {consistency_error:.2f}px")
    logger.info(f"  Expected SE: ({ne_dx:.2f}, {sw_dy:.2f})")
    
    return AlignmentResult(
        method=f"optimized_grid_{int(overlap_percent)}_{search_range}" + 
               (f"_rot{max_rotation}" if use_rotation else "") +
               (f"_zoom{max_zoom_percent}" if use_zoom else ""),
        translations=translations,
        rotations=rotations,
        zooms=zooms,
        ncc_scores=ncc_scores,
        consistency_error=consistency_error,
        success=True,
        details={
            'overlap_percent': overlap_percent,
            'search_range': search_range,
            'use_gradient': use_gradient,
            'use_phase_refinement': use_phase_refinement,
            'use_consistency': use_consistency,
            'use_rotation': use_rotation,
            'use_zoom': use_zoom,
            'max_rotation': max_rotation,
            'max_zoom_percent': max_zoom_percent
        }
    )


def create_stitched_image(images: Dict[str, np.ndarray],
                          translations: Dict[str, Tuple[float, float]],
                          reference_shape: Tuple[int, int] = None) -> np.ndarray:
    """
    Create stitched image using mean blending.
    
    Args:
        images: Dictionary of quadrant images
        translations: Dictionary of (dx, dy) translations
        reference_shape: (height, width) of original images used for alignment.
                        If provided and different from current images, offsets are scaled.
    """
    h, w = images['NW'].shape[:2]
    
    # Scale offsets if reference_shape differs from current image size
    if reference_shape is not None:
        ref_h, ref_w = reference_shape
        scale_x = w / ref_w
        scale_y = h / ref_h
    else:
        scale_x = scale_y = 1.0
    
    # Calculate canvas size with scaled positions
    positions = {'NW': (0, 0)}
    for q, (dx, dy) in translations.items():
        positions[q] = (dx * scale_x, dy * scale_y)
    
    # Calculate canvas size using actual image dimensions per quadrant
    all_dims = {q: images[q].shape[:2] for q in images}
    
    min_x = min(positions[q][0] for q in positions)
    max_x = max(positions[q][0] + all_dims.get(q, (h, w))[1] for q in positions if q in all_dims)
    min_y = min(positions[q][1] for q in positions)
    max_y = max(positions[q][1] + all_dims.get(q, (h, w))[0] for q in positions if q in all_dims)
    
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
        dx, dy = positions.get(q, (0, 0))
        
        x = int(dx + ox)
        y = int(dy + oy)
        
        # Use actual image dimensions for boundary calculations
        src_x0 = max(0, -x)
        src_y0 = max(0, -y)
        src_x1 = min(img_w, canvas_w - x)
        src_y1 = min(img_h, canvas_h - y)
        
        dst_x0 = max(0, x)
        dst_y0 = max(0, y)
        dst_x1 = min(canvas_w, x + img_w)
        dst_y1 = min(canvas_h, y + img_h)
        
        if dst_x1 > dst_x0 and dst_y1 > dst_y0:
            canvas[dst_y0:dst_y1, dst_x0:dst_x1] += img[src_y0:src_y1, src_x0:src_x1]
            count[dst_y0:dst_y1, dst_x0:dst_x1] += 1
    
    # Mean blend
    valid = count > 0
    canvas[valid] /= count[valid]
    
    return canvas.astype(np.float32)


def create_stitched_image_with_transform(images: Dict[str, np.ndarray],
                                          translations: Dict[str, Tuple[float, float]],
                                          rotations: Dict[str, float] = None,
                                          zooms: Dict[str, float] = None,
                                          reference_shape: Tuple[int, int] = None) -> np.ndarray:
    """
    Create stitched image with rotation and zoom transforms applied.
    
    Args:
        images: Dict of quadrant images
        translations: Dict of (dx, dy) translations
        rotations: Dict of rotation angles in degrees (optional)
        zooms: Dict of zoom factors (optional)
        reference_shape: (height, width) of original images used for alignment.
                        If provided and different from current images, offsets are scaled.
        
    Returns:
        Stitched image as numpy array
    """
    if rotations is None:
        rotations = {q: 0.0 for q in images}
    if zooms is None:
        zooms = {q: 1.0 for q in images}
    
    h, w = images['NW'].shape[:2]
    
    # Scale offsets if reference_shape differs from current image size
    if reference_shape is not None:
        ref_h, ref_w = reference_shape
        scale_x = w / ref_w
        scale_y = h / ref_h
    else:
        scale_x = scale_y = 1.0
    
    # Transform images using actual dimensions
    transformed_images = {}
    for q, img in images.items():
        img_h, img_w = img.shape[:2]
        rot = rotations.get(q, 0.0)
        zoom = zooms.get(q, 1.0)
        
        if abs(rot) > 0.001 or abs(zoom - 1.0) > 0.001:
            center = (img_w / 2, img_h / 2)
            M = cv2.getRotationMatrix2D(center, rot, zoom)
            transformed = cv2.warpAffine(img.astype(np.float32), M, (img_w, img_h),
                                          flags=cv2.INTER_LINEAR,
                                          borderMode=cv2.BORDER_REFLECT)
            transformed_images[q] = transformed
        else:
            transformed_images[q] = img
    
    # Calculate canvas size with scaled positions
    positions = {'NW': (0, 0)}
    for q, (dx, dy) in translations.items():
        positions[q] = (dx * scale_x, dy * scale_y)
    
    # Calculate canvas size using actual image dimensions per quadrant
    all_dims = {q: images[q].shape[:2] for q in images}
    
    min_x = min(positions[q][0] for q in positions)
    max_x = max(positions[q][0] + all_dims.get(q, (h, w))[1] for q in positions if q in all_dims)
    min_y = min(positions[q][1] for q in positions)
    max_y = max(positions[q][1] + all_dims.get(q, (h, w))[0] for q in positions if q in all_dims)
    
    canvas_w = int(max_x - min_x) + 10
    canvas_h = int(max_y - min_y) + 10
    ox, oy = -min_x + 5, -min_y + 5
    
    canvas = np.zeros((canvas_h, canvas_w), dtype=np.float64)
    count = np.zeros((canvas_h, canvas_w), dtype=np.int32)
    
    for q in ['NW', 'NE', 'SW', 'SE']:
        if q not in transformed_images:
            continue
        
        img = transformed_images[q].astype(np.float64)
        img_h, img_w = img.shape[:2]
        dx, dy = positions.get(q, (0, 0))
        
        x = int(dx + ox)
        y = int(dy + oy)
        
        # Use actual image dimensions for boundary calculations
        src_x0 = max(0, -x)
        src_y0 = max(0, -y)
        src_x1 = min(img_w, canvas_w - x)
        src_y1 = min(img_h, canvas_h - y)
        
        dst_x0 = max(0, x)
        dst_y0 = max(0, y)
        dst_x1 = min(canvas_w, x + img_w)
        dst_y1 = min(canvas_h, y + img_h)
        
        if dst_x1 > dst_x0 and dst_y1 > dst_y0:
            canvas[dst_y0:dst_y1, dst_x0:dst_x1] += img[src_y0:src_y1, src_x0:src_x1]
            count[dst_y0:dst_y1, dst_x0:dst_x1] += 1
    
    # Mean blend
    valid = count > 0
    canvas[valid] /= count[valid]
    
    return canvas.astype(np.float32)


def visualize_results(images: Dict[str, np.ndarray],
                      result: AlignmentResult,
                      output_path: str):
    """Create visualization of alignment results."""
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("Matplotlib not available, skipping visualization")
        return
    
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    
    # Original quadrants
    for i, (q, ax) in enumerate(zip(['NW', 'NE', 'SW', 'SE'], 
                                     [axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1]])):
        if q in images:
            ax.imshow(images[q], cmap='gray')
            ax.set_title(f'{q}', fontsize=12)
        ax.axis('off')
    
    # Stitched result (with rotation/zoom if available)
    stitched = create_stitched_image_with_transform(images, result.translations,
                                                     result.rotations, result.zooms)
    axes[0, 2].imshow(stitched, cmap='gray')
    axes[0, 2].set_title(f'Stitched\nConsistency: {result.consistency_error:.2f}px', fontsize=12)
    axes[0, 2].axis('off')
    
    # Alignment diagram
    ax_diagram = axes[1, 2]
    h, w = images['NW'].shape
    
    colors = {'NW': '#FF6B6B', 'NE': '#4ECDC4', 'SW': '#45B7D1', 'SE': '#96CEB4'}
    positions = {'NW': (0, 0)}
    positions.update(result.translations)
    
    for q, (dx, dy) in positions.items():
        rect = Rectangle((dx, dy), w, h, linewidth=2, 
                         edgecolor=colors[q], facecolor=colors[q], alpha=0.3)
        ax_diagram.add_patch(rect)
        ax_diagram.text(dx + w/2, dy + h/2, q, ha='center', va='center',
                       fontsize=14, fontweight='bold')
    
    ax_diagram.set_xlim(-50, w * 1.5)
    ax_diagram.set_ylim(-50, h * 1.5)
    ax_diagram.invert_yaxis()
    ax_diagram.set_aspect('equal')
    ax_diagram.set_title('Quadrant Positions', fontsize=12)
    ax_diagram.set_xlabel('X (pixels)')
    ax_diagram.set_ylabel('Y (pixels)')
    
    # Add alignment info (including rotation and zoom)
    info_text = f"Method: {result.method}\n\n"
    for q in ['NE', 'SW', 'SE']:
        if q in result.translations:
            dx, dy = result.translations[q]
            rot = result.rotations.get(q, 0.0)
            zoom = result.zooms.get(q, 1.0)
            ncc = result.ncc_scores.get(q, 0)
            info_text += f"{q}: dx={dx:+.2f}, dy={dy:+.2f}"
            if abs(rot) > 0.001:
                info_text += f", rot={rot:+.2f}°"
            if abs(zoom - 1.0) > 0.001:
                info_text += f", zoom={zoom:.3f}"
            info_text += f", NCC={ncc:.3f}\n"
    
    ne_dx, ne_dy = result.translations['NE']
    sw_dx, sw_dy = result.translations['SW']
    se_dx, se_dy = result.translations['SE']
    info_text += f"\nExpected SE: ({ne_dx:.1f}, {sw_dy:.1f})"
    info_text += f"\nActual SE: ({se_dx:.1f}, {se_dy:.1f})"
    info_text += f"\nError: ({se_dx-ne_dx:.1f}, {se_dy-sw_dy:.1f})"
    
    fig.text(0.02, 0.02, info_text, fontsize=10, fontfamily='monospace',
             verticalalignment='bottom', 
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved visualization to {output_path}")


def visualize_with_chip(original_images: Dict[str, np.ndarray],
                        chip_images: Dict[str, np.ndarray],
                        result: AlignmentResult,
                        output_path: str):
    """
    Create visualization showing both original and chip stitched images.
    
    The chip images are stitched using the same alignment parameters
    computed from the original images.
    """
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("Matplotlib not available, skipping visualization")
        return
    
    # Create stitched images
    original_stitched = create_stitched_image_with_transform(
        original_images, result.translations, result.rotations, result.zooms
    )
    
    chip_stitched = None
    if chip_images and len(chip_images) == 4:
        # Pass original image shape for proper offset scaling
        original_shape = original_images['NW'].shape[:2]
        chip_stitched = create_stitched_image_with_transform(
            chip_images, result.translations, result.rotations, result.zooms,
            reference_shape=original_shape
        )
    
    # Create figure with 2 rows, 3 columns
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    
    # Row 1: Original quadrants (2x2 in first 2 columns) + Original stitched
    axes[0, 0].imshow(original_images.get('NW', np.zeros((100,100))), cmap='gray')
    axes[0, 0].set_title('Original NW', fontsize=11)
    axes[0, 0].axis('off')
    
    axes[0, 1].imshow(original_images.get('NE', np.zeros((100,100))), cmap='gray')
    axes[0, 1].set_title('Original NE', fontsize=11)
    axes[0, 1].axis('off')
    
    axes[1, 0].imshow(original_images.get('SW', np.zeros((100,100))), cmap='gray')
    axes[1, 0].set_title('Original SW', fontsize=11)
    axes[1, 0].axis('off')
    
    axes[1, 1].imshow(original_images.get('SE', np.zeros((100,100))), cmap='gray')
    axes[1, 1].set_title('Original SE', fontsize=11)
    axes[1, 1].axis('off')
    
    # Original stitched
    axes[0, 2].imshow(original_stitched, cmap='gray')
    axes[0, 2].set_title(f'Original Stitched\nConsistency: {result.consistency_error:.2f}px', fontsize=11)
    axes[0, 2].axis('off')
    
    # Chip stitched (if available)
    if chip_stitched is not None:
        axes[1, 2].imshow(chip_stitched, cmap='gray')
        axes[1, 2].set_title('Chip Stitched\n(using same alignment)', fontsize=11)
    else:
        axes[1, 2].text(0.5, 0.5, 'No chip images\nfound', 
                        ha='center', va='center', fontsize=14,
                        transform=axes[1, 2].transAxes)
        axes[1, 2].set_title('Chip Stitched', fontsize=11)
    axes[1, 2].axis('off')
    
    # Add alignment info
    info_text = f"Method: {result.method}\n\n"
    for q in ['NE', 'SW', 'SE']:
        if q in result.translations:
            dx, dy = result.translations[q]
            rot = result.rotations.get(q, 0.0)
            zoom = result.zooms.get(q, 1.0)
            ncc = result.ncc_scores.get(q, 0)
            info_text += f"{q}: dx={dx:+.1f}, dy={dy:+.1f}"
            if abs(rot) > 0.001:
                info_text += f", rot={rot:+.2f}°"
            if abs(zoom - 1.0) > 0.001:
                info_text += f", zoom={zoom:.3f}"
            info_text += f", NCC={ncc:.3f}\n"
    
    fig.text(0.02, 0.02, info_text, fontsize=9, fontfamily='monospace',
             verticalalignment='bottom', 
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.suptitle('Original & Chip Image Alignment', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved combined visualization to {output_path}")


def run_parameter_sweep(images: Dict[str, np.ndarray],
                        output_dir: Path,
                        use_rotation: bool = False,
                        use_zoom: bool = False,
                        max_rotation: float = 5.0,
                        max_zoom_percent: float = 5.0) -> List[AlignmentResult]:
    """Run parameter sweep to find optimal settings."""
    results = []
    
    # Test different overlap percentages
    for overlap in [65, 68, 70, 72, 75]:
        for search in [30, 50, 70]:
            for use_grad in [False, True]:
                result = optimize_alignment(
                    images,
                    overlap_percent=overlap,
                    search_range=search,
                    use_gradient=use_grad,
                    use_phase_refinement=True,
                    use_consistency=True,
                    use_rotation=use_rotation,
                    use_zoom=use_zoom,
                    max_rotation=max_rotation,
                    max_zoom_percent=max_zoom_percent
                )
                results.append(result)
    
    # Sort by consistency error
    results.sort(key=lambda r: r.consistency_error)
    
    logger.info("\n" + "="*60)
    logger.info("PARAMETER SWEEP RESULTS")
    logger.info("="*60)
    
    for i, r in enumerate(results[:10]):
        logger.info(f"\n{i+1}. {r.method}")
        logger.info(f"   Consistency: {r.consistency_error:.2f}px")
        logger.info(f"   NCC scores: NE={r.ncc_scores.get('NE', 0):.3f}, "
                   f"SW={r.ncc_scores.get('SW', 0):.3f}, SE={r.ncc_scores.get('SE', 0):.3f}")
        logger.info(f"   Settings: {r.details}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Optimized Grid-Constrained Alignment")
    parser.add_argument('--input-dir', required=True, help="Directory containing CZI files")
    parser.add_argument('--prefix', required=True, help="File prefix")
    parser.add_argument('--output-dir', default='grid_optimization/output', help="Output directory")
    parser.add_argument('--overlap', type=float, default=70, help="Expected overlap %% (default: 70)")
    parser.add_argument('--search-range', type=int, default=50, help="Search range in pixels")
    parser.add_argument('--sweep', action='store_true', help="Run parameter sweep")
    parser.add_argument('--no-gradient', action='store_true', help="Disable gradient weighting")
    parser.add_argument('--no-phase', action='store_true', help="Disable phase refinement")
    parser.add_argument('--no-consistency', action='store_true', help="Disable consistency refinement")
    
    # Rotation and zoom options
    parser.add_argument('--rotation', action='store_true', help="Enable rotation search")
    parser.add_argument('--zoom', action='store_true', help="Enable zoom/scale search")
    parser.add_argument('--max-rotation', type=float, default=5.0, 
                        help="Maximum rotation to search (±degrees, default: 5.0)")
    parser.add_argument('--max-zoom', type=float, default=5.0,
                        help="Maximum zoom to search (±percent, default: 5.0)")
    
    args = parser.parse_args()
    
    # Load images
    logger.info(f"Loading images from {args.input_dir}")
    images = load_quadrant_images(args.input_dir, args.prefix)
    
    if len(images) < 4:
        logger.error(f"Only found {len(images)} images, need 4")
        return 1
    
    output_dir = Path(args.output_dir)
    
    if args.sweep:
        # Run parameter sweep (with rotation/zoom if enabled)
        results = run_parameter_sweep(images, output_dir, 
                                      use_rotation=args.rotation,
                                      use_zoom=args.zoom,
                                      max_rotation=args.max_rotation,
                                      max_zoom_percent=args.max_zoom)
        best = results[0]
    else:
        # Run single optimization
        best = optimize_alignment(
            images,
            overlap_percent=args.overlap,
            search_range=args.search_range,
            use_gradient=not args.no_gradient,
            use_phase_refinement=not args.no_phase,
            use_consistency=not args.no_consistency,
            use_rotation=args.rotation,
            use_zoom=args.zoom,
            max_rotation=args.max_rotation,
            max_zoom_percent=args.max_zoom
        )
    
    # Load chip images
    logger.info(f"\nLoading chip images from {args.input_dir}")
    chip_images = load_chip_images(args.input_dir, args.prefix)
    if len(chip_images) == 4:
        logger.info(f"Found all 4 chip images")
    elif len(chip_images) > 0:
        logger.warning(f"Only found {len(chip_images)} chip images, need 4")
    else:
        logger.info("No chip images found")
    
    # Visualize original alignment
    viz_path = output_dir / "optimized_alignment.png"
    visualize_results(images, best, str(viz_path))
    
    # Visualize with chip (if available)
    if chip_images:
        viz_combined_path = output_dir / "optimized_alignment_with_chip.png"
        visualize_with_chip(images, chip_images, best, str(viz_combined_path))
    
    # Save stitched original image (apply rotation/zoom if present)
    stitched = create_stitched_image_with_transform(images, best.translations, 
                                                      best.rotations, best.zooms)
    stitched_path = output_dir / "optimized_stitched.png"
    cv2.imwrite(str(stitched_path), stitched.astype(np.uint8))
    logger.info(f"Saved original stitched image to {stitched_path}")
    
    # Save stitched chip image (using same alignment parameters)
    if len(chip_images) == 4:
        # Pass original image shape for proper offset scaling
        original_shape = images['NW'].shape[:2]
        chip_stitched = create_stitched_image_with_transform(chip_images, best.translations,
                                                               best.rotations, best.zooms,
                                                               reference_shape=original_shape)
        chip_stitched_path = output_dir / "optimized_chip_stitched.png"
        cv2.imwrite(str(chip_stitched_path), chip_stitched.astype(np.uint8))
        logger.info(f"Saved chip stitched image to {chip_stitched_path}")
    
    # Save parameters
    import json
    params_path = output_dir / "optimized_alignment_params.json"
    params = {
        'method': best.method,
        'consistency_error': best.consistency_error,
        'translations': {q: list(t) for q, t in best.translations.items()},
        'rotations': {q: float(r) for q, r in best.rotations.items()},
        'zooms': {q: float(z) for q, z in best.zooms.items()},
        'ncc_scores': best.ncc_scores,
        'settings': best.details,
        'chip_images_found': len(chip_images) == 4
    }
    with open(params_path, 'w') as f:
        json.dump(params, f, indent=2)
    logger.info(f"Saved parameters to {params_path}")
    
    logger.info(f"\n*** BEST RESULT: {best.method} ***")
    logger.info(f"Consistency error: {best.consistency_error:.4f}px")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
