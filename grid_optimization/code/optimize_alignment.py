#!/usr/bin/env python3
"""
CLI script to optimize image alignment parameters.
Tries multiple approaches and reports the best configuration.

Usage:
    python optimize_alignment.py --input-dir raw_data/2025.10.22_opnT2 --prefix "2025.10.22-10.34.56-4134-opnT2_"
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import numpy as np
import cv2

# Scikit-image imports for advanced registration
try:
    from skimage.registration import phase_cross_correlation
    from skimage.transform import EuclideanTransform, AffineTransform, warp
    from skimage.feature import ORB as SkimageORB, match_descriptors
    from skimage.measure import ransac
    from skimage.filters import gaussian
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False
    print("Warning: scikit-image not available, some methods will be skipped")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.lib.io import load_image

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AlignmentResult:
    """Result of an alignment attempt."""
    method: str
    params: dict
    translations: Dict[str, Tuple[float, float]]
    rotations: Dict[str, float]
    reprojection_errors: Dict[str, float]
    total_matches: int
    success: bool
    notes: str = ""


def load_quadrant_images(input_dir: str, prefix: str) -> Dict[str, np.ndarray]:
    """Load quadrant images from directory."""
    images = {}
    quadrants = ['NW', 'NE', 'SW', 'SE']
    
    for q in quadrants:
        # Try different file patterns
        patterns = [
            f"{prefix}{q}.czi",
            f"{prefix}{q}2.czi",  # Some files have 2 suffix
        ]
        
        for pattern in patterns:
            filepath = Path(input_dir) / pattern
            if filepath.exists():
                try:
                    img, metadata = load_image(filepath)
                    if img is not None:
                        # Convert to grayscale uint8
                        if img.ndim == 3:
                            img = img[:, :, 0]
                        if img.dtype == np.uint16:
                            img = (img / 256).astype(np.uint8)
                        elif img.dtype != np.uint8:
                            img = img.astype(np.uint8)
                        images[q] = img
                        logger.info(f"Loaded {q}: {filepath.name}, shape={img.shape}")
                        break
                except Exception as e:
                    logger.warning(f"Failed to load {filepath}: {e}")
    
    return images


def create_detector(method: str, **kwargs) -> cv2.Feature2D:
    """Create feature detector with given parameters."""
    if method == 'orb':
        return cv2.ORB_create(
            nfeatures=kwargs.get('nfeatures', 10000),
            scaleFactor=kwargs.get('scaleFactor', 1.2),
            nlevels=kwargs.get('nlevels', 8),
            edgeThreshold=kwargs.get('edgeThreshold', 31),
            patchSize=kwargs.get('patchSize', 31)
        )
    elif method == 'sift':
        return cv2.SIFT_create(
            nfeatures=kwargs.get('nfeatures', 0),  # 0 = unlimited
            nOctaveLayers=kwargs.get('nOctaveLayers', 3),
            contrastThreshold=kwargs.get('contrastThreshold', 0.02),
            edgeThreshold=kwargs.get('edgeThreshold', 10),
            sigma=kwargs.get('sigma', 1.6)
        )
    elif method == 'akaze':
        return cv2.AKAZE_create(
            threshold=kwargs.get('threshold', 0.0005),
            nOctaves=kwargs.get('nOctaves', 4),
            nOctaveLayers=kwargs.get('nOctaveLayers', 4)
        )
    elif method == 'brisk':
        return cv2.BRISK_create(
            thresh=kwargs.get('thresh', 30),
            octaves=kwargs.get('octaves', 3)
        )
    else:
        raise ValueError(f"Unknown detector: {method}")


def match_features(desc1: np.ndarray, desc2: np.ndarray, 
                   method: str, ratio_thresh: float = 0.75,
                   cross_check: bool = False) -> List:
    """Match features with various strategies."""
    if desc1 is None or desc2 is None:
        return []
    
    # Choose matcher based on descriptor type
    if method in ['orb', 'brisk', 'akaze']:
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=cross_check)
    else:
        matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=cross_check)
    
    if cross_check:
        # Simple cross-check matching
        matches = matcher.match(desc1, desc2)
        return sorted(matches, key=lambda x: x.distance)
    else:
        # kNN matching with ratio test
        matches = matcher.knnMatch(desc1, desc2, k=2)
        good = []
        for m_n in matches:
            if len(m_n) == 2:
                m, n = m_n
                if m.distance < ratio_thresh * n.distance:
                    good.append(m)
        return good


def compute_homography_robust(kp1, kp2, matches, 
                              ransac_thresh: float = 3.0,
                              max_iters: int = 2000) -> Tuple[Optional[np.ndarray], int, float]:
    """
    Compute homography with multiple refinement stages.
    Returns (H, num_inliers, mean_reproj_error).
    """
    if len(matches) < 4:
        return None, 0, float('inf')
    
    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    
    # Stage 1: RANSAC
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 
                                  ransacReprojThreshold=ransac_thresh,
                                  maxIters=max_iters,
                                  confidence=0.999)
    
    if H is None:
        return None, 0, float('inf')
    
    inlier_mask = mask.ravel() == 1
    num_inliers = np.sum(inlier_mask)
    
    if num_inliers < 4:
        return H, num_inliers, float('inf')
    
    # Stage 2: Refine with inliers using LMEDS
    src_inliers = src_pts[inlier_mask]
    dst_inliers = dst_pts[inlier_mask]
    
    H_refined, _ = cv2.findHomography(src_inliers, dst_inliers, cv2.LMEDS)
    if H_refined is not None:
        H = H_refined
    
    # Compute reprojection error
    projected = cv2.perspectiveTransform(src_inliers, H)
    errors = np.sqrt(np.sum((projected - dst_inliers) ** 2, axis=2))
    mean_error = errors.mean()
    
    return H, num_inliers, mean_error


def extract_transform_params(H: np.ndarray) -> Tuple[float, float, float]:
    """Extract translation (dx, dy) and rotation (degrees) from homography."""
    dx = H[0, 2]
    dy = H[1, 2]
    
    # Extract rotation
    cos_theta = (H[0, 0] + H[1, 1]) / 2
    sin_theta = (H[1, 0] - H[0, 1]) / 2
    rotation_rad = np.arctan2(sin_theta, cos_theta)
    rotation_deg = np.degrees(rotation_rad)
    
    return dx, dy, rotation_deg


def phase_correlation_align(img1: np.ndarray, img2: np.ndarray) -> Tuple[float, float, float]:
    """
    Use phase correlation for translation estimation.
    Returns (dx, dy, response).
    """
    # Ensure same size
    h = min(img1.shape[0], img2.shape[0])
    w = min(img1.shape[1], img2.shape[1])
    
    img1_crop = img1[:h, :w].astype(np.float32)
    img2_crop = img2[:h, :w].astype(np.float32)
    
    # Apply window function to reduce edge effects
    window = cv2.createHanningWindow((w, h), cv2.CV_32F)
    img1_win = img1_crop * window
    img2_win = img2_crop * window
    
    # Phase correlation
    (dx, dy), response = cv2.phaseCorrelate(img1_win, img2_win)
    
    return dx, dy, response


def ecc_refine(img_src: np.ndarray, img_dst: np.ndarray, 
               H_initial: np.ndarray, 
               motion_type: int = cv2.MOTION_EUCLIDEAN,
               max_iters: int = 500,
               epsilon: float = 1e-6) -> Tuple[np.ndarray, float]:
    """
    Refine alignment using ECC.
    Returns (H_refined, correlation_coefficient).
    """
    src = img_src.astype(np.float32)
    dst = img_dst.astype(np.float32)
    
    # Normalize
    src = (src - src.mean()) / (src.std() + 1e-8)
    dst = (dst - dst.mean()) / (dst.std() + 1e-8)
    
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, max_iters, epsilon)
    
    try:
        if motion_type == cv2.MOTION_EUCLIDEAN:
            # Extract 2x3 for euclidean
            M = np.eye(2, 3, dtype=np.float32)
            M[0, 2] = H_initial[0, 2]
            M[1, 2] = H_initial[1, 2]
            
            cos_t = (H_initial[0, 0] + H_initial[1, 1]) / 2
            sin_t = (H_initial[1, 0] - H_initial[0, 1]) / 2
            norm = np.sqrt(cos_t**2 + sin_t**2)
            if norm > 0.1:
                cos_t /= norm
                sin_t /= norm
            else:
                cos_t, sin_t = 1.0, 0.0
            
            M[0, 0] = cos_t
            M[0, 1] = -sin_t
            M[1, 0] = sin_t
            M[1, 1] = cos_t
            
            cc, M_refined = cv2.findTransformECC(dst, src, M, motion_type, criteria, 
                                                  inputMask=None, gaussFiltSize=5)
            
            # Convert back to 3x3
            H_refined = np.eye(3, dtype=np.float64)
            H_refined[:2, :] = M_refined
            
        elif motion_type == cv2.MOTION_AFFINE:
            M = H_initial[:2, :].astype(np.float32)
            cc, M_refined = cv2.findTransformECC(dst, src, M, motion_type, criteria,
                                                  inputMask=None, gaussFiltSize=5)
            H_refined = np.eye(3, dtype=np.float64)
            H_refined[:2, :] = M_refined
            
        else:  # MOTION_HOMOGRAPHY
            H = H_initial.astype(np.float32)
            cc, H_refined = cv2.findTransformECC(dst, src, H, motion_type, criteria,
                                                  inputMask=None, gaussFiltSize=5)
            H_refined = H_refined.astype(np.float64)
        
        return H_refined, cc
        
    except cv2.error as e:
        logger.warning(f"ECC failed: {e}")
        return H_initial, 0.0


def try_alignment_method(images: Dict[str, np.ndarray],
                         detector_name: str,
                         detector_params: dict,
                         match_params: dict,
                         ransac_thresh: float,
                         use_ecc: bool = True,
                         ecc_motion: int = cv2.MOTION_EUCLIDEAN) -> AlignmentResult:
    """
    Try a specific alignment configuration.
    """
    method_name = f"{detector_name}_{match_params.get('ratio', 0.75):.2f}_ransac{ransac_thresh:.1f}"
    
    result = AlignmentResult(
        method=method_name,
        params={
            'detector': detector_name,
            'detector_params': detector_params,
            'match_params': match_params,
            'ransac_thresh': ransac_thresh,
            'use_ecc': use_ecc
        },
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    try:
        detector = create_detector(detector_name, **detector_params)
    except Exception as e:
        result.notes = f"Failed to create detector: {e}"
        return result
    
    # Detect features in all images
    features = {}
    for q, img in images.items():
        kp, desc = detector.detectAndCompute(img, None)
        features[q] = (kp, desc)
        logger.debug(f"{q}: detected {len(kp)} keypoints")
    
    # NW is reference
    if 'NW' not in features:
        result.notes = "NW image missing"
        return result
    
    kp_nw, desc_nw = features['NW']
    
    # Compute alignments for each quadrant to NW
    homographies = {}
    
    for q in ['NE', 'SW', 'SE']:
        if q not in features:
            continue
        
        kp_q, desc_q = features[q]
        
        # Match
        matches = match_features(
            desc_q, desc_nw,
            detector_name,
            ratio_thresh=match_params.get('ratio', 0.75),
            cross_check=match_params.get('cross_check', False)
        )
        
        result.total_matches += len(matches)
        
        if len(matches) < 8:
            logger.warning(f"{q}: Only {len(matches)} matches, trying direct neighbors")
            
            # For SE, try via SW or NE
            if q == 'SE':
                # Try SE -> SW -> NW
                if 'SW' in features and 'SW' in homographies:
                    kp_sw, desc_sw = features['SW']
                    matches_se_sw = match_features(desc_q, desc_sw, detector_name,
                                                   ratio_thresh=match_params.get('ratio', 0.75))
                    
                    if len(matches_se_sw) >= 8:
                        H_se_sw, inliers, err = compute_homography_robust(
                            kp_q, kp_sw, matches_se_sw, ransac_thresh
                        )
                        if H_se_sw is not None:
                            H_se_nw = homographies['SW'] @ H_se_sw
                            homographies[q] = H_se_nw
                            result.reprojection_errors[q] = err
                            logger.info(f"{q} via SW: {len(matches_se_sw)} matches, err={err:.3f}")
                            continue
                
                # Try SE -> NE -> NW
                if 'NE' in features and 'NE' in homographies:
                    kp_ne, desc_ne = features['NE']
                    matches_se_ne = match_features(desc_q, desc_ne, detector_name,
                                                   ratio_thresh=match_params.get('ratio', 0.75))
                    
                    if len(matches_se_ne) >= 8:
                        H_se_ne, inliers, err = compute_homography_robust(
                            kp_q, kp_ne, matches_se_ne, ransac_thresh
                        )
                        if H_se_ne is not None:
                            H_se_nw = homographies['NE'] @ H_se_ne
                            homographies[q] = H_se_nw
                            result.reprojection_errors[q] = err
                            logger.info(f"{q} via NE: {len(matches_se_ne)} matches, err={err:.3f}")
                            continue
            
            result.notes += f"{q}: insufficient matches ({len(matches)}); "
            continue
        
        # Compute homography
        H, inliers, err = compute_homography_robust(kp_q, kp_nw, matches, ransac_thresh)
        
        if H is None:
            result.notes += f"{q}: homography failed; "
            continue
        
        homographies[q] = H
        result.reprojection_errors[q] = err
        logger.info(f"{q}: {len(matches)} matches, {inliers} inliers, err={err:.3f}px")
    
    # Apply ECC refinement
    if use_ecc:
        for q in homographies:
            H = homographies[q]
            H_refined, cc = ecc_refine(images[q], images['NW'], H, ecc_motion)
            homographies[q] = H_refined
            logger.info(f"{q} ECC: cc={cc:.4f}")
    
    # Extract final parameters
    for q, H in homographies.items():
        dx, dy, rot = extract_transform_params(H)
        result.translations[q] = (dx, dy)
        result.rotations[q] = rot
    
    result.success = len(homographies) == 3
    
    return result


def run_optimization(images: Dict[str, np.ndarray]) -> List[AlignmentResult]:
    """
    Run multiple alignment configurations and return results.
    """
    results = []
    
    # Configuration space to explore
    configs = [
        # ORB configurations
        {
            'detector': 'orb',
            'detector_params': {'nfeatures': 50000, 'scaleFactor': 1.1, 'nlevels': 12},
            'match_params': {'ratio': 0.8, 'cross_check': False},
            'ransac_thresh': 3.0,
            'use_ecc': True,
            'ecc_motion': cv2.MOTION_EUCLIDEAN
        },
        {
            'detector': 'orb',
            'detector_params': {'nfeatures': 50000, 'scaleFactor': 1.2, 'nlevels': 8},
            'match_params': {'ratio': 0.85, 'cross_check': False},
            'ransac_thresh': 5.0,
            'use_ecc': True,
            'ecc_motion': cv2.MOTION_EUCLIDEAN
        },
        {
            'detector': 'orb',
            'detector_params': {'nfeatures': 30000},
            'match_params': {'ratio': 0.9, 'cross_check': False},
            'ransac_thresh': 5.0,
            'use_ecc': True,
            'ecc_motion': cv2.MOTION_AFFINE
        },
        # SIFT configurations
        {
            'detector': 'sift',
            'detector_params': {'contrastThreshold': 0.01, 'edgeThreshold': 15},
            'match_params': {'ratio': 0.75, 'cross_check': False},
            'ransac_thresh': 3.0,
            'use_ecc': True,
            'ecc_motion': cv2.MOTION_EUCLIDEAN
        },
        {
            'detector': 'sift',
            'detector_params': {'contrastThreshold': 0.005, 'edgeThreshold': 20},
            'match_params': {'ratio': 0.8, 'cross_check': False},
            'ransac_thresh': 5.0,
            'use_ecc': True,
            'ecc_motion': cv2.MOTION_EUCLIDEAN
        },
        # AKAZE configurations
        {
            'detector': 'akaze',
            'detector_params': {'threshold': 0.0003},
            'match_params': {'ratio': 0.8, 'cross_check': False},
            'ransac_thresh': 3.0,
            'use_ecc': True,
            'ecc_motion': cv2.MOTION_EUCLIDEAN
        },
        {
            'detector': 'akaze',
            'detector_params': {'threshold': 0.0001},
            'match_params': {'ratio': 0.85, 'cross_check': False},
            'ransac_thresh': 5.0,
            'use_ecc': True,
            'ecc_motion': cv2.MOTION_AFFINE
        },
        # BRISK configuration
        {
            'detector': 'brisk',
            'detector_params': {'thresh': 20, 'octaves': 4},
            'match_params': {'ratio': 0.8, 'cross_check': False},
            'ransac_thresh': 5.0,
            'use_ecc': True,
            'ecc_motion': cv2.MOTION_EUCLIDEAN
        },
        # Cross-check configurations (no ratio test)
        {
            'detector': 'orb',
            'detector_params': {'nfeatures': 50000},
            'match_params': {'cross_check': True},
            'ransac_thresh': 5.0,
            'use_ecc': True,
            'ecc_motion': cv2.MOTION_EUCLIDEAN
        },
        {
            'detector': 'sift',
            'detector_params': {'contrastThreshold': 0.01},
            'match_params': {'cross_check': True},
            'ransac_thresh': 3.0,
            'use_ecc': True,
            'ecc_motion': cv2.MOTION_EUCLIDEAN
        },
    ]
    
    for i, cfg in enumerate(configs):
        logger.info(f"\n{'='*60}")
        logger.info(f"Configuration {i+1}/{len(configs)}: {cfg['detector']} with {cfg['match_params']}")
        logger.info(f"{'='*60}")
        
        result = try_alignment_method(
            images,
            cfg['detector'],
            cfg['detector_params'],
            cfg['match_params'],
            cfg['ransac_thresh'],
            cfg['use_ecc'],
            cfg['ecc_motion']
        )
        
        results.append(result)
        
        # Print summary
        if result.success:
            logger.info(f"✓ SUCCESS: {result.method}")
            for q in ['NE', 'SW', 'SE']:
                if q in result.translations:
                    dx, dy = result.translations[q]
                    rot = result.rotations[q]
                    err = result.reprojection_errors.get(q, float('nan'))
                    logger.info(f"  {q}: dx={dx:+.2f}, dy={dy:+.2f}, rot={rot:+.2f}°, err={err:.3f}px")
        else:
            logger.info(f"✗ FAILED: {result.method} - {result.notes}")
    
    return results


def try_grid_constrained_alignment(images: Dict[str, np.ndarray],
                                    expected_overlap_percent: float = 30.0,
                                    search_range: int = 50) -> AlignmentResult:
    """
    Use expected grid geometry as prior, then refine with normalized cross-correlation.
    Assumes quadrants are arranged in a 2x2 grid with uniform overlap.
    """
    logger.info("\n" + "="*60)
    logger.info(f"Trying GRID-CONSTRAINED ALIGNMENT (overlap={expected_overlap_percent}%, search=±{search_range}px)")
    logger.info("="*60)
    
    result = AlignmentResult(
        method=f"grid_constrained_{expected_overlap_percent:.0f}_{search_range}",
        params={'overlap_percent': expected_overlap_percent, 'search_range': search_range},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    h, w = ref.shape
    expected_shift = int(w * (100 - expected_overlap_percent) / 100)
    
    logger.info(f"Expected shift based on {expected_overlap_percent}% overlap: {expected_shift}px")
    
    def find_best_shift_ncc(img_ref: np.ndarray, img_target: np.ndarray,
                            expected_dx: int, expected_dy: int,
                            search_range: int) -> Tuple[int, int, float]:
        """Find best shift using normalized cross-correlation in a local window."""
        best_dx, best_dy = expected_dx, expected_dy
        best_score = -1
        
        # Create search window
        for dy in range(-search_range, search_range + 1, 2):
            for dx in range(-search_range, search_range + 1, 2):
                test_dx = expected_dx + dx
                test_dy = expected_dy + dy
                
                # Compute overlap region
                if test_dx >= 0:
                    ref_x1, ref_x2 = test_dx, w
                    tgt_x1, tgt_x2 = 0, w - test_dx
                else:
                    ref_x1, ref_x2 = 0, w + test_dx
                    tgt_x1, tgt_x2 = -test_dx, w
                
                if test_dy >= 0:
                    ref_y1, ref_y2 = test_dy, h
                    tgt_y1, tgt_y2 = 0, h - test_dy
                else:
                    ref_y1, ref_y2 = 0, h + test_dy
                    tgt_y1, tgt_y2 = -test_dy, h
                
                if ref_x2 <= ref_x1 or ref_y2 <= ref_y1:
                    continue
                
                # Extract overlap regions
                ref_crop = img_ref[ref_y1:ref_y2, ref_x1:ref_x2].astype(np.float64)
                tgt_crop = img_target[tgt_y1:tgt_y2, tgt_x1:tgt_x2].astype(np.float64)
                
                if ref_crop.size == 0 or tgt_crop.size == 0:
                    continue
                
                # Normalized cross-correlation
                ref_norm = (ref_crop - ref_crop.mean()) / (ref_crop.std() + 1e-8)
                tgt_norm = (tgt_crop - tgt_crop.mean()) / (tgt_crop.std() + 1e-8)
                
                ncc = np.mean(ref_norm * tgt_norm)
                
                if ncc > best_score:
                    best_score = ncc
                    best_dx = test_dx
                    best_dy = test_dy
        
        return best_dx, best_dy, best_score
    
    # NE: expected to be to the right of NW
    if 'NE' in images:
        ne = images['NE']
        dx, dy, score = find_best_shift_ncc(ref, ne, expected_shift, 0, search_range)
        result.translations['NE'] = (float(dx), float(dy))
        result.rotations['NE'] = 0.0
        result.reprojection_errors['NE'] = 1.0 - score
        logger.info(f"NE: dx={dx}, dy={dy}, NCC={score:.4f}")
    
    # SW: expected to be below NW
    if 'SW' in images:
        sw = images['SW']
        dx, dy, score = find_best_shift_ncc(ref, sw, 0, expected_shift, search_range)
        result.translations['SW'] = (float(dx), float(dy))
        result.rotations['SW'] = 0.0
        result.reprojection_errors['SW'] = 1.0 - score
        logger.info(f"SW: dx={dx}, dy={dy}, NCC={score:.4f}")
    
    # SE: expected to be at (NE_x, SW_y)
    if 'SE' in images and 'NE' in result.translations and 'SW' in result.translations:
        se = images['SE']
        expected_se_dx = int(result.translations['NE'][0])
        expected_se_dy = int(result.translations['SW'][1])
        
        dx, dy, score = find_best_shift_ncc(ref, se, expected_se_dx, expected_se_dy, search_range)
        result.translations['SE'] = (float(dx), float(dy))
        result.rotations['SE'] = 0.0
        result.reprojection_errors['SE'] = 1.0 - score
        logger.info(f"SE: dx={dx}, dy={dy}, NCC={score:.4f}")
    
    result.success = len(result.translations) == 3
    return result


def try_skimage_phase_correlation(images: Dict[str, np.ndarray], 
                                    upsample_factor: int = 100) -> AlignmentResult:
    """
    Use scikit-image phase_cross_correlation for sub-pixel accurate translation.
    
    phase_cross_correlation provides sub-pixel accuracy via upsampling in Fourier space.
    upsample_factor=100 gives 0.01 pixel accuracy.
    """
    if not SKIMAGE_AVAILABLE:
        return AlignmentResult(
            method="skimage_phase_correlation",
            params={},
            translations={},
            rotations={},
            reprojection_errors={},
            total_matches=0,
            success=False,
            notes="scikit-image not available"
        )
    
    logger.info("\n" + "="*60)
    logger.info(f"Trying SKIMAGE PHASE CORRELATION (upsample={upsample_factor}x)")
    logger.info("="*60)
    
    result = AlignmentResult(
        method=f"skimage_phase_{upsample_factor}",
        params={'upsample_factor': upsample_factor},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    # Normalize reference
    ref_float = ref.astype(np.float64)
    ref_float = (ref_float - ref_float.mean()) / (ref_float.std() + 1e-8)
    
    for q in ['NE', 'SW', 'SE']:
        if q not in images:
            continue
        
        img = images[q].astype(np.float64)
        img = (img - img.mean()) / (img.std() + 1e-8)
        
        # Phase cross-correlation with sub-pixel accuracy
        shift, error, diffphase = phase_cross_correlation(
            ref_float, img,
            upsample_factor=upsample_factor,
            normalization=None  # Already normalized
        )
        
        # shift is (dy, dx) in numpy convention
        dy, dx = shift
        
        result.translations[q] = (float(dx), float(dy))
        result.rotations[q] = 0.0  # Phase correlation doesn't detect rotation
        result.reprojection_errors[q] = float(error)
        
        logger.info(f"{q}: dx={dx:.4f}, dy={dy:.4f}, error={error:.6f}")
    
    result.success = len(result.translations) == 3
    return result


def try_skimage_masked_registration(images: Dict[str, np.ndarray],
                                     overlap_percent: float = 70.0) -> AlignmentResult:
    """
    Use scikit-image phase correlation on overlap regions only.
    More robust for images with different content outside overlap.
    """
    if not SKIMAGE_AVAILABLE:
        return AlignmentResult(
            method="skimage_masked",
            params={},
            translations={},
            rotations={},
            reprojection_errors={},
            total_matches=0,
            success=False,
            notes="scikit-image not available"
        )
    
    logger.info("\n" + "="*60)
    logger.info(f"Trying SKIMAGE MASKED REGISTRATION (overlap={overlap_percent}%)")
    logger.info("="*60)
    
    result = AlignmentResult(
        method=f"skimage_masked_{overlap_percent:.0f}",
        params={'overlap_percent': overlap_percent},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    h, w = ref.shape
    overlap_px = int(w * overlap_percent / 100)
    expected_shift = w - overlap_px
    
    # NE alignment: overlap on right edge of NW, left edge of NE
    if 'NE' in images:
        ne = images['NE']
        
        # Take overlap regions
        ref_overlap = ref[:, -overlap_px:].astype(np.float64)
        ne_overlap = ne[:, :overlap_px].astype(np.float64)
        
        # Normalize
        ref_overlap = (ref_overlap - ref_overlap.mean()) / (ref_overlap.std() + 1e-8)
        ne_overlap = (ne_overlap - ne_overlap.mean()) / (ne_overlap.std() + 1e-8)
        
        shift, error, _ = phase_cross_correlation(
            ref_overlap, ne_overlap,
            upsample_factor=100
        )
        
        # Convert to full-image coordinates
        dy, dx = shift
        full_dx = expected_shift - dx  # NE is to the right
        full_dy = -dy
        
        result.translations['NE'] = (float(full_dx), float(full_dy))
        result.rotations['NE'] = 0.0
        result.reprojection_errors['NE'] = float(error)
        logger.info(f"NE: dx={full_dx:.2f}, dy={full_dy:.2f}, error={error:.6f}")
    
    # SW alignment: overlap on bottom edge of NW, top edge of SW
    if 'SW' in images:
        sw = images['SW']
        
        ref_overlap = ref[-overlap_px:, :].astype(np.float64)
        sw_overlap = sw[:overlap_px, :].astype(np.float64)
        
        ref_overlap = (ref_overlap - ref_overlap.mean()) / (ref_overlap.std() + 1e-8)
        sw_overlap = (sw_overlap - sw_overlap.mean()) / (sw_overlap.std() + 1e-8)
        
        shift, error, _ = phase_cross_correlation(
            ref_overlap, sw_overlap,
            upsample_factor=100
        )
        
        dy, dx = shift
        full_dx = -dx
        full_dy = expected_shift - dy
        
        result.translations['SW'] = (float(full_dx), float(full_dy))
        result.rotations['SW'] = 0.0
        result.reprojection_errors['SW'] = float(error)
        logger.info(f"SW: dx={full_dx:.2f}, dy={full_dy:.2f}, error={error:.6f}")
    
    # SE alignment: expected at (NE_x, SW_y)
    if 'SE' in images and 'NE' in result.translations and 'SW' in result.translations:
        se = images['SE']
        ne = images['NE']
        
        # Align SE to NE (SE is below NE)
        ne_overlap = ne[-overlap_px:, :].astype(np.float64)
        se_overlap = se[:overlap_px, :].astype(np.float64)
        
        ne_overlap = (ne_overlap - ne_overlap.mean()) / (ne_overlap.std() + 1e-8)
        se_overlap = (se_overlap - se_overlap.mean()) / (se_overlap.std() + 1e-8)
        
        shift, error, _ = phase_cross_correlation(
            ne_overlap, se_overlap,
            upsample_factor=100
        )
        
        dy, dx = shift
        # SE position relative to NW = NE position + (SE relative to NE)
        ne_dx, ne_dy = result.translations['NE']
        full_dx = ne_dx - dx
        full_dy = ne_dy + expected_shift - dy
        
        result.translations['SE'] = (float(full_dx), float(full_dy))
        result.rotations['SE'] = 0.0
        result.reprojection_errors['SE'] = float(error)
        logger.info(f"SE: dx={full_dx:.2f}, dy={full_dy:.2f}, error={error:.6f}")
    
    result.success = len(result.translations) == 3
    return result


def try_skimage_orb_registration(images: Dict[str, np.ndarray]) -> AlignmentResult:
    """
    Use scikit-image ORB feature detector with RANSAC for robust registration.
    """
    if not SKIMAGE_AVAILABLE:
        return AlignmentResult(
            method="skimage_orb",
            params={},
            translations={},
            rotations={},
            reprojection_errors={},
            total_matches=0,
            success=False,
            notes="scikit-image not available"
        )
    
    logger.info("\n" + "="*60)
    logger.info("Trying SKIMAGE ORB + RANSAC")
    logger.info("="*60)
    
    result = AlignmentResult(
        method="skimage_orb_ransac",
        params={},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    # Create ORB detector
    orb = SkimageORB(n_keypoints=5000, fast_threshold=0.05)
    
    # Detect in reference
    orb.detect_and_extract(ref)
    kp_ref = orb.keypoints
    desc_ref = orb.descriptors
    
    for q in ['NE', 'SW', 'SE']:
        if q not in images:
            continue
        
        img = images[q]
        
        try:
            orb.detect_and_extract(img)
            kp_img = orb.keypoints
            desc_img = orb.descriptors
            
            if desc_ref is None or desc_img is None:
                logger.warning(f"{q}: No descriptors found")
                continue
            
            # Match descriptors
            matches = match_descriptors(desc_ref, desc_img, cross_check=True)
            
            if len(matches) < 4:
                logger.warning(f"{q}: Only {len(matches)} matches")
                continue
            
            result.total_matches += len(matches)
            
            # Get matched keypoints
            src = kp_img[matches[:, 1]]  # Image keypoints (source)
            dst = kp_ref[matches[:, 0]]  # Reference keypoints (destination)
            
            # RANSAC with Euclidean transform (rotation + translation)
            model, inliers = ransac(
                (src, dst),
                EuclideanTransform,
                min_samples=3,
                residual_threshold=2.0,
                max_trials=1000
            )
            
            if model is not None:
                # Extract translation and rotation
                dx = model.translation[0]
                dy = model.translation[1]
                rotation = np.degrees(model.rotation)
                
                result.translations[q] = (float(dx), float(dy))
                result.rotations[q] = float(rotation)
                
                # Compute reprojection error
                src_transformed = model(src)
                errors = np.sqrt(np.sum((src_transformed - dst) ** 2, axis=1))
                result.reprojection_errors[q] = float(errors.mean())
                
                logger.info(
                    f"{q}: {len(matches)} matches, {np.sum(inliers)} inliers, "
                    f"dx={dx:.2f}, dy={dy:.2f}, rot={rotation:.2f}°, err={errors.mean():.3f}px"
                )
            else:
                logger.warning(f"{q}: RANSAC failed")
                
        except Exception as e:
            logger.warning(f"{q}: Error - {e}")
    
    result.success = len(result.translations) == 3
    return result


def try_skimage_direct_to_nw(images: Dict[str, np.ndarray], 
                              max_zoom_percent: float = 5.0,
                              target_correlation: float = 0.9,
                              max_iterations: int = 5) -> AlignmentResult:
    """
    All quadrants align directly to NW with iterative refinement.
    
    Continues refining until correlation > target_correlation or max_iterations reached.
    Uses multi-scale approach for robust alignment.
    """
    if not SKIMAGE_AVAILABLE:
        return AlignmentResult(
            method="skimage_direct_nw",
            params={'max_zoom_percent': max_zoom_percent, 'target_correlation': target_correlation},
            translations={},
            rotations={},
            reprojection_errors={},
            total_matches=0,
            success=False,
            notes="scikit-image not available"
        )
    
    logger.info("\n" + "="*60)
    logger.info(f"Trying SKIMAGE DIRECT TO NW (target corr > {target_correlation})")
    logger.info("="*60)
    
    result = AlignmentResult(
        method=f"skimage_direct_nw_{target_correlation}",
        params={'max_zoom_percent': max_zoom_percent, 'target_correlation': target_correlation},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    h, w = ref.shape
    
    # Scale search range
    if max_zoom_percent > 0:
        scale_range = np.linspace(1.0 - max_zoom_percent/100, 1.0 + max_zoom_percent/100, 21)
    else:
        scale_range = [1.0]
    
    def align_with_refinement(img: np.ndarray, ref_img: np.ndarray, name: str):
        """Align image to reference with iterative refinement."""
        
        # Multi-scale pyramid for robust initial alignment
        scales_pyramid = [0.25, 0.5, 1.0]
        
        best_dx, best_dy = 0.0, 0.0
        best_scale = 1.0
        best_corr = -float('inf')
        
        # Start with coarse scale for robust initial estimate
        for pyramid_scale in scales_pyramid:
            if pyramid_scale < 1.0:
                ref_small = cv2.resize(ref_img, None, fx=pyramid_scale, fy=pyramid_scale, 
                                       interpolation=cv2.INTER_AREA)
                img_small = cv2.resize(img, None, fx=pyramid_scale, fy=pyramid_scale,
                                       interpolation=cv2.INTER_AREA)
            else:
                ref_small = ref_img
                img_small = img
            
            # Normalize
            ref_norm = ref_small.astype(np.float64)
            ref_norm = (ref_norm - ref_norm.mean()) / (ref_norm.std() + 1e-8)
            img_norm = img_small.astype(np.float64)
            img_norm = (img_norm - img_norm.mean()) / (img_norm.std() + 1e-8)
            
            # Phase correlation
            shift, corr, _ = phase_cross_correlation(ref_norm, img_norm, upsample_factor=100)
            dy, dx = shift
            
            # Scale back to original size
            dx = dx / pyramid_scale
            dy = dy / pyramid_scale
            
            if corr > best_corr:
                best_corr = corr
                best_dx, best_dy = dx, dy
        
        logger.debug(f"{name}: initial dx={best_dx:.2f}, dy={best_dy:.2f}, corr={best_corr:.4f}")
        
        # Iterative refinement with zoom search
        for iteration in range(max_iterations):
            if best_corr >= target_correlation:
                logger.info(f"{name}: target correlation {target_correlation} reached at iteration {iteration}")
                break
            
            # Search for best scale
            current_best_corr = best_corr
            current_best_scale = best_scale
            current_best_dx = best_dx
            current_best_dy = best_dy
            
            for scale in scale_range:
                # Apply scale to image
                if abs(scale - 1.0) > 0.001:
                    new_w, new_h = int(w * scale), int(h * scale)
                    img_scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                    # Crop/pad to original size
                    if new_w >= w and new_h >= h:
                        start_x, start_y = (new_w - w) // 2, (new_h - h) // 2
                        img_test = img_scaled[start_y:start_y+h, start_x:start_x+w]
                    else:
                        img_test = np.zeros((h, w), dtype=img_scaled.dtype)
                        paste_x = (w - new_w) // 2
                        paste_y = (h - new_h) // 2
                        img_test[paste_y:paste_y+new_h, paste_x:paste_x+new_w] = img_scaled
                else:
                    img_test = img
                
                # Normalize
                ref_norm = ref_img.astype(np.float64)
                ref_norm = (ref_norm - ref_norm.mean()) / (ref_norm.std() + 1e-8)
                img_norm = img_test.astype(np.float64)
                img_norm = (img_norm - img_norm.mean()) / (img_norm.std() + 1e-8)
                
                # Phase correlation with high precision
                shift, corr, _ = phase_cross_correlation(ref_norm, img_norm, upsample_factor=1000)
                dy, dx = shift
                
                if corr > current_best_corr:
                    current_best_corr = corr
                    current_best_scale = scale
                    current_best_dx = dx
                    current_best_dy = dy
            
            # Update best values
            if current_best_corr > best_corr:
                best_corr = current_best_corr
                best_scale = current_best_scale
                best_dx = current_best_dx
                best_dy = current_best_dy
                logger.debug(f"{name} iter {iteration}: improved to corr={best_corr:.4f}, scale={best_scale:.4f}")
            else:
                # No improvement, try finer scale search around current best
                fine_scale_range = np.linspace(best_scale - 0.01, best_scale + 0.01, 11)
                for scale in fine_scale_range:
                    if scale <= 0:
                        continue
                    new_w, new_h = int(w * scale), int(h * scale)
                    if new_w <= 0 or new_h <= 0:
                        continue
                    img_scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                    if new_w >= w and new_h >= h:
                        start_x, start_y = (new_w - w) // 2, (new_h - h) // 2
                        img_test = img_scaled[start_y:start_y+h, start_x:start_x+w]
                    else:
                        img_test = np.zeros((h, w), dtype=img_scaled.dtype)
                        paste_x = (w - new_w) // 2
                        paste_y = (h - new_h) // 2
                        if paste_x >= 0 and paste_y >= 0:
                            img_test[paste_y:paste_y+new_h, paste_x:paste_x+new_w] = img_scaled
                    
                    ref_norm = ref_img.astype(np.float64)
                    ref_norm = (ref_norm - ref_norm.mean()) / (ref_norm.std() + 1e-8)
                    img_norm = img_test.astype(np.float64)
                    img_norm = (img_norm - img_norm.mean()) / (img_norm.std() + 1e-8)
                    
                    shift, corr, _ = phase_cross_correlation(ref_norm, img_norm, upsample_factor=1000)
                    dy, dx = shift
                    
                    if corr > best_corr:
                        best_corr = corr
                        best_scale = scale
                        best_dx = dx
                        best_dy = dy
                
                if best_corr >= target_correlation:
                    break
        
        scale_pct = (best_scale - 1.0) * 100
        logger.info(f"{name}: dx={best_dx:.4f}, dy={best_dy:.4f}, scale={best_scale:.4f} ({scale_pct:+.2f}%), corr={best_corr:.4f}")
        
        return best_dx, best_dy, best_scale, best_corr
    
    # Align NE and SW directly to NW (they overlap with NW)
    for q in ['NE', 'SW']:
        if q not in images:
            continue
        
        dx, dy, scale, corr = align_with_refinement(images[q], ref, q)
        
        result.translations[q] = (float(dx), float(dy))
        result.rotations[q] = 0.0
        result.reprojection_errors[q] = 1.0 - float(corr)
        
        if not result.notes:
            result.notes = ""
        result.notes += f"{q}: scale={scale:.4f}; "
    
    # SE: Chain through NE (SE doesn't directly overlap with NW)
    if 'SE' in images and 'NE' in result.translations:
        ne_img = images['NE']
        se_img = images['SE']
        
        # Normalize NE as reference for SE alignment
        ne_float = ne_img.astype(np.float64)
        ne_float = (ne_float - ne_float.mean()) / (ne_float.std() + 1e-8)
        
        # Align SE to NE
        dx_rel, dy_rel, scale_se, corr_se = align_with_refinement(se_img, ne_float, "SE_via_NE")
        
        # SE position = NE position + relative shift
        ne_dx, ne_dy = result.translations['NE']
        se_dx = ne_dx + dx_rel
        se_dy = ne_dy + dy_rel
        
        # Cross-validate with SW path
        if 'SW' in result.translations:
            sw_img = images['SW']
            sw_float = sw_img.astype(np.float64)
            sw_float = (sw_float - sw_float.mean()) / (sw_float.std() + 1e-8)
            
            dx_rel2, dy_rel2, _, corr_sw = align_with_refinement(se_img, sw_float, "SE_via_SW")
            
            sw_dx, sw_dy = result.translations['SW']
            se_dx2 = sw_dx + dx_rel2
            se_dy2 = sw_dy + dy_rel2
            
            # Check consistency: SE should be at approximately (NE_x, SW_y)
            consistency_ne = abs(se_dx - ne_dx) + abs(se_dy - sw_dy)
            consistency_sw = abs(se_dx2 - ne_dx) + abs(se_dy2 - sw_dy)
            
            logger.info(f"SE consistency: via NE={consistency_ne:.2f}, via SW={consistency_sw:.2f}")
            
            if consistency_sw < consistency_ne * 0.7:
                # SW path is significantly better
                se_dx, se_dy = se_dx2, se_dy2
                logger.info(f"SE: using SW path (more consistent)")
            elif consistency_ne < consistency_sw * 0.7:
                # NE path is significantly better (already have correct values)
                logger.info(f"SE: using NE path (more consistent)")
            else:
                # Average both paths with weights
                weight_ne = 1.0 / (consistency_ne + 1)
                weight_sw = 1.0 / (consistency_sw + 1)
                total_weight = weight_ne + weight_sw
                se_dx = (se_dx * weight_ne + se_dx2 * weight_sw) / total_weight
                se_dy = (se_dy * weight_ne + se_dy2 * weight_sw) / total_weight
                logger.info(f"SE: averaged from both paths")
        
        result.translations['SE'] = (float(se_dx), float(se_dy))
        result.rotations['SE'] = 0.0
        result.reprojection_errors['SE'] = 1.0 - float(corr_se)
        result.notes += f"SE: scale={scale_se:.4f}; "
        
        logger.info(f"SE final: dx={se_dx:.4f}, dy={se_dy:.4f}, scale={scale_se:.4f}, corr={corr_se:.4f}")
    
    result.success = len(result.translations) == 3
    result.total_matches = 4
    
    return result


def try_skimage_with_zoom(images: Dict[str, np.ndarray], max_zoom_percent: float = 5.0) -> AlignmentResult:
    """
    Scikit-image registration with zoom/scale search.
    
    Searches for optimal scale within ±max_zoom_percent for each quadrant.
    """
    if not SKIMAGE_AVAILABLE:
        return AlignmentResult(
            method=f"skimage_zoom_{max_zoom_percent:.0f}",
            params={'max_zoom_percent': max_zoom_percent},
            translations={},
            rotations={},
            reprojection_errors={},
            total_matches=0,
            success=False,
            notes="scikit-image not available"
        )
    
    logger.info("\n" + "="*60)
    logger.info(f"Trying SKIMAGE WITH ZOOM SEARCH (±{max_zoom_percent}%)")
    logger.info("="*60)
    
    result = AlignmentResult(
        method=f"skimage_zoom_{max_zoom_percent:.0f}",
        params={'max_zoom_percent': max_zoom_percent},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    h, w = ref.shape
    
    # Scale search range
    scale_range = np.linspace(1.0 - max_zoom_percent/100, 1.0 + max_zoom_percent/100, 11)
    
    # Normalize reference
    ref_float = ref.astype(np.float64)
    ref_float = (ref_float - ref_float.mean()) / (ref_float.std() + 1e-8)
    
    def find_best_scale_and_shift(img: np.ndarray, ref_norm: np.ndarray):
        """Find optimal scale and translation."""
        best_scale = 1.0
        best_dx, best_dy = 0.0, 0.0
        best_corr = -float('inf')
        
        for scale in scale_range:
            if abs(scale - 1.0) > 0.001:
                new_w, new_h = int(w * scale), int(h * scale)
                img_scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                # Crop/pad to original size
                if new_w >= w and new_h >= h:
                    start_x, start_y = (new_w - w) // 2, (new_h - h) // 2
                    img_test = img_scaled[start_y:start_y+h, start_x:start_x+w]
                else:
                    img_test = np.zeros((h, w), dtype=img_scaled.dtype)
                    paste_x = (w - new_w) // 2
                    paste_y = (h - new_h) // 2
                    img_test[paste_y:paste_y+new_h, paste_x:paste_x+new_w] = img_scaled
            else:
                img_test = img
            
            img_norm = img_test.astype(np.float64)
            img_norm = (img_norm - img_norm.mean()) / (img_norm.std() + 1e-8)
            
            shift, corr, _ = phase_cross_correlation(ref_norm, img_norm, upsample_factor=100)
            
            if corr > best_corr:
                best_corr = corr
                best_scale = scale
                best_dy, best_dx = shift
        
        return best_dx, best_dy, best_scale, best_corr
    
    # Process each quadrant
    for q in ['NE', 'SW', 'SE']:
        if q not in images:
            continue
        
        dx, dy, scale, corr = find_best_scale_and_shift(images[q], ref_float)
        
        result.translations[q] = (float(dx), float(dy))
        result.rotations[q] = 0.0
        result.reprojection_errors[q] = 1.0 - float(corr)  # Convert correlation to error
        
        scale_pct = (scale - 1.0) * 100
        logger.info(f"{q}: dx={dx:.4f}, dy={dy:.4f}, scale={scale:.4f} ({scale_pct:+.2f}%), corr={corr:.4f}")
    
    result.success = len(result.translations) == 3
    return result


def try_skimage_chained_registration(images: Dict[str, np.ndarray]) -> AlignmentResult:
    """
    Best scikit-image approach: 
    - Use phase_cross_correlation for NE and SW (direct overlap with NW)
    - Compute SE via chaining through NE or SW
    """
    if not SKIMAGE_AVAILABLE:
        return AlignmentResult(
            method="skimage_chained",
            params={},
            translations={},
            rotations={},
            reprojection_errors={},
            total_matches=0,
            success=False,
            notes="scikit-image not available"
        )
    
    logger.info("\n" + "="*60)
    logger.info("Trying SKIMAGE CHAINED REGISTRATION (best method)")
    logger.info("="*60)
    
    result = AlignmentResult(
        method="skimage_chained",
        params={},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    h, w = ref.shape
    
    # Normalize reference
    ref_float = ref.astype(np.float64)
    ref_float = (ref_float - ref_float.mean()) / (ref_float.std() + 1e-8)
    
    # NE: direct phase correlation with NW (high upsample for sub-pixel)
    if 'NE' in images:
        ne = images['NE'].astype(np.float64)
        ne = (ne - ne.mean()) / (ne.std() + 1e-8)
        
        shift, error, _ = phase_cross_correlation(ref_float, ne, upsample_factor=100)
        dy, dx = shift
        
        result.translations['NE'] = (float(dx), float(dy))
        result.rotations['NE'] = 0.0
        result.reprojection_errors['NE'] = float(error)
        logger.info(f"NE (direct): dx={dx:.4f}, dy={dy:.4f}")
    
    # SW: direct phase correlation with NW
    if 'SW' in images:
        sw = images['SW'].astype(np.float64)
        sw = (sw - sw.mean()) / (sw.std() + 1e-8)
        
        shift, error, _ = phase_cross_correlation(ref_float, sw, upsample_factor=100)
        dy, dx = shift
        
        result.translations['SW'] = (float(dx), float(dy))
        result.rotations['SW'] = 0.0
        result.reprojection_errors['SW'] = float(error)
        logger.info(f"SW (direct): dx={dx:.4f}, dy={dy:.4f}")
    
        # SE: chain through NE (SE is below NE) - this is more reliable
    if 'SE' in images and 'NE' in result.translations:
        se = images['SE'].astype(np.float64)
        se = (se - se.mean()) / (se.std() + 1e-8)
        
        ne = images['NE'].astype(np.float64)
        ne = (ne - ne.mean()) / (ne.std() + 1e-8)
        
        # SE relative to NE
        shift_se_ne, error, _ = phase_cross_correlation(ne, se, upsample_factor=100)
        dy_rel, dx_rel = shift_se_ne
        
        # SE position = NE position + relative shift
        ne_dx, ne_dy = result.translations['NE']
        se_dx_via_ne = ne_dx + dx_rel
        se_dy_via_ne = ne_dy + dy_rel
        
        logger.info(f"SE relative to NE: dx_rel={dx_rel:.4f}, dy_rel={dy_rel:.4f}")
        logger.info(f"SE via NE: ({se_dx_via_ne:.2f}, {se_dy_via_ne:.2f})")
        
        # Also try SE relative to SW for cross-validation
        se_dx_via_sw, se_dy_via_sw = None, None
        if 'SW' in result.translations:
            sw = images['SW'].astype(np.float64)
            sw = (sw - sw.mean()) / (sw.std() + 1e-8)
            
            shift_se_sw, _, _ = phase_cross_correlation(sw, se, upsample_factor=100)
            dy_rel2, dx_rel2 = shift_se_sw
            
            sw_dx, sw_dy = result.translations['SW']
            se_dx_via_sw = sw_dx + dx_rel2
            se_dy_via_sw = sw_dy + dy_rel2
            
            logger.info(f"SE relative to SW: dx_rel={dx_rel2:.4f}, dy_rel={dy_rel2:.4f}")
            logger.info(f"SE via SW: ({se_dx_via_sw:.2f}, {se_dy_via_sw:.2f})")
        
        # Check consistency: SE should be at approximately (NE_x, SW_y)
        # Use the estimate that is more consistent
        sw_dy_expected = result.translations['SW'][1] if 'SW' in result.translations else se_dy_via_ne
        
        # SE via NE is generally more reliable for these images
        # Only average if both estimates are geometrically consistent
        if se_dx_via_sw is not None:
            consistency_ne = abs(se_dx_via_ne - ne_dx) + abs(se_dy_via_ne - sw_dy_expected)
            consistency_sw = abs(se_dx_via_sw - ne_dx) + abs(se_dy_via_sw - sw_dy_expected)
            
            logger.info(f"Consistency: via NE={consistency_ne:.2f}, via SW={consistency_sw:.2f}")
            
            if consistency_sw < consistency_ne * 2:
                # Both are reasonably consistent, average them with weights
                weight_ne = 1.0 / (consistency_ne + 1)
                weight_sw = 1.0 / (consistency_sw + 1)
                total_weight = weight_ne + weight_sw
                
                se_dx = (se_dx_via_ne * weight_ne + se_dx_via_sw * weight_sw) / total_weight
                se_dy = (se_dy_via_ne * weight_ne + se_dy_via_sw * weight_sw) / total_weight
                logger.info(f"SE weighted average: ({se_dx:.2f}, {se_dy:.2f})")
            else:
                # SW path is much worse, use NE path only
                se_dx, se_dy = se_dx_via_ne, se_dy_via_ne
                logger.info(f"SE using NE path only (SW inconsistent): ({se_dx:.2f}, {se_dy:.2f})")
        else:
            se_dx, se_dy = se_dx_via_ne, se_dy_via_ne
        
        result.translations['SE'] = (float(se_dx), float(se_dy))
        result.rotations['SE'] = 0.0
        result.reprojection_errors['SE'] = float(error)
    
    result.success = len(result.translations) == 3
    return result


def try_skimage_iterative_registration(images: Dict[str, np.ndarray],
                                        num_iterations: int = 3) -> AlignmentResult:
    """
    Iterative registration: phase correlation -> warp -> refine.
    Each iteration refines the alignment.
    """
    if not SKIMAGE_AVAILABLE:
        return AlignmentResult(
            method="skimage_iterative",
            params={},
            translations={},
            rotations={},
            reprojection_errors={},
            total_matches=0,
            success=False,
            notes="scikit-image not available"
        )
    
    logger.info("\n" + "="*60)
    logger.info(f"Trying SKIMAGE ITERATIVE REGISTRATION ({num_iterations} iterations)")
    logger.info("="*60)
    
    result = AlignmentResult(
        method=f"skimage_iterative_{num_iterations}",
        params={'num_iterations': num_iterations},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    h, w = ref.shape
    
    # Initial estimate from expected 70% overlap
    expected_shift = int(w * 0.30)  # 30% non-overlap = 70% overlap
    initial_estimates = {
        'NE': (expected_shift, 0),
        'SW': (0, expected_shift),
        'SE': (expected_shift, expected_shift)
    }
    
    ref_float = ref.astype(np.float64)
    
    for q in ['NE', 'SW', 'SE']:
        if q not in images:
            continue
        
        img = images[q].astype(np.float64)
        
        # Initialize with expected position
        dx, dy = initial_estimates[q]
        
        for iteration in range(num_iterations):
            # Create shifted version of image
            transform = EuclideanTransform(translation=(-dx, -dy))
            img_warped = warp(img, transform.inverse, output_shape=(h, w), 
                             preserve_range=True)
            
            # Normalize for correlation
            ref_norm = (ref_float - ref_float.mean()) / (ref_float.std() + 1e-8)
            img_norm = (img_warped - img_warped.mean()) / (img_warped.std() + 1e-8)
            
            # Phase correlation for residual shift
            shift, error, _ = phase_cross_correlation(
                ref_norm, img_norm,
                upsample_factor=100
            )
            
            # Update cumulative shift
            dy_residual, dx_residual = shift
            dx -= dx_residual
            dy -= dy_residual
            
            logger.debug(f"{q} iter {iteration}: dx={dx:.4f}, dy={dy:.4f}, residual=({dx_residual:.4f}, {dy_residual:.4f})")
        
        result.translations[q] = (float(dx), float(dy))
        result.rotations[q] = 0.0
        result.reprojection_errors[q] = float(error)
        
        logger.info(f"{q}: dx={dx:.4f}, dy={dy:.4f}, final_error={error:.6f}")
    
    result.success = len(result.translations) == 3
    return result


def try_phase_correlation_only(images: Dict[str, np.ndarray]) -> AlignmentResult:
    """
    Try pure phase correlation alignment (translation only).
    """
    logger.info("\n" + "="*60)
    logger.info("Trying PHASE CORRELATION (translation only)")
    logger.info("="*60)
    
    result = AlignmentResult(
        method="phase_correlation",
        params={},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    for q in ['NE', 'SW', 'SE']:
        if q not in images:
            continue
        
        img = images[q]
        dx, dy, response = phase_correlation_align(img, ref)
        
        result.translations[q] = (dx, dy)
        result.rotations[q] = 0.0  # Phase correlation doesn't detect rotation
        
        logger.info(f"{q}: dx={dx:+.2f}, dy={dy:+.2f}, response={response:.4f}")
    
    result.success = len(result.translations) == 3
    return result


def try_overlap_aware_matching(images: Dict[str, np.ndarray], 
                                overlap_percent: float = 30.0) -> AlignmentResult:
    """
    Match features only in expected overlap regions.
    This is much more robust for repetitive cell images.
    """
    logger.info("\n" + "="*60)
    logger.info(f"Trying OVERLAP-AWARE MATCHING (overlap={overlap_percent}%)")
    logger.info("="*60)
    
    result = AlignmentResult(
        method=f"overlap_aware_{overlap_percent:.0f}",
        params={'overlap_percent': overlap_percent},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    h, w = ref.shape
    overlap_px = int(w * overlap_percent / 100)
    
    # Use SIFT for better matching
    detector = cv2.SIFT_create(contrastThreshold=0.01, edgeThreshold=15)
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    
    # NE alignment: match right edge of NW with left edge of NE
    if 'NE' in images:
        ne = images['NE']
        
        # Extract overlap regions
        nw_right = ref[:, -overlap_px:]
        ne_left = ne[:, :overlap_px]
        
        kp1, desc1 = detector.detectAndCompute(nw_right, None)
        kp2, desc2 = detector.detectAndCompute(ne_left, None)
        
        if desc1 is not None and desc2 is not None and len(kp1) > 0 and len(kp2) > 0:
            matches = matcher.knnMatch(desc2, desc1, k=2)
            good = [m for m, n in matches if len([m, n]) == 2 and m.distance < 0.75 * n.distance]
            
            if len(good) >= 8:
                # Adjust keypoint coordinates to full image coords
                for kp in kp1:
                    kp.pt = (kp.pt[0] + w - overlap_px, kp.pt[1])
                
                src_pts = np.float32([kp2[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp1[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
                
                H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0)
                if H is not None:
                    dx, dy, rot = extract_transform_params(H)
                    result.translations['NE'] = (dx, dy)
                    result.rotations['NE'] = rot
                    
                    # Compute error
                    inliers = mask.ravel() == 1
                    if np.sum(inliers) > 0:
                        projected = cv2.perspectiveTransform(src_pts[inliers], H)
                        errors = np.sqrt(np.sum((projected - dst_pts[inliers]) ** 2, axis=2))
                        result.reprojection_errors['NE'] = float(errors.mean())
                    
                    result.total_matches += len(good)
                    logger.info(f"NE: {len(good)} matches, dx={dx:.2f}, dy={dy:.2f}, rot={rot:.2f}°")
    
    # SW alignment: match bottom edge of NW with top edge of SW
    if 'SW' in images:
        sw = images['SW']
        
        nw_bottom = ref[-overlap_px:, :]
        sw_top = sw[:overlap_px, :]
        
        kp1, desc1 = detector.detectAndCompute(nw_bottom, None)
        kp2, desc2 = detector.detectAndCompute(sw_top, None)
        
        if desc1 is not None and desc2 is not None and len(kp1) > 0 and len(kp2) > 0:
            matches = matcher.knnMatch(desc2, desc1, k=2)
            good = [m for m, n in matches if len([m, n]) == 2 and m.distance < 0.75 * n.distance]
            
            if len(good) >= 8:
                for kp in kp1:
                    kp.pt = (kp.pt[0], kp.pt[1] + h - overlap_px)
                
                src_pts = np.float32([kp2[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp1[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
                
                H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0)
                if H is not None:
                    dx, dy, rot = extract_transform_params(H)
                    result.translations['SW'] = (dx, dy)
                    result.rotations['SW'] = rot
                    
                    inliers = mask.ravel() == 1
                    if np.sum(inliers) > 0:
                        projected = cv2.perspectiveTransform(src_pts[inliers], H)
                        errors = np.sqrt(np.sum((projected - dst_pts[inliers]) ** 2, axis=2))
                        result.reprojection_errors['SW'] = float(errors.mean())
                    
                    result.total_matches += len(good)
                    logger.info(f"SW: {len(good)} matches, dx={dx:.2f}, dy={dy:.2f}, rot={rot:.2f}°")
    
    # SE alignment: use NE and SW as intermediate
    if 'SE' in images and 'NE' in result.translations and 'SW' in result.translations:
        se = images['SE']
        
        # SE is below NE: match bottom of NE with top of SE
        if 'NE' in images:
            ne = images['NE']
            ne_bottom = ne[-overlap_px:, :]
            se_top = se[:overlap_px, :]
            
            kp1, desc1 = detector.detectAndCompute(ne_bottom, None)
            kp2, desc2 = detector.detectAndCompute(se_top, None)
            
            if desc1 is not None and desc2 is not None and len(kp1) > 0 and len(kp2) > 0:
                matches = matcher.knnMatch(desc2, desc1, k=2)
                good = [m for m, n in matches if len([m, n]) == 2 and m.distance < 0.75 * n.distance]
                
                if len(good) >= 8:
                    for kp in kp1:
                        kp.pt = (kp.pt[0], kp.pt[1] + h - overlap_px)
                    
                    src_pts = np.float32([kp2[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                    dst_pts = np.float32([kp1[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
                    
                    H_se_ne, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0)
                    if H_se_ne is not None:
                        # Chain: SE -> NE -> NW
                        dx_ne, dy_ne = result.translations['NE']
                        H_ne_nw = np.array([
                            [1, 0, dx_ne],
                            [0, 1, dy_ne],
                            [0, 0, 1]
                        ], dtype=np.float64)
                        
                        H_se_nw = H_ne_nw @ H_se_ne
                        dx, dy, rot = extract_transform_params(H_se_nw)
                        result.translations['SE'] = (dx, dy)
                        result.rotations['SE'] = rot
                        
                        inliers = mask.ravel() == 1
                        if np.sum(inliers) > 0:
                            projected = cv2.perspectiveTransform(src_pts[inliers], H_se_ne)
                            errors = np.sqrt(np.sum((projected - dst_pts[inliers]) ** 2, axis=2))
                            result.reprojection_errors['SE'] = float(errors.mean())
                        
                        result.total_matches += len(good)
                        logger.info(f"SE (via NE): {len(good)} matches, dx={dx:.2f}, dy={dy:.2f}, rot={rot:.2f}°")
    
    result.success = len(result.translations) == 3
    return result


def try_template_matching(images: Dict[str, np.ndarray], template_size: int = 200) -> AlignmentResult:
    """
    Try template matching for fine alignment.
    """
    logger.info("\n" + "="*60)
    logger.info(f"Trying TEMPLATE MATCHING (size={template_size})")
    logger.info("="*60)
    
    result = AlignmentResult(
        method=f"template_matching_{template_size}",
        params={'template_size': template_size},
        translations={},
        rotations={},
        reprojection_errors={},
        total_matches=0,
        success=False
    )
    
    ref = images.get('NW')
    if ref is None:
        result.notes = "NW missing"
        return result
    
    h, w = ref.shape
    
    # Expected overlap regions
    overlap_regions = {
        'NE': ((0, h//3, w-template_size, 2*h//3), 'left'),   # Right edge of NW, left of NE
        'SW': ((h-template_size, w//3, h, 2*w//3), 'top'),    # Bottom of NW, top of SW
        'SE': None  # Will compute via SW or NE
    }
    
    for q in ['NE', 'SW']:
        if q not in images:
            continue
        
        img = images[q]
        
        # Take template from overlap region of NW
        if q == 'NE':
            # Right edge of NW
            template = ref[:, -template_size:]
            search_area = img[:, :template_size*2]
        else:  # SW
            # Bottom edge of NW
            template = ref[-template_size:, :]
            search_area = img[:template_size*2, :]
        
        # Template matching
        res = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        # Compute translation
        if q == 'NE':
            # NE is to the right of NW
            dx = (w - template_size) - max_loc[0]
            dy = -max_loc[1]
        else:  # SW
            dx = -max_loc[0]
            dy = (h - template_size) - max_loc[1]
        
        result.translations[q] = (dx, dy)
        result.rotations[q] = 0.0
        result.reprojection_errors[q] = 1.0 - max_val  # Lower is better
        
        logger.info(f"{q}: dx={dx:+.2f}, dy={dy:+.2f}, confidence={max_val:.4f}")
    
    # Compute SE from SW and NE
    if 'NE' in result.translations and 'SW' in result.translations:
        dx_ne, dy_ne = result.translations['NE']
        dx_sw, dy_sw = result.translations['SW']
        
        # SE should be at (NE_x, SW_y) approximately
        result.translations['SE'] = (dx_ne, dy_sw)
        result.rotations['SE'] = 0.0
        logger.info(f"SE (estimated): dx={dx_ne:+.2f}, dy={dy_sw:+.2f}")
    
    result.success = len(result.translations) == 3
    return result


def visualize_alignment(images: Dict[str, np.ndarray], 
                        translations: Dict[str, Tuple[float, float]],
                        output_path: str):
    """
    Visualize the alignment by compositing images.
    """
    if 'NW' not in images:
        return
    
    # Calculate canvas size
    h, w = images['NW'].shape[:2]
    
    # Find bounds
    all_x = [0, w]
    all_y = [0, h]
    
    for q, (dx, dy) in translations.items():
        all_x.extend([dx, dx + w])
        all_y.extend([dy, dy + h])
    
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    canvas_w = int(max_x - min_x + 1)
    canvas_h = int(max_y - min_y + 1)
    offset_x = -min_x
    offset_y = -min_y
    
    # Create canvas (use float for averaging)
    canvas_sum = np.zeros((canvas_h, canvas_w), dtype=np.float64)
    canvas_count = np.zeros((canvas_h, canvas_w), dtype=np.float64)
    
    # Place NW
    x1, y1 = int(offset_x), int(offset_y)
    canvas_sum[y1:y1+h, x1:x1+w] += images['NW'].astype(np.float64)
    canvas_count[y1:y1+h, x1:x1+w] += 1
    
    # Place other quadrants
    for q, (dx, dy) in translations.items():
        if q not in images:
            continue
        
        img = images[q]
        x1 = int(offset_x + dx)
        y1 = int(offset_y + dy)
        
        # Clip to canvas
        src_x1 = max(0, -x1)
        src_y1 = max(0, -y1)
        dst_x1 = max(0, x1)
        dst_y1 = max(0, y1)
        
        copy_w = min(w - src_x1, canvas_w - dst_x1)
        copy_h = min(h - src_y1, canvas_h - dst_y1)
        
        if copy_w > 0 and copy_h > 0:
            canvas_sum[dst_y1:dst_y1+copy_h, dst_x1:dst_x1+copy_w] += \
                img[src_y1:src_y1+copy_h, src_x1:src_x1+copy_w].astype(np.float64)
            canvas_count[dst_y1:dst_y1+copy_h, dst_x1:dst_x1+copy_w] += 1
    
    # Average
    canvas_count[canvas_count == 0] = 1
    result = (canvas_sum / canvas_count).astype(np.uint8)
    
    cv2.imwrite(output_path, result)
    logger.info(f"Saved visualization to {output_path}")


def visualize_stitching_result(images: Dict[str, np.ndarray], 
                                translations: Dict[str, Tuple[float, float]],
                                title: str = "Stitching Result",
                                output_path: Optional[str] = None) -> np.ndarray:
    """
    Create a visualization of the stitched result.
    
    Args:
        images: Dict of quadrant images (grayscale)
        translations: Dict mapping quadrant name to (dx, dy) translation
        title: Title for the plot
        output_path: If provided, save to this path
        
    Returns:
        Stitched image as numpy array
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    
    ref = images.get('NW')
    if ref is None:
        return None
    
    h, w = ref.shape
    
    # Calculate canvas size
    min_x, max_x = 0, w
    min_y, max_y = 0, h
    
    for q, (dx, dy) in translations.items():
        min_x = min(min_x, dx)
        max_x = max(max_x, dx + w)
        min_y = min(min_y, dy)
        max_y = max(max_y, dy + h)
    
    canvas_w = int(max_x - min_x) + 10
    canvas_h = int(max_y - min_y) + 10
    ox, oy = -min_x + 5, -min_y + 5
    
    # Create canvas
    canvas = np.zeros((canvas_h, canvas_w), dtype=np.float32)
    count_canvas = np.zeros((canvas_h, canvas_w), dtype=np.int32)
    
    # Composite using mean blending
    quadrant_positions = {'NW': (0, 0)}
    quadrant_positions.update({q: t for q, t in translations.items()})
    
    for q_name in ['NW', 'NE', 'SW', 'SE']:
        if q_name not in images:
            continue
        
        img = images[q_name].astype(np.float32)
        dx, dy = quadrant_positions.get(q_name, (0, 0))
        
        x = int(dx + ox)
        y = int(dy + oy)
        
        # Clip to canvas
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
            count_canvas[dst_y0:dst_y1, dst_x0:dst_x1] += 1
    
    # Mean blending
    valid_mask = count_canvas > 0
    canvas[valid_mask] /= count_canvas[valid_mask]
    
    return canvas


def plot_alignment_comparison(images: Dict[str, np.ndarray],
                               results: List['AlignmentResult'],
                               output_path: str,
                               top_n: int = 6):
    """
    Create a comparison plot showing multiple alignment results.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    
    # Filter successful results
    successful = [r for r in results if r.success and r.translations]
    if not successful:
        logger.warning("No successful results to visualize")
        return
    
    # Score by consistency
    def consistency_score(r):
        if 'NE' not in r.translations or 'SW' not in r.translations or 'SE' not in r.translations:
            return float('inf')
        dx_ne, dy_ne = r.translations['NE']
        dx_sw, dy_sw = r.translations['SW']
        dx_se, dy_se = r.translations['SE']
        return abs(dx_se - dx_ne) + abs(dy_se - dy_sw)
    
    successful.sort(key=consistency_score)
    top_results = successful[:top_n]
    
    # Create figure
    n_cols = min(3, len(top_results))
    n_rows = (len(top_results) + n_cols - 1) // n_cols + 1  # +1 for original quadrants
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6*n_cols, 5*n_rows))
    if n_rows == 1:
        axes = axes.reshape(1, -1)
    
    # Show original quadrants in first row
    quadrant_names = ['NW', 'NE', 'SW', 'SE']
    for i, q in enumerate(quadrant_names[:n_cols]):
        if q in images:
            axes[0, i].imshow(images[q], cmap='gray')
            axes[0, i].set_title(f'Original {q}', fontsize=12)
            axes[0, i].axis('off')
    
    # Show stitched results
    for idx, result in enumerate(top_results):
        row = 1 + idx // n_cols
        col = idx % n_cols
        
        if row >= n_rows:
            break
        
        stitched = visualize_stitching_result(images, result.translations)
        if stitched is not None:
            axes[row, col].imshow(stitched, cmap='gray')
            
            # Add quadrant boundaries
            h, w = images['NW'].shape
            colors = {'NW': 'red', 'NE': 'green', 'SW': 'blue', 'SE': 'yellow'}
            
            score = consistency_score(result)
            title = f"{result.method}\nconsistency={score:.1f}"
            if 'NE' in result.translations:
                ne_dx, ne_dy = result.translations['NE']
                title += f"\nNE:({ne_dx:.0f},{ne_dy:.0f})"
            if 'SW' in result.translations:
                sw_dx, sw_dy = result.translations['SW']
                title += f" SW:({sw_dx:.0f},{sw_dy:.0f})"
            if 'SE' in result.translations:
                se_dx, se_dy = result.translations['SE']
                title += f" SE:({se_dx:.0f},{se_dy:.0f})"
            
            axes[row, col].set_title(title, fontsize=9)
        axes[row, col].axis('off')
    
    # Hide empty subplots
    for i in range(n_rows):
        for j in range(n_cols):
            if i > 0 and (i-1) * n_cols + j >= len(top_results):
                axes[i, j].axis('off')
    
    plt.suptitle('Alignment Comparison (sorted by consistency score)', fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved comparison plot to {output_path}")


def plot_best_alignment_detail(images: Dict[str, np.ndarray],
                                result: 'AlignmentResult',
                                output_path: str):
    """
    Create a detailed plot of the best alignment result.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, FancyArrowPatch
    import matplotlib.patches as mpatches
    
    fig = plt.figure(figsize=(16, 10))
    
    # Create grid layout
    gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
    
    # 1. Stitched result (large, left side)
    ax_main = fig.add_subplot(gs[:, 0])
    stitched = visualize_stitching_result(images, result.translations)
    if stitched is not None:
        ax_main.imshow(stitched, cmap='gray')
        ax_main.set_title(f'Stitched Result\n{result.method}', fontsize=14)
    ax_main.axis('off')
    
    # 2. Quadrant positions diagram (top right)
    ax_diagram = fig.add_subplot(gs[0, 1])
    h, w = images['NW'].shape
    
    # Draw quadrant positions
    colors = {'NW': '#FF6B6B', 'NE': '#4ECDC4', 'SW': '#45B7D1', 'SE': '#96CEB4'}
    positions = {'NW': (0, 0)}
    positions.update({q: result.translations[q] for q in ['NE', 'SW', 'SE'] if q in result.translations})
    
    for q, (dx, dy) in positions.items():
        rect = Rectangle((dx, dy), w, h, linewidth=2, edgecolor=colors[q], 
                         facecolor=colors[q], alpha=0.3)
        ax_diagram.add_patch(rect)
        ax_diagram.text(dx + w/2, dy + h/2, q, ha='center', va='center', 
                       fontsize=12, fontweight='bold', color='black')
    
    ax_diagram.set_xlim(-100, w * 1.8)
    ax_diagram.set_ylim(-100, h * 1.8)
    ax_diagram.invert_yaxis()
    ax_diagram.set_aspect('equal')
    ax_diagram.set_title('Quadrant Positions', fontsize=12)
    ax_diagram.set_xlabel('X (pixels)')
    ax_diagram.set_ylabel('Y (pixels)')
    
    # Add legend
    legend_elements = [mpatches.Patch(facecolor=colors[q], alpha=0.5, label=q) for q in colors]
    ax_diagram.legend(handles=legend_elements, loc='lower right')
    
    # 3. Translation values (top far right)
    ax_text = fig.add_subplot(gs[0, 2])
    ax_text.axis('off')
    
    text_content = f"Method: {result.method}\n\n"
    text_content += "Translations:\n"
    for q in ['NE', 'SW', 'SE']:
        if q in result.translations:
            dx, dy = result.translations[q]
            rot = result.rotations.get(q, 0)
            err = result.reprojection_errors.get(q, 0)
            text_content += f"  {q}: dx={dx:+.2f}, dy={dy:+.2f}\n"
            text_content += f"      rot={rot:+.2f}°, err={err:.4f}\n"
    
    # Consistency check
    if all(q in result.translations for q in ['NE', 'SW', 'SE']):
        ne_dx, ne_dy = result.translations['NE']
        sw_dx, sw_dy = result.translations['SW']
        se_dx, se_dy = result.translations['SE']
        
        text_content += f"\nConsistency Check:\n"
        text_content += f"  SE expected: ({ne_dx:.1f}, {sw_dy:.1f})\n"
        text_content += f"  SE actual:   ({se_dx:.1f}, {se_dy:.1f})\n"
        
        err_x = abs(se_dx - ne_dx)
        err_y = abs(se_dy - sw_dy)
        text_content += f"  Error: ({err_x:.1f}, {err_y:.1f}) px\n"
        text_content += f"  Total: {err_x + err_y:.1f} px"
    
    ax_text.text(0.1, 0.9, text_content, transform=ax_text.transAxes, 
                fontsize=11, verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 4. Overlap regions (bottom middle and right)
    ax_ne_overlap = fig.add_subplot(gs[1, 1])
    ax_sw_overlap = fig.add_subplot(gs[1, 2])
    
    # Show NE overlap with NW
    if 'NE' in result.translations:
        ne_dx, ne_dy = result.translations['NE']
        overlap_w = max(0, int(w - abs(ne_dx)))
        overlap_h = h
        
        if overlap_w > 0:
            # Get overlap regions
            nw_region = images['NW'][:, -overlap_w:]
            ne_region = images['NE'][:, :overlap_w]
            
            # Show side by side
            combined = np.hstack([nw_region, ne_region])
            ax_ne_overlap.imshow(combined, cmap='gray')
            ax_ne_overlap.axvline(x=overlap_w, color='red', linewidth=2, linestyle='--')
            ax_ne_overlap.set_title(f'NW-NE Overlap\n(shift: {ne_dx:.1f}px)', fontsize=11)
    ax_ne_overlap.axis('off')
    
    # Show SW overlap with NW
    if 'SW' in result.translations:
        sw_dx, sw_dy = result.translations['SW']
        overlap_h = max(0, int(h - abs(sw_dy)))
        
        if overlap_h > 0:
            nw_region = images['NW'][-overlap_h:, :]
            sw_region = images['SW'][:overlap_h, :]
            
            combined = np.vstack([nw_region, sw_region])
            ax_sw_overlap.imshow(combined, cmap='gray')
            ax_sw_overlap.axhline(y=overlap_h, color='blue', linewidth=2, linestyle='--')
            ax_sw_overlap.set_title(f'NW-SW Overlap\n(shift: {sw_dy:.1f}px)', fontsize=11)
    ax_sw_overlap.axis('off')
    
    plt.suptitle('Alignment Analysis', fontsize=16, y=0.98)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved detailed analysis to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Optimize image alignment parameters")
    parser.add_argument('--input-dir', required=True, help="Directory containing CZI files")
    parser.add_argument('--prefix', required=True, help="File prefix (e.g., '2025.10.22-10.34.56-4134-opnT2_')")
    parser.add_argument('--output-dir', default='grid_optimization/output', help="Output directory for results")
    parser.add_argument('--no-plot', action='store_true', help="Skip generating plots")
    
    args = parser.parse_args()
    
    # Load images
    logger.info(f"Loading images from {args.input_dir} with prefix {args.prefix}")
    images = load_quadrant_images(args.input_dir, args.prefix)
    
    if len(images) < 4:
        logger.error(f"Only found {len(images)} images, need 4")
        return 1
    
    logger.info(f"Loaded {len(images)} images: {list(images.keys())}")
    
    # Run optimization
    results = run_optimization(images)
    
    # Also try alternative methods
    results.append(try_phase_correlation_only(images))
    results.append(try_overlap_aware_matching(images, 20))
    results.append(try_overlap_aware_matching(images, 30))
    results.append(try_overlap_aware_matching(images, 40))
    
    # Grid-constrained alignment with different overlap assumptions
    results.append(try_grid_constrained_alignment(images, 30, 50))
    results.append(try_grid_constrained_alignment(images, 35, 50))
    results.append(try_grid_constrained_alignment(images, 40, 50))
    results.append(try_grid_constrained_alignment(images, 70, 50))  # High overlap based on NE result ~307px
    
    # Scikit-image methods
    if SKIMAGE_AVAILABLE:
        # Direct to NW alignment with iterative refinement (best method)
        results.append(try_skimage_direct_to_nw(images, max_zoom_percent=5.0, target_correlation=0.9))
        results.append(try_skimage_direct_to_nw(images, max_zoom_percent=5.0, target_correlation=0.95))
        results.append(try_skimage_direct_to_nw(images, max_zoom_percent=3.0, target_correlation=0.9))
        
        results.append(try_skimage_chained_registration(images))
        results.append(try_skimage_with_zoom(images, max_zoom_percent=5.0))
        results.append(try_skimage_with_zoom(images, max_zoom_percent=3.0))
        results.append(try_skimage_phase_correlation(images, upsample_factor=100))
        results.append(try_skimage_phase_correlation(images, upsample_factor=1000))
        results.append(try_skimage_masked_registration(images, overlap_percent=70))
        results.append(try_skimage_masked_registration(images, overlap_percent=60))
        results.append(try_skimage_orb_registration(images))
        results.append(try_skimage_iterative_registration(images, num_iterations=3))
        results.append(try_skimage_iterative_registration(images, num_iterations=5))
    
    results.append(try_template_matching(images, 200))
    results.append(try_template_matching(images, 300))
    
    # Find best result
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    
    successful = [r for r in results if r.success]
    
    if not successful:
        logger.error("No configuration succeeded!")
        return 1
    
    # Score by geometric consistency: SE should be approximately at (NE_x, SW_y)
    # Also consider NCC quality for grid-constrained methods
    def consistency_score(r):
        if 'NE' not in r.translations or 'SW' not in r.translations or 'SE' not in r.translations:
            return float('inf')
        
        dx_ne, dy_ne = r.translations['NE']
        dx_sw, dy_sw = r.translations['SW']
        dx_se, dy_se = r.translations['SE']
        
        # Expected SE position
        expected_dx = dx_ne  # SE should be at same X as NE (to the right)
        expected_dy = dy_sw  # SE should be at same Y as SW (below)
        
        # Consistency error
        x_err = abs(dx_se - expected_dx)
        y_err = abs(dy_se - expected_dy)
        
        # Also penalize extreme rotations
        rot_penalty = sum(abs(r.rotations.get(q, 0)) for q in ['NE', 'SW', 'SE']) / 3
        if rot_penalty > 5:  # Penalize heavily if average rotation > 5°
            rot_penalty *= 10
        
        # For grid-constrained methods, also consider NCC quality (lower error = higher NCC)
        # reprojection_errors for grid methods are 1-NCC, so lower is better
        if r.method.startswith('grid_constrained'):
            avg_ncc = 1 - np.mean(list(r.reprojection_errors.values()))
            # Boost score if NCC is high (above 0.5)
            if avg_ncc > 0.5:
                return (x_err + y_err + rot_penalty) * 0.5  # Halve score (lower is better)
            elif avg_ncc < 0.2:
                return (x_err + y_err + rot_penalty) * 2  # Double score (penalize low NCC)
        
        # For template matching, penalize if translations don't make physical sense
        if r.method.startswith('template'):
            # If NE translation is > 60% of image width, it's likely wrong
            if abs(dx_ne) > 600 or abs(dy_sw) > 600:
                return (x_err + y_err + rot_penalty) + 500  # Heavy penalty
        
        return x_err + y_err + rot_penalty
    
    # Rank by consistency
    successful.sort(key=consistency_score)
    
    logger.info("\n** CONSISTENCY-BASED RANKING (SE should be at NE_x, SW_y) **")
    for i, r in enumerate(successful[:5]):
        score = consistency_score(r)
        logger.info(f"{i+1}. {r.method}: consistency_score={score:.2f}")
        if 'NE' in r.translations and 'SW' in r.translations and 'SE' in r.translations:
            dx_ne, dy_ne = r.translations['NE']
            dx_sw, dy_sw = r.translations['SW']
            dx_se, dy_se = r.translations['SE']
            logger.info(f"   Expected SE: ({dx_ne:.1f}, {dy_sw:.1f}), Actual: ({dx_se:.1f}, {dy_se:.1f})")
    
    # Also rank by reprojection error
    def reproj_score(r):
        errors = list(r.reprojection_errors.values())
        return np.mean(errors) if errors else float('inf')
    
    successful_by_error = sorted(successful, key=reproj_score)
    
    logger.info("\nRanked results (by reprojection error):")
    for i, r in enumerate(successful_by_error[:5]):
        avg_err = reproj_score(r)
        logger.info(f"\n{i+1}. {r.method}")
        logger.info(f"   Average reprojection error: {avg_err:.4f}px")
        logger.info(f"   Total matches: {r.total_matches}")
        for q in ['NE', 'SW', 'SE']:
            if q in r.translations:
                dx, dy = r.translations[q]
                rot = r.rotations[q]
                logger.info(f"   {q}: dx={dx:+7.2f}, dy={dy:+7.2f}, rot={rot:+5.2f}°")
    
    # Best result (by consistency - first in list after sorting)
    best = successful[0]  # Already sorted by consistency
    logger.info(f"\n*** BEST: {best.method} ***")
    logger.info(f"Parameters: {best.params}")
    
    # Generate plots
    if not args.no_plot:
        output_dir = Path(args.output_dir)
        
        # Comparison plot showing top 6 methods
        comparison_path = output_dir / "alignment_comparison.png"
        plot_alignment_comparison(images, results, str(comparison_path), top_n=6)
        
        # Detailed analysis of best result
        detail_path = output_dir / "alignment_detail.png"
        plot_best_alignment_detail(images, best, str(detail_path))
        
        # Save the stitched image
        stitched_path = output_dir / "stitched_result.png"
        stitched = visualize_stitching_result(images, best.translations)
        if stitched is not None:
            import matplotlib.pyplot as plt
            plt.figure(figsize=(12, 12))
            plt.imshow(stitched, cmap='gray')
            plt.title(f'Stitched Result: {best.method}', fontsize=14)
            plt.axis('off')
            plt.savefig(str(stitched_path), dpi=200, bbox_inches='tight')
            plt.close()
            logger.info(f"Saved stitched image to {stitched_path}")
    
    # Save best parameters as JSON
    import json
    params_path = Path(args.output_dir) / "best_alignment_params.json"
    
    params = {
        'method': best.method,
        'config': {k: str(v) for k, v in best.params.items()},
        'alignments': {
            q: {
                'translation': [float(x) for x in best.translations[q]],
                'rotation': float(best.rotations[q]),
                'reprojection_error': float(best.reprojection_errors.get(q, 0))
            }
            for q in best.translations
        }
    }
    
    with open(params_path, 'w') as f:
        json.dump(params, f, indent=2)
    
    logger.info(f"Saved parameters to {params_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
