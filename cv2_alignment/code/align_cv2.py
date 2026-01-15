#!/usr/bin/env python3
"""
OpenCV-based Image Alignment for 2x2 Quadrant Stitching

All quadrants (NE, SW, SE) are aligned relative to NW.
Supports translation, rotation, and zoom optimization.

Methods:
1. Feature-based (ORB, SIFT, AKAZE) with homography estimation
2. ECC (Enhanced Correlation Coefficient) for sub-pixel refinement
3. Phase correlation for translation estimation

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
class QuadrantAlignment:
    """Alignment parameters for a single quadrant relative to NW."""
    dx: float = 0.0
    dy: float = 0.0
    rotation_deg: float = 0.0
    zoom: float = 1.0
    ncc: float = 0.0
    method: str = ""


@dataclass 
class AlignmentResult:
    """Complete alignment result for all quadrants."""
    quadrants: Dict[str, QuadrantAlignment] = field(default_factory=dict)
    consistency_error: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            'quadrants': {
                q: {
                    'dx': float(qa.dx),
                    'dy': float(qa.dy),
                    'rotation_deg': float(qa.rotation_deg),
                    'zoom': float(qa.zoom),
                    'ncc': float(qa.ncc),
                    'method': qa.method
                }
                for q, qa in self.quadrants.items()
            },
            'consistency_error': float(self.consistency_error)
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
                
                # Squeeze dimensions
                while img_data.ndim > 2 and img_data.shape[0] == 1:
                    img_data = img_data.squeeze(axis=0)
                
                if img_data.ndim == 4:
                    img_data = img_data[img_data.shape[0] // 2]
                
                if img_data.ndim == 3:
                    if img_data.shape[0] < img_data.shape[-1]:
                        img = img_data[0]
                    else:
                        img = img_data[:, :, 0]
                else:
                    img = img_data
                
                # Normalize to float32
                if img.dtype == np.uint16:
                    img = (img / 65535.0 * 255).astype(np.float32)
                else:
                    img = img.astype(np.float32)
                
                images[quadrant] = img
                logger.info(f"Loaded {quadrant}: {czi_matches[0].name}, shape={img.shape}")
                continue
            except ImportError:
                logger.warning("czifile not installed, trying TIFF...")
        
        # Try TIFF
        for ext in ['*.tif', '*.tiff', '*.png']:
            tiff_pattern = f"{prefix}{quadrant}{ext[1:]}"
            tiff_matches = list(input_path.glob(tiff_pattern))
            if tiff_matches:
                img = cv2.imread(str(tiff_matches[0]), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    images[quadrant] = img.astype(np.float32)
                    logger.info(f"Loaded {quadrant}: {tiff_matches[0].name}")
                    break
    
    return images


def load_chip_images(input_dir: str, prefix: str) -> Dict[str, np.ndarray]:
    """Load chip quadrant images."""
    images = {}
    input_path = Path(input_dir)
    
    for quadrant in ['NW', 'NE', 'SW', 'SE']:
        patterns = [
            f"{prefix}chip{quadrant}.czi",
            f"{prefix}_chip{quadrant}.czi",
        ]
        
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
                    
                    if img_data.ndim == 3:
                        if img_data.shape[0] < img_data.shape[-1]:
                            img = img_data[0]
                        else:
                            img = img_data[:, :, 0]
                    else:
                        img = img_data
                    
                    if img.dtype == np.uint16:
                        img = (img / 65535.0 * 255).astype(np.float32)
                    else:
                        img = img.astype(np.float32)
                    
                    images[quadrant] = img
                    logger.info(f"Loaded chip {quadrant}: {matches[0].name}")
                    break
                except ImportError:
                    pass
    
    return images


def extract_overlap_region(img: np.ndarray, 
                            direction: str,
                            overlap_percent: float = 70) -> np.ndarray:
    """Extract overlap region from image."""
    h, w = img.shape[:2]
    
    if direction == 'right':  # Right edge (for NW→NE)
        overlap_w = int(w * overlap_percent / 100)
        return img[:, -overlap_w:]
    elif direction == 'left':  # Left edge (for NE)
        overlap_w = int(w * overlap_percent / 100)
        return img[:, :overlap_w]
    elif direction == 'bottom':  # Bottom edge (for NW→SW)
        overlap_h = int(h * overlap_percent / 100)
        return img[-overlap_h:, :]
    elif direction == 'top':  # Top edge (for SW)
        overlap_h = int(h * overlap_percent / 100)
        return img[:overlap_h, :]
    else:
        return img


def align_with_features(ref_img: np.ndarray,
                        target_img: np.ndarray,
                        detector_type: str = 'ORB',
                        max_rotation: float = 5.0,
                        max_zoom_percent: float = 5.0) -> Tuple[float, float, float, float, float]:
    """
    Align target to reference using feature matching.
    
    Returns:
        (dx, dy, rotation_deg, zoom, match_score)
    """
    # Convert to uint8 for feature detection
    ref_u8 = np.clip(ref_img, 0, 255).astype(np.uint8)
    target_u8 = np.clip(target_img, 0, 255).astype(np.uint8)
    
    # Create detector
    if detector_type == 'ORB':
        detector = cv2.ORB_create(nfeatures=5000)
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    elif detector_type == 'SIFT':
        detector = cv2.SIFT_create(nfeatures=5000)
        matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    elif detector_type == 'AKAZE':
        detector = cv2.AKAZE_create()
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    else:
        detector = cv2.ORB_create(nfeatures=5000)
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    
    # Detect and compute
    kp1, des1 = detector.detectAndCompute(ref_u8, None)
    kp2, des2 = detector.detectAndCompute(target_u8, None)
    
    if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
        logger.warning(f"Not enough features: ref={len(kp1) if kp1 else 0}, target={len(kp2) if kp2 else 0}")
        return 0.0, 0.0, 0.0, 1.0, 0.0
    
    # Match features
    matches = matcher.knnMatch(des1, des2, k=2)
    
    # Ratio test
    good_matches = []
    for m_n in matches:
        if len(m_n) == 2:
            m, n = m_n
            if m.distance < 0.7 * n.distance:
                good_matches.append(m)
    
    if len(good_matches) < 4:
        logger.warning(f"Not enough good matches: {len(good_matches)}")
        return 0.0, 0.0, 0.0, 1.0, 0.0
    
    # Get matching points
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    
    # Estimate homography
    H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 3.0)
    
    if H is None:
        logger.warning("Could not estimate homography")
        return 0.0, 0.0, 0.0, 1.0, 0.0
    
    # Decompose homography to get rotation, scale, translation
    # H = [[s*cos(θ), -s*sin(θ), tx],
    #      [s*sin(θ),  s*cos(θ), ty],
    #      [0,         0,        1 ]]
    
    # Extract translation
    dx = H[0, 2]
    dy = H[1, 2]
    
    # Extract rotation and scale
    a = H[0, 0]
    b = H[0, 1]
    c = H[1, 0]
    d = H[1, 1]
    
    # Scale (average of x and y scales)
    sx = np.sqrt(a*a + c*c)
    sy = np.sqrt(b*b + d*d)
    zoom = (sx + sy) / 2
    
    # Rotation
    rotation_rad = np.arctan2(c, a)
    rotation_deg = np.degrees(rotation_rad)
    
    # Clamp rotation and zoom
    if abs(rotation_deg) > max_rotation:
        rotation_deg = np.clip(rotation_deg, -max_rotation, max_rotation)
    
    max_zoom = 1.0 + max_zoom_percent / 100
    min_zoom = 1.0 - max_zoom_percent / 100
    if zoom > max_zoom or zoom < min_zoom:
        zoom = np.clip(zoom, min_zoom, max_zoom)
    
    # Match score
    inliers = np.sum(mask) if mask is not None else 0
    match_score = inliers / len(good_matches) if good_matches else 0.0
    
    logger.debug(f"Features: {len(good_matches)} matches, {inliers} inliers, score={match_score:.2f}")
    
    return dx, dy, rotation_deg, zoom, match_score


def align_with_ecc(ref_img: np.ndarray,
                   target_img: np.ndarray,
                   motion_type: str = 'euclidean',
                   max_rotation: float = 5.0,
                   max_zoom_percent: float = 5.0,
                   num_iterations: int = 1000,
                   termination_eps: float = 1e-6) -> Tuple[float, float, float, float, float]:
    """
    Align using Enhanced Correlation Coefficient (ECC).
    
    Returns:
        (dx, dy, rotation_deg, zoom, correlation)
    """
    # Normalize images
    ref_norm = cv2.normalize(ref_img, None, 0, 255, cv2.NORM_MINMAX).astype(np.float32)
    target_norm = cv2.normalize(target_img, None, 0, 255, cv2.NORM_MINMAX).astype(np.float32)
    
    # Define motion model
    if motion_type == 'translation':
        warp_mode = cv2.MOTION_TRANSLATION
        warp_matrix = np.eye(2, 3, dtype=np.float32)
    elif motion_type == 'euclidean':
        warp_mode = cv2.MOTION_EUCLIDEAN
        warp_matrix = np.eye(2, 3, dtype=np.float32)
    elif motion_type == 'affine':
        warp_mode = cv2.MOTION_AFFINE
        warp_matrix = np.eye(2, 3, dtype=np.float32)
    else:
        warp_mode = cv2.MOTION_EUCLIDEAN
        warp_matrix = np.eye(2, 3, dtype=np.float32)
    
    # Termination criteria
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 
                num_iterations, termination_eps)
    
    try:
        cc, warp_matrix = cv2.findTransformECC(
            ref_norm, target_norm, warp_matrix, warp_mode, criteria
        )
    except cv2.error as e:
        logger.warning(f"ECC failed: {e}")
        return 0.0, 0.0, 0.0, 1.0, 0.0
    
    # Extract parameters
    dx = warp_matrix[0, 2]
    dy = warp_matrix[1, 2]
    
    if warp_mode in [cv2.MOTION_EUCLIDEAN, cv2.MOTION_AFFINE]:
        rotation_rad = np.arctan2(warp_matrix[1, 0], warp_matrix[0, 0])
        rotation_deg = np.degrees(rotation_rad)
        
        if warp_mode == cv2.MOTION_AFFINE:
            sx = np.sqrt(warp_matrix[0, 0]**2 + warp_matrix[1, 0]**2)
            sy = np.sqrt(warp_matrix[0, 1]**2 + warp_matrix[1, 1]**2)
            zoom = (sx + sy) / 2
        else:
            zoom = 1.0
    else:
        rotation_deg = 0.0
        zoom = 1.0
    
    # Clamp
    rotation_deg = np.clip(rotation_deg, -max_rotation, max_rotation)
    max_z = 1.0 + max_zoom_percent / 100
    min_z = 1.0 - max_zoom_percent / 100
    zoom = np.clip(zoom, min_z, max_z)
    
    return dx, dy, rotation_deg, zoom, cc


def align_with_phase_correlation(ref_img: np.ndarray,
                                  target_img: np.ndarray) -> Tuple[float, float, float]:
    """
    Align using phase correlation (translation only).
    
    Returns:
        (dx, dy, response)
    """
    # Ensure same size
    h = min(ref_img.shape[0], target_img.shape[0])
    w = min(ref_img.shape[1], target_img.shape[1])
    
    ref_crop = ref_img[:h, :w].astype(np.float32)
    target_crop = target_img[:h, :w].astype(np.float32)
    
    # Phase correlation
    shift, response = cv2.phaseCorrelate(ref_crop, target_crop)
    
    dx, dy = shift
    return dx, dy, response


def align_quadrant_to_nw(nw_img: np.ndarray,
                          target_img: np.ndarray,
                          direction: str,
                          overlap_percent: float = 70,
                          method: str = 'ecc',
                          max_rotation: float = 5.0,
                          max_zoom_percent: float = 5.0,
                          detector_type: str = 'ORB') -> QuadrantAlignment:
    """
    Align a quadrant image to NW.
    
    Args:
        nw_img: NW reference image
        target_img: Target quadrant image
        direction: 'horizontal' (NE), 'vertical' (SW)
        overlap_percent: Expected overlap percentage
        method: 'ecc', 'features', or 'phase'
        max_rotation: Maximum rotation (degrees)
        max_zoom_percent: Maximum zoom (percent)
        detector_type: Feature detector for 'features' method
        
    Returns:
        QuadrantAlignment with parameters relative to NW
    """
    h, w = nw_img.shape[:2]
    
    # Extract overlap regions
    if direction == 'horizontal':
        # NE is to the right of NW
        ref_overlap = extract_overlap_region(nw_img, 'right', overlap_percent)
        target_overlap = extract_overlap_region(target_img, 'left', overlap_percent)
        base_dx = w - int(w * overlap_percent / 100)
        base_dy = 0
    else:  # vertical
        # SW is below NW
        ref_overlap = extract_overlap_region(nw_img, 'bottom', overlap_percent)
        target_overlap = extract_overlap_region(target_img, 'top', overlap_percent)
        base_dx = 0
        base_dy = h - int(h * overlap_percent / 100)
    
    # Align overlap regions
    if method == 'features':
        dx, dy, rot, zoom, score = align_with_features(
            ref_overlap, target_overlap, detector_type, max_rotation, max_zoom_percent
        )
    elif method == 'ecc':
        dx, dy, rot, zoom, score = align_with_ecc(
            ref_overlap, target_overlap, 'euclidean', max_rotation, max_zoom_percent
        )
    elif method == 'ecc_affine':
        dx, dy, rot, zoom, score = align_with_ecc(
            ref_overlap, target_overlap, 'affine', max_rotation, max_zoom_percent
        )
    else:  # phase
        dx, dy, score = align_with_phase_correlation(ref_overlap, target_overlap)
        rot, zoom = 0.0, 1.0
    
    # Convert to NW reference frame
    final_dx = base_dx + dx
    final_dy = base_dy + dy
    
    return QuadrantAlignment(
        dx=final_dx,
        dy=final_dy,
        rotation_deg=rot,
        zoom=zoom,
        ncc=score,
        method=method
    )


def align_se_via_chain(images: Dict[str, np.ndarray],
                       ne_alignment: QuadrantAlignment,
                       sw_alignment: QuadrantAlignment,
                       overlap_percent: float = 70,
                       method: str = 'ecc',
                       max_rotation: float = 5.0,
                       max_zoom_percent: float = 5.0,
                       detector_type: str = 'ORB') -> QuadrantAlignment:
    """
    Align SE quadrant via NE or SW chain, returning position relative to NW.
    """
    h, w = images['NW'].shape[:2]
    
    # Path 1: SE via NE (SE is below NE)
    ne_img = images['NE']
    se_img = images['SE']
    
    ref_overlap_ne = extract_overlap_region(ne_img, 'bottom', overlap_percent)
    target_overlap_ne = extract_overlap_region(se_img, 'top', overlap_percent)
    
    if method == 'features':
        dx1, dy1, rot1, zoom1, score1 = align_with_features(
            ref_overlap_ne, target_overlap_ne, detector_type, max_rotation, max_zoom_percent
        )
    elif method in ['ecc', 'ecc_affine']:
        motion = 'affine' if method == 'ecc_affine' else 'euclidean'
        dx1, dy1, rot1, zoom1, score1 = align_with_ecc(
            ref_overlap_ne, target_overlap_ne, motion, max_rotation, max_zoom_percent
        )
    else:
        dx1, dy1, score1 = align_with_phase_correlation(ref_overlap_ne, target_overlap_ne)
        rot1, zoom1 = 0.0, 1.0
    
    # Convert to NW frame
    base_dy1 = h - int(h * overlap_percent / 100)
    se_via_ne_dx = ne_alignment.dx + dx1
    se_via_ne_dy = ne_alignment.dy + base_dy1 + dy1
    
    # Path 2: SE via SW (SE is to the right of SW)
    sw_img = images['SW']
    
    ref_overlap_sw = extract_overlap_region(sw_img, 'right', overlap_percent)
    target_overlap_sw = extract_overlap_region(se_img, 'left', overlap_percent)
    
    if method == 'features':
        dx2, dy2, rot2, zoom2, score2 = align_with_features(
            ref_overlap_sw, target_overlap_sw, detector_type, max_rotation, max_zoom_percent
        )
    elif method in ['ecc', 'ecc_affine']:
        motion = 'affine' if method == 'ecc_affine' else 'euclidean'
        dx2, dy2, rot2, zoom2, score2 = align_with_ecc(
            ref_overlap_sw, target_overlap_sw, motion, max_rotation, max_zoom_percent
        )
    else:
        dx2, dy2, score2 = align_with_phase_correlation(ref_overlap_sw, target_overlap_sw)
        rot2, zoom2 = 0.0, 1.0
    
    # Convert to NW frame
    base_dx2 = w - int(w * overlap_percent / 100)
    se_via_sw_dx = sw_alignment.dx + base_dx2 + dx2
    se_via_sw_dy = sw_alignment.dy + dy2
    
    logger.info(f"SE via NE: dx={se_via_ne_dx:.2f}, dy={se_via_ne_dy:.2f}, score={score1:.4f}")
    logger.info(f"SE via SW: dx={se_via_sw_dx:.2f}, dy={se_via_sw_dy:.2f}, score={score2:.4f}")
    
    # Use path with higher score
    if score1 >= score2:
        logger.info("SE: Using NE path")
        return QuadrantAlignment(
            dx=se_via_ne_dx, dy=se_via_ne_dy,
            rotation_deg=rot1, zoom=zoom1,
            ncc=score1, method=f"{method}_via_NE"
        )
    else:
        logger.info("SE: Using SW path")
        return QuadrantAlignment(
            dx=se_via_sw_dx, dy=se_via_sw_dy,
            rotation_deg=rot2, zoom=zoom2,
            ncc=score2, method=f"{method}_via_SW"
        )


def stitch_images(images: Dict[str, np.ndarray],
                  result: AlignmentResult) -> np.ndarray:
    """Stitch images using alignment result."""
    h, w = images['NW'].shape[:2]
    
    # Get positions
    positions = {'NW': (0, 0)}
    for q in ['NE', 'SW', 'SE']:
        if q in result.quadrants:
            qa = result.quadrants[q]
            positions[q] = (qa.dx, qa.dy)
    
    # Calculate canvas size
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
        
        # Apply rotation and zoom if present
        if q in result.quadrants:
            qa = result.quadrants[q]
            if abs(qa.rotation_deg) > 0.001 or abs(qa.zoom - 1.0) > 0.001:
                center = (w / 2, h / 2)
                M = cv2.getRotationMatrix2D(center, qa.rotation_deg, qa.zoom)
                img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_REFLECT)
        
        dx, dy = positions.get(q, (0, 0))
        x = int(dx + ox)
        y = int(dy + oy)
        
        # Clip to canvas bounds
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
    
    # Mean blend
    valid = count > 0
    canvas[valid] /= count[valid]
    
    return canvas.astype(np.float32)


def visualize_results(images: Dict[str, np.ndarray],
                      chip_images: Dict[str, np.ndarray],
                      result: AlignmentResult,
                      output_path: str):
    """Create visualization."""
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except ImportError:
        logger.warning("Matplotlib not available")
        return
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    
    # Original quadrants
    for i, (q, ax) in enumerate(zip(['NW', 'NE', 'SW', 'SE'], 
                                     [axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1]])):
        if q in images:
            ax.imshow(images[q], cmap='gray')
            if q in result.quadrants:
                qa = result.quadrants[q]
                ax.set_title(f'{q}\ndx={qa.dx:.1f}, dy={qa.dy:.1f}\n'
                            f'rot={qa.rotation_deg:.2f}°, zoom={qa.zoom:.3f}', fontsize=10)
            else:
                ax.set_title(f'{q} (reference)', fontsize=10)
        ax.axis('off')
    
    # Stitched original
    stitched = stitch_images(images, result)
    axes[0, 2].imshow(stitched, cmap='gray')
    axes[0, 2].set_title(f'Original Stitched\nConsistency: {result.consistency_error:.2f}px', fontsize=11)
    axes[0, 2].axis('off')
    
    # Stitched chip
    if len(chip_images) == 4:
        chip_stitched = stitch_images(chip_images, result)
        axes[1, 2].imshow(chip_stitched, cmap='gray')
        axes[1, 2].set_title('Chip Stitched\n(using same alignment)', fontsize=11)
    else:
        axes[1, 2].text(0.5, 0.5, 'No chip images', ha='center', va='center',
                        transform=axes[1, 2].transAxes, fontsize=14)
        axes[1, 2].set_title('Chip Stitched', fontsize=11)
    axes[1, 2].axis('off')
    
    # Info text
    info = "Alignment Results (all relative to NW):\n\n"
    for q in ['NE', 'SW', 'SE']:
        if q in result.quadrants:
            qa = result.quadrants[q]
            info += f"{q}: dx={qa.dx:+.1f}, dy={qa.dy:+.1f}"
            if abs(qa.rotation_deg) > 0.001:
                info += f", rot={qa.rotation_deg:+.2f}°"
            if abs(qa.zoom - 1.0) > 0.001:
                info += f", zoom={qa.zoom:.3f}"
            info += f", score={qa.ncc:.3f}\n"
    
    fig.text(0.02, 0.02, info, fontsize=9, fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.suptitle('CV2 Alignment (All → NW)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved visualization to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="CV2-based Image Alignment")
    parser.add_argument('--input-dir', required=True, help="Directory containing images")
    parser.add_argument('--prefix', required=True, help="File prefix")
    parser.add_argument('--output-dir', default='cv2_alignment/output', help="Output directory")
    parser.add_argument('--overlap', type=float, default=70, help="Expected overlap %% (default: 70)")
    parser.add_argument('--method', choices=['ecc', 'ecc_affine', 'features', 'phase'],
                        default='ecc', help="Alignment method")
    parser.add_argument('--detector', choices=['ORB', 'SIFT', 'AKAZE'],
                        default='ORB', help="Feature detector (for 'features' method)")
    parser.add_argument('--max-rotation', type=float, default=5.0,
                        help="Maximum rotation (±degrees)")
    parser.add_argument('--max-zoom', type=float, default=5.0,
                        help="Maximum zoom (±percent)")
    
    args = parser.parse_args()
    
    # Load images
    logger.info(f"Loading images from {args.input_dir}")
    images = load_images(args.input_dir, args.prefix)
    
    if len(images) < 4:
        logger.error(f"Only found {len(images)} images, need 4")
        return 1
    
    logger.info(f"\n{'='*60}")
    logger.info(f"CV2 Alignment: method={args.method}, overlap={args.overlap}%")
    logger.info(f"Max rotation: ±{args.max_rotation}°, Max zoom: ±{args.max_zoom}%")
    logger.info(f"{'='*60}")
    
    result = AlignmentResult()
    
    # Align NE to NW (horizontal)
    logger.info("\nAligning NE to NW...")
    ne_align = align_quadrant_to_nw(
        images['NW'], images['NE'], 'horizontal',
        args.overlap, args.method, args.max_rotation, args.max_zoom, args.detector
    )
    result.quadrants['NE'] = ne_align
    logger.info(f"NE: dx={ne_align.dx:.2f}, dy={ne_align.dy:.2f}, "
               f"rot={ne_align.rotation_deg:.3f}°, zoom={ne_align.zoom:.4f}, score={ne_align.ncc:.4f}")
    
    # Align SW to NW (vertical)
    logger.info("\nAligning SW to NW...")
    sw_align = align_quadrant_to_nw(
        images['NW'], images['SW'], 'vertical',
        args.overlap, args.method, args.max_rotation, args.max_zoom, args.detector
    )
    result.quadrants['SW'] = sw_align
    logger.info(f"SW: dx={sw_align.dx:.2f}, dy={sw_align.dy:.2f}, "
               f"rot={sw_align.rotation_deg:.3f}°, zoom={sw_align.zoom:.4f}, score={sw_align.ncc:.4f}")
    
    # Align SE via chain (NE or SW)
    logger.info("\nAligning SE via NE/SW chain...")
    se_align = align_se_via_chain(
        images, ne_align, sw_align,
        args.overlap, args.method, args.max_rotation, args.max_zoom, args.detector
    )
    result.quadrants['SE'] = se_align
    logger.info(f"SE: dx={se_align.dx:.2f}, dy={se_align.dy:.2f}, "
               f"rot={se_align.rotation_deg:.3f}°, zoom={se_align.zoom:.4f}")
    
    # Calculate consistency error
    expected_se_dx = ne_align.dx
    expected_se_dy = sw_align.dy
    result.consistency_error = abs(se_align.dx - expected_se_dx) + abs(se_align.dy - expected_se_dy)
    
    logger.info(f"\nExpected SE: ({expected_se_dx:.1f}, {expected_se_dy:.1f})")
    logger.info(f"Actual SE: ({se_align.dx:.1f}, {se_align.dy:.1f})")
    logger.info(f"Consistency error: {result.consistency_error:.2f}px")
    
    # Load chip images
    logger.info(f"\nLoading chip images...")
    chip_images = load_chip_images(args.input_dir, args.prefix)
    if len(chip_images) == 4:
        logger.info("Found all 4 chip images")
    else:
        logger.info(f"Found {len(chip_images)} chip images")
    
    # Save outputs
    output_dir = Path(args.output_dir)
    
    # Visualization
    viz_path = output_dir / "cv2_alignment.png"
    visualize_results(images, chip_images, result, str(viz_path))
    
    # Stitched images
    stitched = stitch_images(images, result)
    stitched_path = output_dir / "cv2_stitched.png"
    cv2.imwrite(str(stitched_path), np.clip(stitched, 0, 255).astype(np.uint8))
    logger.info(f"Saved original stitched to {stitched_path}")
    
    if len(chip_images) == 4:
        chip_stitched = stitch_images(chip_images, result)
        chip_path = output_dir / "cv2_chip_stitched.png"
        cv2.imwrite(str(chip_path), np.clip(chip_stitched, 0, 255).astype(np.uint8))
        logger.info(f"Saved chip stitched to {chip_path}")
    
    # Parameters JSON
    params_path = output_dir / "cv2_alignment_params.json"
    with open(params_path, 'w') as f:
        json.dump(result.to_dict(), f, indent=2)
    logger.info(f"Saved parameters to {params_path}")
    
    logger.info(f"\n*** ALIGNMENT COMPLETE ***")
    logger.info(f"Method: {args.method}")
    logger.info(f"Consistency error: {result.consistency_error:.2f}px")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
