#!/usr/bin/env python3
"""
LaTeX-Aware Adaptive OCR Destroyer
The quantum evolution of PDF text extraction that respects academic typographical perfection
while demolishing everything else with extreme prejudice
"""

import pypdf
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat
import pdf2image
import numpy as np
import cv2
import io
import os
import argparse
import re
from pathlib import Path
import logging
from dataclasses import dataclass
from typing import Tuple, List, Dict
import math

# Configure logging for maximum intelligence warfare
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class LaTeXQualityMetrics:
    """
    The forensic report card for LaTeX document quality and complexity
    This is CSI: Academic Document Edition
    """
    base_resolution: int              # Effective DPI
    contrast_ratio: float             # Text-background separation power
    noise_level: float                # Digital artifact contamination
    sharpness_score: float           # Edge definition crispness
    brightness_variance: float        # Lighting consistency
    math_density: float              # Mathematical notation concentration
    font_complexity: float           # Typography sophistication level
    ligature_probability: float      # Likelihood of ligature chaos
    layout_complexity: float         # Multi-column/table nightmare factor
    overall_quality: str             # HIGH, MEDIUM, LOW, GARBAGE
    latex_confidence: float          # Probability this is LaTeX-generated
    
    def __str__(self):
        return (f"LaTeX Quality Intel: {self.overall_quality} | "
                f"LaTeX Confidence: {self.latex_confidence:.1%} | "
                f"Resolution: {self.base_resolution}DPI | "
                f"Math Density: {self.math_density:.1%} | "
                f"Font Complexity: {self.font_complexity:.2f}")

class LaTeXDocumentDetective:
    """
    The Sherlock Holmes of academic document forensics
    Can smell a LaTeX document from across the digital universe and assess its quality faster than a caffeinated PhD student
    """
    
    def __init__(self):
        # Quality thresholds calibrated for academic document warfare
        self.quality_thresholds = {
            'high_resolution': 200,          # LaTeX often renders at lower effective DPI
            'excellent_contrast': 3.0,       # Academic documents usually have stellar contrast
            'low_noise': 0.1,               # Professional LaTeX is pristine
            'sharp_threshold': 120,          # Vector fonts are crispy as fuck
            'consistent_lighting': 1500,     # Perfect synthetic lighting
            'high_math_density': 0.15,       # 15%+ mathematical symbols
            'complex_fonts': 1.5,            # Sophisticated typography
            'ligature_heavy': 0.8            # High probability of ligature nightmares
        }
        
        # LaTeX detection patterns - the digital fingerprints of academic perfection
        self.latex_indicators = {
            'mathematical_symbols': r'[âˆ‘âˆ«âˆ‚âˆ‡Ã—Â±â‰¤â‰¥â‰ â‰ˆâˆžÂ°âˆšâˆâˆˆâˆ‰âŠ‚âŠƒâˆªâˆ©Î±Î²Î³Î´ÎµÎ¶Î·Î¸Î¹ÎºÎ»Î¼Î½Î¾Î¿Ï€ÏÏƒÏ„Ï…Ï†Ï‡ÏˆÏ‰Î‘Î’Î“Î”Î•Î–Î—Î˜Î™ÎšÎ›ÎœÎÎžÎŸÎ Î¡Î£Î¤Î¥Î¦Î§Î¨Î©]',
            'latex_ligatures': r'[ï¬ï¬‚ï¬€ï¬ƒï¬„]',
            'academic_patterns': r'(theorem|lemma|proof|equation|figure|table|bibliography|references)',
            'citation_patterns': r'(\[[0-9,\-\s]+\]|\([A-Za-z]+\s+et\s+al\.\s+[0-9]{4}\))',
            'math_environments': r'(\$.*?\$|\\begin\{.*?\}|\\end\{.*?\})'
        }
    
    def detect_mathematical_density(self, image: Image.Image) -> float:
        """
        Calculate the concentration of mathematical notation in the document
        This is like a geiger counter for academic complexity
        
        Args:
            image: PIL Image to analyze
            
        Returns:
            Mathematical symbol density (0.0 to 1.0)
        """
        try:
            # Quick OCR scan to detect mathematical symbols
            quick_text = pytesseract.image_to_string(
                image, 
                config='--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ .,!?:;-_()[]{}"\''
            )
            
            if not quick_text:
                return 0.0
            
            # Count mathematical symbols and patterns
            math_pattern = re.compile(self.latex_indicators['mathematical_symbols'])
            math_matches = len(math_pattern.findall(quick_text))
            
            # Look for equation-like patterns
            equation_patterns = [
                r'[a-zA-Z]\s*[=]\s*[a-zA-Z0-9]',  # Simple equations
                r'[0-9]+\s*[+\-*/]\s*[0-9]+',     # Mathematical operations
                r'[a-zA-Z]_[0-9]',                # Subscripts (poorly OCR'd)
                r'[a-zA-Z]\^[0-9]'                # Superscripts (poorly OCR'd)
            ]
            
            equation_matches = 0
            for pattern in equation_patterns:
                equation_matches += len(re.findall(pattern, quick_text))
            
            total_math_indicators = math_matches + equation_matches
            total_chars = len(quick_text.replace(' ', ''))
            
            if total_chars == 0:
                return 0.0
            
            math_density = min(total_math_indicators / total_chars, 1.0)
            logger.debug(f"Mathematical density: {math_density:.1%}")
            return math_density
            
        except Exception as e:
            logger.warning(f"Mathematical density detection failed: {e}")
            return 0.0
    
    def assess_font_complexity(self, image: Image.Image) -> float:
        """
        Analyze typographical sophistication level
        LaTeX fonts are like digital calligraphy - beautiful but OCR-hostile
        
        Args:
            image: PIL Image to analyze
            
        Returns:
            Font complexity score (higher = more sophisticated/problematic)
        """
        try:
            # Convert to grayscale for analysis
            if image.mode != 'L':
                gray_image = image.convert('L')
            else:
                gray_image = image
            
            img_array = np.array(gray_image)
            
            # Analyze character stroke width variation
            # LaTeX fonts have sophisticated stroke modulation
            edges = cv2.Canny(img_array, 50, 150)
            
            # Calculate edge density and variation
            edge_density = np.mean(edges) / 255.0
            
            # Analyze horizontal and vertical stroke patterns
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1))
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 9))
            
            horizontal_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
            vertical_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, vertical_kernel)
            
            stroke_variation = np.std([np.mean(horizontal_lines), np.mean(vertical_lines)])
            
            # Complex fonts have higher edge density and stroke variation
            complexity_score = edge_density * 10 + stroke_variation * 5
            
            logger.debug(f"Font complexity score: {complexity_score:.2f}")
            return min(complexity_score, 5.0)  # Cap at reasonable maximum
            
        except Exception as e:
            logger.warning(f"Font complexity analysis failed: {e}")
            return 1.0
    
    def detect_ligature_probability(self, image: Image.Image) -> float:
        """
        Estimate likelihood of ligature-induced OCR chaos
        LaTeX loves ligatures like a typography nerd loves kerning
        
        Args:
            image: PIL Image to analyze
            
        Returns:
            Ligature probability (0.0 to 1.0)
        """
        try:
            # Quick OCR to find potential ligature artifacts
            sample_text = pytesseract.image_to_string(image, config='--oem 3 --psm 6')
            
            if not sample_text:
                return 0.0
            
            # Look for ligature indicators
            ligature_pattern = re.compile(self.latex_indicators['latex_ligatures'])
            ligature_matches = len(ligature_pattern.findall(sample_text))
            
            # Look for common ligature source combinations
            potential_ligatures = ['fi', 'fl', 'ff', 'ffi', 'ffl']
            ligature_sources = 0
            
            for combo in potential_ligatures:
                ligature_sources += sample_text.count(combo)
            
            # Calculate probability based on detected patterns
            total_indicators = ligature_matches * 3 + ligature_sources  # Weight actual ligatures higher
            total_chars = len(sample_text.replace(' ', ''))
            
            if total_chars == 0:
                return 0.0
            
            probability = min(total_indicators / total_chars * 10, 1.0)  # Scale and cap
            logger.debug(f"Ligature probability: {probability:.1%}")
            return probability
            
        except Exception as e:
            logger.warning(f"Ligature detection failed: {e}")
            return 0.5  # Conservative estimate
    
    def analyze_layout_complexity(self, image: Image.Image) -> float:
        """
        Assess document layout sophistication
        LaTeX can create layouts that would make InDesign weep
        
        Args:
            image: PIL Image to analyze
            
        Returns:
            Layout complexity score (0.0 to 1.0)
        """
        try:
            # Convert to grayscale
            if image.mode != 'L':
                gray_image = image.convert('L')
            else:
                gray_image = image
            
            img_array = np.array(gray_image)
            
            # Detect text regions using morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 5))
            morph = cv2.morphologyEx(img_array, cv2.MORPH_CLOSE, kernel)
            
            # Find contours of text blocks
            contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(contours) == 0:
                return 0.0
            
            # Analyze spatial distribution of text blocks
            centroids = []
            for contour in contours:
                M = cv2.moments(contour)
                if M['m00'] != 0:
                    cx = int(M['m10'] / M['m00'])
                    cy = int(M['m01'] / M['m00'])
                    centroids.append((cx, cy))
            
            if len(centroids) < 2:
                return 0.1  # Simple single-column layout
            
            # Calculate layout complexity metrics
            # Multi-column detection
            x_positions = [c[0] for c in centroids]
            x_variance = np.var(x_positions)
            
            # Vertical alignment analysis
            y_positions = [c[1] for c in centroids]
            y_variance = np.var(y_positions)
            
            # Complex layouts have high variance in both dimensions
            img_width, img_height = image.size
            normalized_complexity = min((x_variance + y_variance) / (img_width * img_height) * 1000, 1.0)
            
            logger.debug(f"Layout complexity: {normalized_complexity:.2f}")
            return normalized_complexity
            
        except Exception as e:
            logger.warning(f"Layout analysis failed: {e}")
            return 0.3  # Medium complexity estimate
    
    def calculate_latex_confidence(self, metrics: Dict) -> float:
        """
        Determine probability that this document was generated by LaTeX
        This is like digital DNA analysis for academic documents
        
        Args:
            metrics: Dictionary of calculated metrics
            
        Returns:
            LaTeX confidence score (0.0 to 1.0)
        """
        confidence_score = 0.0
        
        # High-quality rendering suggests vector-based generation (LaTeX characteristic)
        if metrics['contrast_ratio'] > 2.5 and metrics['sharpness_score'] > 100:
            confidence_score += 0.3
        
        # Mathematical content is a strong LaTeX indicator
        if metrics['math_density'] > 0.05:
            confidence_score += 0.4 * min(metrics['math_density'] * 10, 1.0)
        
        # Font complexity suggests sophisticated typography
        if metrics['font_complexity'] > 1.2:
            confidence_score += 0.2
        
        # Layout complexity indicates academic formatting
        if metrics['layout_complexity'] > 0.3:
            confidence_score += 0.15
        
        # High ligature probability is classic LaTeX
        if metrics['ligature_probability'] > 0.3:
            confidence_score += 0.15
        
        # Perfect lighting and low noise suggest synthetic generation
        if metrics['noise_level'] < 0.1 and metrics['brightness_variance'] < 1000:
            confidence_score += 0.1
        
        return min(confidence_score, 1.0)
    
    def assess_latex_quality(self, image: Image.Image, pdf_page_size: Tuple[float, float] = None) -> LaTeXQualityMetrics:
        """
        The master LaTeX document assessment function
        This is where digital forensics meets academic typography analysis
        
        Args:
            image: PIL Image to analyze
            pdf_page_size: Optional page size for accurate DPI calculation
            
        Returns:
            LaTeXQualityMetrics with complete forensic analysis
        """
        logger.info("ðŸ”¬ Conducting LaTeX-aware quality forensics...")
        
        # Basic quality metrics (inherited from base system)
        resolution = self.estimate_effective_dpi(image, pdf_page_size)
        contrast = self.calculate_contrast_ratio(image)
        noise = self.measure_noise_level(image)
        sharpness = self.calculate_sharpness_score(image)
        brightness_var = self.analyze_brightness_consistency(image)
        
        # LaTeX-specific metrics (the academic special sauce)
        math_density = self.detect_mathematical_density(image)
        font_complexity = self.assess_font_complexity(image)
        ligature_prob = self.detect_ligature_probability(image)
        layout_complexity = self.analyze_layout_complexity(image)
        
        # Calculate LaTeX confidence
        metrics_dict = {
            'contrast_ratio': contrast,
            'sharpness_score': sharpness,
            'math_density': math_density,
            'font_complexity': font_complexity,
            'layout_complexity': layout_complexity,
            'ligature_probability': ligature_prob,
            'noise_level': noise,
            'brightness_variance': brightness_var
        }
        
        latex_confidence = self.calculate_latex_confidence(metrics_dict)
        
        # Quality scoring with LaTeX-aware adjustments
        quality_score = 0
        
        # Resolution scoring (LaTeX often has lower effective DPI but high quality)
        if resolution >= 150:  # Lower threshold for LaTeX
            quality_score += 2
        elif resolution >= 100:
            quality_score += 1
        
        # Contrast scoring (LaTeX typically has excellent contrast)
        if contrast >= 3.0:
            quality_score += 2
        elif contrast >= 2.0:
            quality_score += 1
        
        # Noise scoring (LaTeX should be pristine)
        if noise <= 0.08:  # Stricter for LaTeX
            quality_score += 2
        elif noise <= 0.2:
            quality_score += 1
        
        # Sharpness scoring (vector fonts should be crisp)
        if sharpness >= 120:  # Higher threshold for LaTeX
            quality_score += 2
        elif sharpness >= 80:
            quality_score += 1
        
        # Brightness consistency (synthetic documents should be perfect)
        if brightness_var <= 1000:  # Stricter for LaTeX
            quality_score += 2
        elif brightness_var <= 3000:
            quality_score += 1
        
        # Determine overall quality with LaTeX considerations
        if quality_score >= 8:
            overall_quality = "HIGH"
        elif quality_score >= 5:
            overall_quality = "MEDIUM"
        elif quality_score >= 2:
            overall_quality = "LOW"
        else:
            overall_quality = "GARBAGE"
        
        metrics = LaTeXQualityMetrics(
            base_resolution=resolution,
            contrast_ratio=contrast,
            noise_level=noise,
            sharpness_score=sharpness,
            brightness_variance=brightness_var,
            math_density=math_density,
            font_complexity=font_complexity,
            ligature_probability=ligature_prob,
            layout_complexity=layout_complexity,
            overall_quality=overall_quality,
            latex_confidence=latex_confidence
        )
        
        logger.info(f"ðŸ“Š {metrics}")
        return metrics
    
    # Include base quality methods for compatibility
    def estimate_effective_dpi(self, image: Image.Image, pdf_page_size: Tuple[float, float] = None) -> int:
        try:
            img_width, img_height = image.size
            if pdf_page_size:
                page_width_inches = pdf_page_size[0] / 72.0
                page_height_inches = pdf_page_size[1] / 72.0
                dpi_x = img_width / page_width_inches
                dpi_y = img_height / page_height_inches
                estimated_dpi = int((dpi_x + dpi_y) / 2)
            else:
                typical_width_inches = 8.5
                estimated_dpi = int(img_width / typical_width_inches)
            return max(72, estimated_dpi)
        except Exception as e:
            logger.warning(f"DPI estimation failed: {e}")
            return 150
    
    def calculate_contrast_ratio(self, image: Image.Image) -> float:
        try:
            if image.mode != 'L':
                gray_image = image.convert('L')
            else:
                gray_image = image
            stat = ImageStat.Stat(gray_image)
            mean_brightness = stat.mean[0]
            std_brightness = stat.stddev[0]
            if mean_brightness > 0:
                contrast_ratio = std_brightness / mean_brightness
            else:
                contrast_ratio = 0.0
            return contrast_ratio
        except Exception as e:
            logger.warning(f"Contrast calculation failed: {e}")
            return 1.0
    
    def measure_noise_level(self, image: Image.Image) -> float:
        try:
            if image.mode != 'L':
                gray_image = image.convert('L')
            else:
                gray_image = image
            img_array = np.array(gray_image)
            laplacian = cv2.Laplacian(img_array, cv2.CV_64F)
            noise_variance = laplacian.var()
            normalized_noise = min(noise_variance / 10000.0, 1.0)
            return normalized_noise
        except Exception as e:
            logger.warning(f"Noise measurement failed: {e}")
            return 0.5
    
    def calculate_sharpness_score(self, image: Image.Image) -> float:
        try:
            if image.mode != 'L':
                gray_image = image.convert('L')
            else:
                gray_image = image
            img_array = np.array(gray_image)
            sobelx = cv2.Sobel(img_array, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(img_array, cv2.CV_64F, 0, 1, ksize=3)
            gradient_magnitude = np.sqrt(sobelx**2 + sobely**2)
            sharpness = np.mean(gradient_magnitude)
            return sharpness
        except Exception as e:
            logger.warning(f"Sharpness calculation failed: {e}")
            return 50.0
    
    def analyze_brightness_consistency(self, image: Image.Image) -> float:
        try:
            if image.mode != 'L':
                gray_image = image.convert('L')
            else:
                gray_image = image
            img_array = np.array(gray_image)
            h, w = img_array.shape
            block_size = min(h, w) // 10
            if block_size < 10:
                return np.var(img_array)
            block_means = []
            for i in range(0, h - block_size, block_size):
                for j in range(0, w - block_size, block_size):
                    block = img_array[i:i+block_size, j:j+block_size]
                    block_means.append(np.mean(block))
            brightness_variance = np.var(block_means)
            return brightness_variance
        except Exception as e:
            logger.warning(f"Brightness analysis failed: {e}")
            return 1000.0

class LaTeXAwareOCRProcessor:
    """
    The ultimate academic document processing warrior
    Like having a PhD in typography with a black belt in digital text extraction
    """
    
    def __init__(self, tesseract_path=None, lang='eng'):
        """
        Initialize the LaTeX-aware OCR destroyer
        
        Args:
            tesseract_path: Path to tesseract executable
            lang: OCR language (can be multi-language for academic papers)
        """
        self.lang = lang
        self.latex_detective = LaTeXDocumentDetective()
        
        # LaTeX-specific character sets and configurations
        self.latex_char_sets = {
            'basic_latin': r'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ .,!?:;-_()[]{}"\'\`',
            'mathematical': r'Î±Î²Î³Î´ÎµÎ¶Î·Î¸Î¹ÎºÎ»Î¼Î½Î¾Î¿Ï€ÏÏƒÏ„Ï…Ï†Ï‡ÏˆÏ‰Î‘Î’Î“Î”Î•Î–Î—Î˜Î™ÎšÎ›ÎœÎÎžÎŸÎ Î¡Î£Î¤Î¥Î¦Î§Î¨Î©',
            'symbols': r'âˆ‘âˆ«âˆ‚âˆ‡Ã—Â±â‰¤â‰¥â‰ â‰ˆâˆžÂ°âˆšâˆâˆˆâˆ‰âŠ‚âŠƒâˆªâˆ©Ã·Ã—Â¬âˆ§âˆ¨âŠ•âŠ—âˆ…â„â„‚â„•â„¤â„š',
            'accented': r'Ã Ã¡Ã¢Ã¤Ã¨Ã©ÃªÃ«Ã¬Ã­Ã®Ã¯Ã²Ã³Ã´Ã¶Ã¹ÃºÃ»Ã¼Ã€ÃÃ‚Ã„ÃˆÃ‰ÃŠÃ‹ÃŒÃÃŽÃÃ’Ã“Ã”Ã–Ã™ÃšÃ›ÃœÃ§Ã‡Ã±Ã‘',
            'punctuation': r'""''â€“â€”â€¦â€šâ€žâ€¹â€ºÂ«Â»â€°â€±Â§Â¶â€ â€¡â€¢'
        }
        
        # Tesseract configuration
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        try:
            pytesseract.get_tesseract_version()
            logger.info("ðŸŽ“ Tesseract OCR armed for academic document warfare")
        except Exception as e:
            raise RuntimeError(f"Tesseract academic deployment failed: {e}")
    
    def determine_latex_strategy(self, quality_metrics: LaTeXQualityMetrics) -> Dict:
        """
        Choose optimal processing strategy based on LaTeX-aware quality assessment
        This is the strategic command center for academic document processing
        
        Args:
            quality_metrics: LaTeX quality assessment results
            
        Returns:
            Processing configuration optimized for LaTeX challenges
        """
        strategy = {
            'conversion_dpi': 300,
            'preprocessing_mode': 'basic',
            'ocr_configs': [],
            'enhancement_level': 'minimal',
            'latex_postprocessing': True,
            'mathematical_mode': False,
            'ligature_correction': True,
            'layout_reconstruction': False
        }
        
        # Adapt strategy based on LaTeX confidence
        if quality_metrics.latex_confidence >= 0.7:
            logger.info(f"ðŸŽ¯ HIGH LaTeX confidence ({quality_metrics.latex_confidence:.1%}) - deploying academic arsenal")
            strategy['latex_postprocessing'] = True
            strategy['ligature_correction'] = True
            
            # Mathematical content requires special handling
            if quality_metrics.math_density > 0.1:
                strategy['mathematical_mode'] = True
                logger.info(f"ðŸ“ Mathematical content detected ({quality_metrics.math_density:.1%}) - enabling math mode")
            
            # Complex layouts need reconstruction
            if quality_metrics.layout_complexity > 0.4:
                strategy['layout_reconstruction'] = True
                logger.info(f"ðŸ“Š Complex layout detected - enabling reconstruction")
        
        # Quality-based adjustments for LaTeX documents
        if quality_metrics.overall_quality == "HIGH":
            # High-quality LaTeX - preserve perfection
            strategy.update({
                'conversion_dpi': min(250, quality_metrics.base_resolution),  # Don't oversample perfection
                'preprocessing_mode': 'latex_gentle',
                'ocr_configs': ['latex_high_quality', 'mathematical_gentle'],
                'enhancement_level': 'none'
            })
            logger.info("ðŸ† HIGH quality LaTeX - using gentle academic extraction")
            
        elif quality_metrics.overall_quality == "MEDIUM":
            # Medium quality LaTeX - balanced academic approach
            strategy.update({
                'conversion_dpi': max(300, quality_metrics.base_resolution),
                'preprocessing_mode': 'latex_balanced',
                'ocr_configs': ['latex_standard', 'mathematical_standard', 'layout_aware'],
                'enhancement_level': 'moderate'
            })
            logger.info("âš–ï¸  MEDIUM quality LaTeX - using balanced academic extraction")
            
        elif quality_metrics.overall_quality == "LOW":
            # Low quality LaTeX - enhanced academic processing
            strategy.update({
                'conversion_dpi': max(400, quality_metrics.base_resolution * 1.3),
                'preprocessing_mode': 'latex_enhanced',
                'ocr_configs': ['latex_aggressive', 'mathematical_robust', 'layout_reconstruction', 'symbol_focused'],
                'enhancement_level': 'aggressive'
            })
            logger.info("ðŸ”§ LOW quality LaTeX - using enhanced academic extraction")
            
        else:  # GARBAGE quality
            # Nuclear option for destroyed academic documents
            strategy.update({
                'conversion_dpi': 600,
                'preprocessing_mode': 'latex_nuclear',
                'ocr_configs': ['latex_nuclear', 'mathematical_desperate', 'symbol_emergency', 'text_recovery'],
                'enhancement_level': 'nuclear'
            })
            logger.info("â˜¢ï¸  GARBAGE quality LaTeX - deploying academic nuclear option")
        
        return strategy
    
    def get_latex_ocr_configs(self, config_name: str) -> str:
        """
        Generate Tesseract configurations optimized for LaTeX challenges
        Each config is like a specialized weapon for different academic warfare scenarios
        
        Args:
            config_name: Configuration strategy name
            
        Returns:
            Tesseract configuration string
        """
        base_config = '--oem 3'
        
        config_map = {
            'latex_high_quality': f'{base_config} --psm 6',
            'mathematical_gentle': f'{base_config} --psm 8 -c tessedit_char_whitelist={self.latex_char_sets["basic_latin"]}{self.latex_char_sets["mathematical"]}{self.latex_char_sets["symbols"]}',
            'latex_standard': f'{base_config} --psm 6',
            'mathematical_standard': f'{base_config} --psm 6 -c tessedit_char_whitelist={self.latex_char_sets["basic_latin"]}{self.latex_char_sets["mathematical"]}{self.latex_char_sets["symbols"]}',
            'layout_aware': f'{base_config} --psm 4',
            'latex_aggressive': f'{base_config} --psm 3',
            'mathematical_robust': f'{base_config} --psm 1 -c tessedit_char_whitelist={self.latex_char_sets["basic_latin"]}{self.latex_char_sets["mathematical"]}{self.latex_char_sets["symbols"]}',
            'layout_reconstruction': f'{base_config} --psm 11',
            'symbol_focused': f'{base_config} --psm 8 -c tessedit_char_whitelist={self.latex_char_sets["symbols"]}{self.latex_char_sets["mathematical"]}',
            'latex_nuclear': f'{base_config} --psm 1',
            'mathematical_desperate': f'{base_config} --psm 13 -c tessedit_char_whitelist={self.latex_char_sets["basic_latin"]}{self.latex_char_sets["mathematical"]}{self.latex_char_sets["symbols"]}',
            'symbol_emergency': f'{base_config} --psm 8 -c tessedit_char_whitelist={self.latex_char_sets["symbols"]}',
            'text_recovery': f'{base_config} --psm 3'
        }
        
        return config_map.get(config_name, f'{base_config} --psm 6')
    
    def latex_aware_preprocessing(self, image: Image.Image, enhancement_level: str, quality_metrics: LaTeXQualityMetrics) -> Image.Image:
        """
        Apply LaTeX-aware image preprocessing
        This is where we respect academic typography while preparing for OCR warfare
        
        Args:
            image: PIL Image to process
            enhancement_level: Enhancement strategy
            quality_metrics: LaTeX quality metrics for guidance
            
        Returns:
            Enhanced PIL Image optimized for LaTeX content
        """
        try:
            if enhancement_level == 'none':
                return image
            
            # Convert to grayscale for processing
            if image.mode != 'L':
                processed = image.convert('L')
            else:
                processed = image.copy()
            
            # LaTeX-specific preprocessing strategies
            if enhancement_level == 'latex_gentle':
                # Minimal processing for high-quality LaTeX
                enhancer = ImageEnhance.Contrast(processed)
                processed = enhancer.enhance(1.05)  # Tiny boost
                
            elif enhancement_level == 'latex_balanced':
                # Balanced enhancement respecting typography
                enhancer = ImageEnhance.Contrast(processed)
                processed = enhancer.enhance(1.3)
                
                # Gentle sharpening for vector fonts
                processed = processed.filter(ImageFilter.UnsharpMask(radius=1, percent=110, threshold=2))
                
            elif enhancement_level == 'latex_enhanced':
                # Stronger enhancement while preserving mathematical symbols
                enhancer = ImageEnhance.Contrast(processed)
                processed = enhancer.enhance(1.8)
                
                # Mathematical symbol-aware sharpening
                processed = processed.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=1))
                
                # Light noise reduction
                cv_image = cv2.cvtColor(np.array(processed), cv2.COLOR_GRAY2BGR)
                denoised = cv2.fastNlMeansDenoising(cv_image, h=10)
                processed = Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY))
                
            elif enhancement_level == 'latex_nuclear':
                # Full nuclear treatment for destroyed academic documents
                cv_image = cv2.cvtColor(np.array(processed), cv2.COLOR_GRAY2BGR)
                
                # Aggressive noise reduction
                denoised = cv2.fastNlMeansDenoising(cv_image, h=20)
                processed = Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY))
                
                # Nuclear contrast enhancement
                enhancer = ImageEnhance.Contrast(processed)
                processed = enhancer.enhance(2.5)
                
                # Mathematical symbol preservation via morphological operations
                img_array = np.array(processed)
                kernel = np.ones((2, 2), np.uint8)
                processed_array = cv2.morphologyEx(img_array, cv2.MORPH_CLOSE, kernel)
                
                # Otsu thresholding for clean binary conversion
                _, binary = cv2.threshold(processed_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                processed = Image.fromarray(binary)
            
            return processed
            
        except Exception as e:
            logger.warning(f"LaTeX preprocessing failed: {e}")
            return image
    
    def multi_config_latex_ocr(self, image: Image.Image, ocr_configs: List[str], quality_metrics: LaTeXQualityMetrics) -> str:
        """
        Run OCR with multiple LaTeX-optimized configurations
        This is academic document processing with multiple specialized weapons
        
        Args:
            image: PIL Image to process
            ocr_configs: List of configuration names
            quality_metrics: LaTeX quality metrics for result weighting
            
        Returns:
            Best OCR result optimized for LaTeX content
        """
        results = []
        confidence_scores = []
        
        for config_name in ocr_configs:
            try:
                config_string = self.get_latex_ocr_configs(config_name)
                text = pytesseract.image_to_string(image, lang=self.lang, config=config_string)
                
                # Get confidence scores if available
                try:
                    data = pytesseract.image_to_data(image, lang=self.lang, config=config_string, output_type=pytesseract.Output.DICT)
                    confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                    avg_confidence = np.mean(confidences) if confidences else 0
                except:
                    avg_confidence = len(text.strip())  # Fallback: length-based scoring
                
                results.append(text.strip())
                confidence_scores.append(avg_confidence)
                
                logger.debug(f"OCR config {config_name}: {len(text)} chars, confidence: {avg_confidence:.1f}")
                
            except Exception as e:
                logger.debug(f"OCR config {config_name} failed: {e}")
                continue
        
        if not results:
            return ""
        
        # Weight results based on confidence and LaTeX-specific factors
        weighted_scores = []
        for i, (text, confidence) in enumerate(zip(results, confidence_scores)):
            score = confidence
            
            # Boost score for mathematical content detection
            if quality_metrics.math_density > 0.1:
                math_pattern = re.compile(r'[âˆ‘âˆ«âˆ‚âˆ‡Ã—Â±â‰¤â‰¥â‰ â‰ˆâˆžÂ°âˆšâˆÎ±Î²Î³Î´ÎµÎ¶Î·Î¸Î¹ÎºÎ»Î¼Î½Î¾Î¿Ï€ÏÏƒÏ„Ï…Ï†Ï‡ÏˆÏ‰]')
                math_matches = len(math_pattern.findall(text))
                score += math_matches * 10  # Bonus for mathematical symbols
            
            # Penalty for obvious OCR errors in academic context
            if 'ï¬' in text or 'ï¬‚' in text:  # Ligature artifacts
                score -= 5
            
            weighted_scores.append(score)
        
        # Return result with highest weighted score
        best_index = np.argmax(weighted_scores)
        best_result = results[best_index]
        
        logger.debug(f"Selected result with score {weighted_scores[best_index]:.1f}")
        return best_result
    
    def latex_postprocessing(self, text: str, quality_metrics: LaTeXQualityMetrics) -> str:
        """
        Apply LaTeX-specific post-processing to fix common OCR artifacts
        This is digital surgery for academic documents
        
        Args:
            text: Raw OCR output
            quality_metrics: LaTeX quality metrics for guidance
            
        Returns:
            Cleaned text with LaTeX artifacts corrected
        """
        try:
            cleaned_text = text
            
            # Fix common ligature corruptions
            ligature_fixes = {
                'ï¬': 'fi',
                'ï¬‚': 'fl',
                'ï¬€': 'ff',
                'ï¬ƒ': 'ffi',
                'ï¬„': 'ffl',
                'ï¬†': 'st'
            }
            
            for corrupted, correct in ligature_fixes.items():
                cleaned_text = cleaned_text.replace(corrupted, correct)
            
            # Fix common mathematical symbol corruptions
            math_symbol_fixes = {
                'Ã¢â‚¬"': 'â€“',      # En dash
                'Ã¢â‚¬â„¢': ''',      # Right single quote
                'Ã¢â‚¬Å“': '"',      # Left double quote
                'Ã¢â‚¬\x9d': '"',   # Right double quote
                'Ã‚Â±': 'Â±',       # Plus-minus
                'Ã¢Ë†'': 'âˆ‘',      # Summation
                'Ã¢Ë†Â«': 'âˆ«',      # Integral
                'Ã¢Ë†â€š': 'âˆ‚',      # Partial derivative
                'Ã¢Ë†Å¾': 'âˆž',      # Infinity
                'ÃŽÂ±': 'Î±',       # Alpha
                'ÃŽÂ²': 'Î²',       # Beta
                'ÃŽÂ³': 'Î³',       # Gamma
                'ÃŽÂ´': 'Î´',       # Delta
                'ÃŽÂµ': 'Îµ',       # Epsilon
                'ÃŽÂ¸': 'Î¸',       # Theta
                'ÃŽÂ»': 'Î»',       # Lambda
                'ÃŽÂ¼': 'Î¼',       # Mu
                'Ãâ‚¬': 'Ï€',       # Pi
                'Ãâ€°': 'Ï‰'        # Omega
            }
            
            for corrupted, correct in math_symbol_fixes.items():
                cleaned_text = cleaned_text.replace(corrupted, correct)
            
            # Reconstruct hyphenated words (common in LaTeX justified text)
            cleaned_text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', cleaned_text)
            
            # Fix spacing around mathematical operators
            cleaned_text = re.sub(r'\s*([=+\-*/])\s*', r' \1 ', cleaned_text)
            
            # Clean up excessive whitespace while preserving paragraph structure
            cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)  # Multiple newlines to double
            cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)  # Multiple spaces to single
            
            # Fix common citation formatting
            cleaned_text = re.sub(r'\[\s*(\d+)\s*\]', r'[\1]', cleaned_text)  # Clean up citation brackets
            
            logger.debug(f"Post-processing applied: {len(text)} -> {len(cleaned_text)} characters")
            return cleaned_text.strip()
            
        except Exception as e:
            logger.warning(f"LaTeX post-processing failed: {e}")
            return text
    
    def convert_pdf_to_images(self, pdf_path: str, target_dpi: int) -> List[Image.Image]:
        """Convert PDF to images with specified DPI"""
        try:
            logger.info(f"ðŸ”„ Converting LaTeX PDF at {target_dpi} DPI...")
            page_images = pdf2image.convert_from_path(
                pdf_path,
                dpi=target_dpi,
                fmt='PNG',
                thread_count=1,
                grayscale=False,
                use_pdftocairo=True
            )
            logger.info(f"âœ… Converted {len(page_images)} pages successfully")
            return page_images
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            return []
    
    def process_latex_pdf(self, pdf_path: str, output_path: str = None) -> str:
        """
        The master orchestrator for LaTeX-aware PDF processing
        This is where academic typography meets adaptive OCR warfare
        
        Args:
            pdf_path: Path to PDF file
            output_path: Output text file path
            
        Returns:
            Extracted text optimized for LaTeX content
        """
        logger.info(f"ðŸŽ“ Starting LaTeX-aware PDF processing: {pdf_path}")
        
        # Step 1: Quality assessment with LaTeX-specific analysis
        logger.info("ðŸ”¬ Conducting LaTeX-aware quality assessment...")
        sample_images = self.convert_pdf_to_images(pdf_path, 200)
        
        if not sample_images:
            logger.error("Failed to convert PDF for quality assessment")
            return ""
        
        quality_metrics = self.latex_detective.assess_latex_quality(sample_images[0])
        
        # Step 2: Determine LaTeX-optimized processing strategy
        strategy = self.determine_latex_strategy(quality_metrics)
        
        # Step 3: Convert at optimal DPI
        if strategy['conversion_dpi'] != 200:
            page_images = self.convert_pdf_to_images(pdf_path, strategy['conversion_dpi'])
        else:
            page_images = sample_images
        
        if not page_images:
            logger.error("Failed to convert PDF at target DPI")
            return ""
        
        # Step 4: Process each page with LaTeX-aware strategy
        all_text = []
        
        for page_num, page_image in enumerate(page_images):
            logger.info(f"ðŸ“„ Processing page {page_num + 1}/{len(page_images)} with LaTeX-aware {strategy['enhancement_level']} enhancement")
            
            # Apply LaTeX-aware preprocessing
            enhanced_image = self.latex_aware_preprocessing(
                page_image, 
                strategy['enhancement_level'], 
                quality_metrics
            )
            
            # Run multi-config LaTeX-optimized OCR
            page_text = self.multi_config_latex_ocr(
                enhanced_image, 
                strategy['ocr_configs'], 
                quality_metrics
            )
            
            # Apply LaTeX-specific post-processing
            if strategy['latex_postprocessing'] and page_text:
                page_text = self.latex_postprocessing(page_text, quality_metrics)
            
            if page_text:
                all_text.append(f"=== PAGE {page_num + 1} ===\n{page_text}\n")
                logger.info(f"âœ… Page {page_num + 1}: {len(page_text)} characters extracted")
            else:
                logger.warning(f"âš ï¸  No text found on page {page_num + 1}")
        
        # Combine results
        combined_text = "\n".join(all_text)
        
        # Save results with metadata
        if output_path:
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(f"LaTeX Quality Assessment: {quality_metrics}\n")
                    f.write(f"Processing Strategy: {strategy}\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(combined_text)
                logger.info(f"ðŸ’¾ LaTeX results saved to: {output_path}")
            except Exception as e:
                logger.error(f"Failed to save results: {e}")
        
        logger.info(f"ðŸŽ¯ LaTeX-aware processing complete! Total characters: {len(combined_text)}")
        return combined_text

def main():
    """
    Command line interface for the LaTeX-aware adaptive OCR destroyer
    """
    parser = argparse.ArgumentParser(
        description="LaTeX-aware adaptive PDF OCR with quality-based processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python latex_ocr.py academic_paper.pdf
    python latex_ocr.py thesis.pdf --output extracted.txt
    python latex_ocr.py math_document.pdf --lang eng+osd --tesseract-path /usr/bin/tesseract
        """
    )
    
    parser.add_argument('pdf_path', help='Path to PDF file (optimized for LaTeX documents)')
    parser.add_argument('--output', '-o', help='Output text file path')
    parser.add_argument('--lang', default='eng', help='OCR language (eng, spa, fra, etc.)')
    parser.add_argument('--tesseract-path', help='Path to tesseract executable')
    
    args = parser.parse_args()
    
    # Validate input
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        return 1
    
    # Default output path
    if not args.output:
        pdf_stem = Path(args.pdf_path).stem
        args.output = f"{pdf_stem}_latex_extracted.txt"
    
    try:
        # Initialize LaTeX-aware processor
        processor = LaTeXAwareOCRProcessor(
            tesseract_path=args.tesseract_path,
            lang=args.lang
        )
        
        # Process with LaTeX-aware intelligence
        extracted_text = processor.process_latex_pdf(args.pdf_path, args.output)
        
        if extracted_text:
            print(f"\nðŸŽ‰ Academic mission accomplished! Extracted {len(extracted_text)} characters")
            print(f"ðŸ“ Results saved to: {args.output}")
            
            # Preview the academic spoils
            print("\nðŸ“– Preview of extracted text:")
            print("=" * 60)
            preview = extracted_text[:750] + "..." if len(extracted_text) > 750 else extracted_text
            print(preview)
        else:
            print("ðŸ’€ No text extracted - check PDF format and tesseract installation")
    
    except Exception as e:
        logger.error(f"LaTeX-aware processing failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
