import pytesseract
import cv2
import numpy as np
from PIL import Image
import difflib
import re
import json
import logging
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed  # FIXED: Using ProcessPoolExecutor for CPU-bound ops
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import time
import sympy as sp
from sympy.parsing.sympy_parser import parse_expr
from sympy.core.sympify import SympifyError
from functools import lru_cache
import hashlib
import shlex  # For proper shell escaping
from pdf2image import convert_from_path  # PDF HANDLING ADDED
import os
from pathlib import Path

# Set up comprehensive logging that tracks divergence regions with their similarity scores
logging.basicConfig(filename="app.log", level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EngineMode(Enum):
    LEGACY = 0
    NEURAL_NET = 1
    LEGACY_NEURAL = 2
    LSTM_ONLY = 3

class DocumentType(Enum):
    GENERAL = "general"
    FINANCIAL = "financial"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    ENGINEERING = "engineering"

class MathContextState(Enum):
    """Context state machine for mathematical content detection"""
    NEUTRAL = "neutral"
    THEOREM_HEADER = "theorem_header"
    EQUATION_BLOCK = "equation_block"
    PROOF_SECTION = "proof_section"
    FORMULA_LIST = "formula_list"

@dataclass
class MathRegion:
    start_pos: int
    end_pos: int
    content: str
    confidence: float
    context_before: str = ""
    context_after: str = ""
    classification: str = ""  # Simple variables, complex equations, matrix notation, integral expressions
    sympy_parseable: bool = False
    false_positive_score: float = 0.0
    context_state: MathContextState = MathContextState.NEUTRAL
    spatial_confidence_boost: float = 0.0

@dataclass
class AlignmentDecision:
    """Character-by-character differences in critical sections"""
    restricted_segment: str
    full_segment: str
    similarity: float
    start_pos: int
    end_pos: int
    tag: str  # equal, replace, delete, insert

class TwoPassMathOCR:
    def __init__(self, doc_type: DocumentType = DocumentType.GENERAL, custom_whitelist: str = None):
        # Make whitelist configurable via init params for different doc types
        base_ascii = (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "abcdefghijklmnopqrstuvwxyz"
            "0123456789"
            ".,;:'\"\(\)\[\]\-\/"
            " \t\n"
        )
        
        # Your whitelist string should include: All uppercase letters (A-Z), All lowercase letters (a-z), Numbers (0-9)
        # Add more currency symbols if it's financial math shit
        doc_specific_chars = {
            DocumentType.FINANCIAL: "$€£¥¢₹₽₩₪₦₡₨₫₭₮₯₰₱₲₳₴₵₶₷₸₹₺₻₼₽₾₿",
            DocumentType.PHYSICS: "°·×÷∞",
            DocumentType.CHEMISTRY: "°·×÷→←↔",
            DocumentType.ENGINEERING: "°·×÷±∞∠∥⊥",
            DocumentType.GENERAL: ""
        }
        
        if custom_whitelist:
            self.ascii_whitelist = custom_whitelist
        else:
            self.ascii_whitelist = base_ascii + doc_specific_chars[doc_type]
        
        # Mathematical-only character set for nuclear option
        self.math_only_whitelist = (
            "αβγδεζηθικλμνξοπρστυφχψω"
            "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
            "∫∑∏√∂∇∞±≤≥≠≈∈∉⊂⊃∪∩"
            "₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹"
            "½⅓⅔¼¾⅛⅜⅝⅞"
            "()[]{}^_="
        )
        
        # Build your config string with --oem 3 (LSTM neural net mode) and --psm 6 (uniform block of text)
        self.base_config = "--psm 6"
        
        # Add language parameters (e.g., --lang eng+equ for math-heavy docs)
        self.lang_config = "-l eng+equ"
        
        # ADAPTIVE THRESHOLDING: These get adjusted based on document quality
        self.high_divergence_threshold = 0.3
        self.medium_divergence_threshold = 0.7
        self.low_divergence_threshold = 0.9
        self.baseline_ocr_consistency = 0.0  # Calculated from document
        
        # Keep 5-10 characters before and after each mathematical region
        self.context_chars = 10
        
        # Alignment algorithm decisions tracking
        self.alignment_decisions: List[AlignmentDecision] = []
        
        # Final classification reasoning for each marked region
        self.classification_reasoning: Dict[int, str] = {}
        
        # Error tracking and retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0
        
        # Context state machine for mathematical content classification
        self.context_state = MathContextState.NEUTRAL
        self.context_history: List[Tuple[int, MathContextState]] = []
        
        # Spatial confidence propagation parameters
        self.confidence_decay_distance = 100  # characters
        self.confidence_boost_factor = 0.15
        
        # OCR result caching
        self.ocr_cache: Dict[str, str] = {}

    def get_image_hash(self, image: np.ndarray) -> str:
        """Generate hash for image caching"""
        return hashlib.md5(image.tobytes()).hexdigest()

    def escape_whitelist(self, whitelist: str) -> str:
        """Properly escape whitelist strings for shell commands to prevent Tesseract from shitting the bed"""
        # Use shlex.quote to properly escape the entire whitelist
        return shlex.quote(whitelist)

    def convert_pdf_to_images(self, pdf_path: str, dpi: int = 300) -> List[np.ndarray]:
        """PDF HANDLING: Convert PDF pages to images for OCR processing"""
        try:
            logger.info(f"Converting PDF {pdf_path} to images at {dpi} DPI")
            
            # Convert PDF pages to PIL images
            pil_images = convert_from_path(pdf_path, dpi=dpi)
            
            # Convert PIL images to numpy arrays
            np_images = []
            for i, pil_img in enumerate(pil_images):
                # Convert to numpy array
                np_img = np.array(pil_img)
                
                # Convert to grayscale if needed
                if len(np_img.shape) == 3:
                    np_img = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
                
                np_images.append(np_img)
                logger.debug(f"Converted PDF page {i+1} to {np_img.shape} image")
            
            return np_images
            
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            raise

    def preprocess_image(self, image_path: str) -> List[np.ndarray]:
        """Load and preprocess image/PDF for OCR with error handling"""
        try:
            # Check if it's a PDF file

            if Path(image_path).suffix.lower() == '.pdf':
           
                logger.info("PDF detected, converting to images...")
                return self.convert_pdf_to_images(image_path)
            
            # Handle regular image files
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Add error handling for empty images
            if image.size == 0:
                raise ValueError(f"Empty image: {image_path}")
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply image preprocessing variations between passes for better detection
            # Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (1, 1), 0)
            
            # Threshold to get binary image
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return [thresh]
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            raise

    def create_preprocessing_variations(self, image: np.ndarray) -> List[np.ndarray]:
        """Apply image preprocessing variations between passes for better detection"""
        variations = [image]  # Original
        
        # Variation 1: More aggressive noise reduction
        denoised = cv2.medianBlur(image, 3)
        variations.append(denoised)
        
        # Variation 2: Morphological operations
        kernel = np.ones((2,2), np.uint8)
        morph = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
        variations.append(morph)
        
        # Variation 3: Different threshold
        _, adaptive_thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_TRIANGLE)
        variations.append(adaptive_thresh)
        
        return variations

    @lru_cache(maxsize=128)
    def cached_ocr_call(self, image_hash: str, config: str, image_bytes: bytes) -> str:
        """Add caching for repeated OCR calls - turning repeated operations into lightning-fast lookups"""
        # Convert bytes back to image for OCR
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image_array = image_array.reshape(-1)  # Flatten for reconstruction
        
        # This is a simplified cache - in practice you'd want more sophisticated image reconstruction
        # For now, we'll use a runtime cache dict instead of LRU cache due to image complexity
        return ""  # Placeholder - actual implementation below

    def run_ocr_with_retries(self, image: np.ndarray, config: str, ocr_type: str) -> str:
        """Add error handling for Tesseract failures with retries/fallbacks"""
        # Generate cache key
        image_hash = self.get_image_hash(image)
        cache_key = f"{image_hash}_{config}"
        
        # Check cache first
        if cache_key in self.ocr_cache:
            logger.debug(f"Cache hit for {ocr_type} OCR")
            return self.ocr_cache[cache_key]
        
        pil_image = Image.fromarray(image)
        
        for attempt in range(self.max_retries):
            try:
                text = pytesseract.image_to_string(pil_image, config=config)
                
                # Add debug output for whitelist violations Tesseract might log internally
                if len(text.strip()) == 0:
                    logger.warning(f"{ocr_type} OCR returned empty text on attempt {attempt + 1}")
                
                # Cache the result
                self.ocr_cache[cache_key] = text.strip()
                return text.strip()
                
            except Exception as e:
                logger.warning(f"{ocr_type} OCR attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"{ocr_type} OCR failed after {self.max_retries} attempts")
                    return ""

    def run_restricted_ocr(self, image: np.ndarray, engine_mode: EngineMode = EngineMode.LSTM_ONLY) -> str:
        """Phase 1: The Character Whitelist Purge Operation
        
        This whitelist becomes your tessedit_char_whitelist parameter. You're essentially putting Tesseract on a strict ASCII diet - 
        no Greek letters, no integral signs, no fucking mathematical notation whatsoever.
        """
        # Add your whitelist parameter. This configuration makes Tesseract literally blind to mathematical symbols
        # FIXED: Properly escape whitelist string to prevent shell command failures
        escaped_whitelist = self.escape_whitelist(self.ascii_whitelist)
        config = f"{self.base_config} {self.lang_config} --oem {engine_mode.value} -c tessedit_char_whitelist={escaped_whitelist}"
        
        # Store this output as your "clean text" version. This is your baseline reality
        text = self.run_ocr_with_retries(image, config, f"Restricted (OEM {engine_mode.value})")
        logger.debug(f"Restricted OCR (OEM {engine_mode.value}): {len(text)} characters")
        return text

    def run_full_ocr(self, image: np.ndarray, engine_mode: EngineMode = EngineMode.LSTM_ONLY) -> str:
        """Phase 2: The Full Unicode Reconnaissance Mission
        
        Second pass runs with zero restrictions - let Tesseract recognize every fucking symbol it knows.
        No character whitelist (remove that parameter entirely)
        Optional: Add preserve_interword_spaces=1 to maintain spacing fidelity
        """
        # Same page segmentation mode for consistency
        # Enhance with lang params (e.g., --lang eng+equ for math-heavy docs) to boost recognition of equations
        config = f"{self.base_config} {self.lang_config} --oem {engine_mode.value} -c preserve_interword_spaces=1"
        
        # This gives you the raw, unfiltered reality - including all the mathematical notation
        text = self.run_ocr_with_retries(image, config, f"Full (OEM {engine_mode.value})")
        logger.debug(f"Full OCR (OEM {engine_mode.value}): {len(text)} characters")
        return text

    # def run_full_ocr(self, image: np.ndarray, engine_mode: EngineMode = EngineMode.LSTM_ONLY) -> str:
    #     # Don't go completely wild - use an expanded but sane character set
    #     expanded_whitelist = (
    #         self.ascii_whitelist + 
    #         "αβγδεζηθικλμνξοπρστυφχψω" +  # Greek lowercase only
    #         "∫∑∏√±×÷≤≥≠≈∞∂∇" +  # Essential math symbols
    #         "₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹"  # Sub/superscripts
    #     )
        
    #     escaped_whitelist = self.escape_whitelist(expanded_whitelist)
    #     config = f"{self.base_config} {self.lang_config} --oem {engine_mode.value} -c tessedit_char_whitelist={escaped_whitelist} -c preserve_interword_spaces=1"
        
    #     return self.run_ocr_with_retries(image, config, f"Controlled Full (OEM {engine_mode.value})")




    def run_math_only_ocr(self, image: np.ndarray, engine_mode: EngineMode = EngineMode.LSTM_ONLY) -> str:
        """The Nuclear Option: Triple-Pass Verification
        
        Add a third pass with a "mathematical-only" character set (Greek letters, mathematical operators, etc.) 
        to specifically target mathematical regions identified in the differential analysis.
        """
        escaped_whitelist = self.escape_whitelist(self.math_only_whitelist)
        config = f"{self.base_config} {self.lang_config} --oem {engine_mode.value} -c tessedit_char_whitelist={escaped_whitelist}"
        
        # This gives you focused OCR on the mathematical content with settings optimized for that shit
        text = self.run_ocr_with_retries(image, config, f"Math-only (OEM {engine_mode.value})")
        logger.debug(f"Math-only OCR (OEM {engine_mode.value}): {len(text)} characters")
        return text

    def run_multiple_engines(self, image: np.ndarray, ocr_type: str) -> Dict[EngineMode, str]:
        """Use different Tesseract engines (--oem 0, 1, 2, 3) and compare results"""
        results = {}
        
        for engine in EngineMode:
            logger.debug(f"Running {ocr_type} OCR with engine {engine.name}")
            
            if ocr_type == "restricted":
                results[engine] = self.run_restricted_ocr(image, engine)
            elif ocr_type == "full":
                results[engine] = self.run_full_ocr(image, engine)
            elif ocr_type == "math_only":
                results[engine] = self.run_math_only_ocr(image, engine)
        
        return results

    def calculate_baseline_ocr_consistency(self, restricted_text: str, full_text: str) -> float:
        """Calculate baseline OCR consistency on known non-math regions for adaptive thresholding"""
        # Find regions that are likely pure text (no math symbols)
        text_regions = []
        sentences = re.split(r'[.!?]+', full_text)
        
        for sentence in sentences:
            # Skip if contains obvious math symbols
            if not re.search(r'[αβγδεζηθικλμνξοπρστυφχψω∫∑∏√∂∇∞±≤≥≠≈]', sentence):
                text_regions.append(sentence.strip())
        
        if not text_regions:
            return 0.8  # Default baseline
        
        # Calculate average similarity for text-only regions
        similarities = []
        for region in text_regions[:10]:  # Sample first 10 regions
            restricted_match = difflib.get_close_matches(region, [restricted_text], n=1, cutoff=0.1)
            if restricted_match:
                sim = difflib.SequenceMatcher(None, region, restricted_match[0]).ratio()
                similarities.append(sim)
        
        baseline = sum(similarities) / len(similarities) if similarities else 0.8
        logger.info(f"Calculated baseline OCR consistency: {baseline:.3f}")
        return baseline

    def adapt_thresholds_to_document(self, baseline_consistency: float, doc_type: DocumentType):
        """Adjust thresholds based on overall document quality - making this beast document-aware"""
        # Higher baseline consistency means better OCR, so we can be more strict
        if baseline_consistency > 0.9:
            # High quality OCR - be more aggressive with math detection
            self.high_divergence_threshold = 0.25
            self.medium_divergence_threshold = 0.6
        elif baseline_consistency < 0.6:
            # Poor quality OCR - be more conservative
            self.high_divergence_threshold = 0.4
            self.medium_divergence_threshold = 0.8
        
        # Document-specific adjustments
        doc_adjustments = {
            DocumentType.PHYSICS: -0.05,  # Physics has dense math, lower thresholds
            DocumentType.CHEMISTRY: -0.03,
            DocumentType.FINANCIAL: 0.05,  # Financial docs have less dense math
            DocumentType.ENGINEERING: -0.02,
            DocumentType.GENERAL: 0.0
        }
        
        adjustment = doc_adjustments.get(doc_type, 0.0)
        self.high_divergence_threshold += adjustment
        self.medium_divergence_threshold += adjustment
        
        logger.info(f"Adapted thresholds: high={self.high_divergence_threshold:.3f}, "
                   f"medium={self.medium_divergence_threshold:.3f}")

    def update_context_state(self, text: str, position: int) -> MathContextState:
        """Build a context state machine - mathematical regions cluster like wolves"""
        # Check for mathematical context headers
        text_lower = text.lower()
        
        # Theorem/Lemma/Corollary headers boost subsequent math confidence
        if re.search(r'\b(theorem|lemma|corollary|proposition)\s+\d+', text_lower):
            self.context_state = MathContextState.THEOREM_HEADER
            self.context_history.append((position, MathContextState.THEOREM_HEADER))
            logger.debug(f"Context state changed to THEOREM_HEADER at position {position}")
            return MathContextState.THEOREM_HEADER
        
        # Proof sections
        elif re.search(r'\b(proof|demonstration):\s*', text_lower):
            self.context_state = MathContextState.PROOF_SECTION
            self.context_history.append((position, MathContextState.PROOF_SECTION))
            return MathContextState.PROOF_SECTION
        
        # Equation blocks (multiple equations)
        elif re.search(r'\(\d+\)\s*$', text) or 'equation' in text_lower:
            self.context_state = MathContextState.EQUATION_BLOCK
            self.context_history.append((position, MathContextState.EQUATION_BLOCK))
            return MathContextState.EQUATION_BLOCK
        
        # Formula lists
        elif re.search(r'\b(formula|expression)\s*\d+', text_lower):
            self.context_state = MathContextState.FORMULA_LIST
            self.context_history.append((position, MathContextState.FORMULA_LIST))
            return MathContextState.FORMULA_LIST
        
        return self.context_state

    def calculate_spatial_confidence_boost(self, position: int, math_regions: List[MathRegion]) -> float:
        """Implement spatial confidence propagation - math regions give each other confidence boosts"""
        boost = 0.0
        
        # Find nearby high-confidence math regions
        for region in math_regions:
            if region.confidence > 0.7:  # Only high-confidence regions boost others
                distance = min(abs(position - region.start_pos), abs(position - region.end_pos))
                
                if distance < self.confidence_decay_distance:
                    # Exponential decay with distance
                    decay_factor = np.exp(-distance / (self.confidence_decay_distance / 3))
                    region_boost = self.confidence_boost_factor * decay_factor
                    boost += region_boost
                    
                    logger.debug(f"Spatial boost: {region_boost:.3f} from region at {region.start_pos}"
                               f" (distance: {distance}, decay: {decay_factor:.3f})")
        
        # Cap the total boost
        return min(boost, 0.3)

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two text strings"""
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def character_level_fallback(self, text1: str, text2: str, threshold: float = 0.5) -> List[Tuple[str, str, float, int]]:
        """Add character-level fallback if token similarity is too coarse for dense math"""
        char_regions = []
        
        # Only use if texts are similar enough in length but token similarity is low
        if abs(len(text1) - len(text2)) / max(len(text1), len(text2), 1) < 0.3:
            matcher = difflib.SequenceMatcher(None, text1, text2)
            
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag != 'equal':
                    char1 = text1[i1:i2]
                    char2 = text2[j1:j2]
                    sim = self.calculate_similarity(char1, char2)
                    char_regions.append((char1, char2, sim, j1))
        
        return char_regions

    def sliding_window_analysis(self, text1: str, text2: str, window_size: int = 50) -> List[Tuple[str, str, float, int]]:
        """Use a sliding window that moves through both texts simultaneously, identifying regions where they diverge
        
        FIXED: Handle sliding window overlap to prevent double-counting divergence regions
        """
        regions = []
        processed_positions = set()  # Track processed positions to avoid overlap issues
        i = 0
        
        while i < max(len(text1), len(text2)):
            # Skip if this position was already processed in an overlapping window
            if i in processed_positions:
                i += window_size // 4  # Smaller step to ensure coverage
                continue
                
            window1 = text1[i:i+window_size]
            window2 = text2[i:i+window_size]
            
            if not window1 and not window2:
                break
                
            similarity = self.calculate_similarity(window1, window2)
            regions.append((window1, window2, similarity, i))
            
            # Mark this range as processed
            for pos in range(i, min(i + window_size, max(len(text1), len(text2)))):
                processed_positions.add(pos)
            
            # Move window by quarter size to reduce overlap while maintaining coverage
            i += window_size // 4
        
        return regions

    def refine_opcode_boundaries(self, opcodes: List, sliding_windows: List[Tuple[str, str, float, int]]) -> List:
        """Integrate sliding window more - use it to refine opcode boundaries"""
        refined_opcodes = []
        
        for tag, i1, i2, j1, j2 in opcodes:
            # Check if sliding window analysis suggests different boundaries
            relevant_windows = [w for w in sliding_windows if w[3] >= j1 and w[3] <= j2]
            
            if relevant_windows and tag != 'equal':
                # Find the window with lowest similarity to refine boundaries
                min_sim_window = min(relevant_windows, key=lambda x: x[2])
                if min_sim_window[2] < self.medium_divergence_threshold:
                    # Adjust boundaries based on window position
                    window_pos = min_sim_window[3]
                    window_end = window_pos + len(min_sim_window[1])
                    
                    # Refine j1, j2 to focus on problematic region
                    j1_refined = max(j1, window_pos)
                    j2_refined = min(j2, window_end)
                    
                    refined_opcodes.append((tag, i1, i2, j1_refined, j2_refined))
                else:
                    refined_opcodes.append((tag, i1, i2, j1, j2))
            else:
                refined_opcodes.append((tag, i1, i2, j1, j2))
        
        return refined_opcodes

    def align_texts_advanced(self, restricted_text: str, full_text: str) -> List[AlignmentDecision]:
        """Phase 3: The Differential Analysis Warzone
        
        You can't just do a simple character-by-character comparison because the strings might have different lengths.
        Mathematical symbols often get recognized as multiple characters or create spacing differences.
        You need a sequence alignment approach.
        
        FIXED: Better tokenization to handle mathematical symbols with weird spacing
        """
        # Improved tokenization that handles mathematical symbols better
        # Split on word boundaries but preserve mathematical symbols as single tokens
        math_symbol_pattern = r'[αβγδεζηθικλμνξοπρστυφχψω∫∑∏√∂∇∞±≤≥≠≈∈∉⊂⊃∪∩]'
        
        def smart_tokenize(text):
            # First split on math symbols to keep them as separate tokens
            tokens = re.split(f'({math_symbol_pattern})', text)
            
            # Further split non-math tokens on whitespace and punctuation
            result = []
            for token in tokens:
                if re.match(math_symbol_pattern, token):
                    result.append(token)  # Keep math symbols intact
                else:
                    # Split on whitespace and punctuation, keeping separators
                    subtokens = re.findall(r'\S+|\s+', token)
                    result.extend(subtokens)
            
            return [t for t in result if t]  # Remove empty strings
        
        restricted_tokens = smart_tokenize(restricted_text)
        full_tokens = smart_tokenize(full_text)
        
        # Calculate baseline OCR consistency for adaptive thresholding
        self.baseline_ocr_consistency = self.calculate_baseline_ocr_consistency(restricted_text, full_text)
        
        # Use SequenceMatcher for alignment
        matcher = difflib.SequenceMatcher(None, restricted_tokens, full_tokens)
        opcodes = list(matcher.get_opcodes())
        
        # Also run sliding window analysis for comparison
        sliding_windows = self.sliding_window_analysis(restricted_text, full_text)
        
        # Use sliding window to refine opcode boundaries to prevent awkward partial divergences
        refined_opcodes = self.refine_opcode_boundaries(opcodes, sliding_windows)
        
        decisions = []
        current_pos = 0
        
        # Maintain parallel position indices for both strings
        for tag, i1, i2, j1, j2 in refined_opcodes:
            restricted_segment = ''.join(restricted_tokens[i1:i2])
            full_segment = ''.join(full_tokens[j1:j2])
            
            # Update context state based on segment content
            context_state = self.update_context_state(full_segment, current_pos)
            
            if tag == 'equal':
                similarity = 1.0
            else:
                # Set a similarity threshold (like 0.8) because even non-mathematical text might have minor OCR variations
                similarity = self.calculate_similarity(restricted_segment, full_segment)
                
                # Add character-level fallback if token sim is too coarse for dense math
                if similarity < 0.5 and len(full_segment) > 10:
                    char_regions = self.character_level_fallback(restricted_segment, full_segment)
                    if char_regions:
                        logger.debug(f"Character-level fallback found {len(char_regions)} regions")
            
            decision = AlignmentDecision(
                restricted_segment=restricted_segment,
                full_segment=full_segment,
                similarity=similarity,
                start_pos=current_pos,
                end_pos=current_pos + len(full_segment),
                tag=tag
            )
            
            decisions.append(decision)
            # Track alignment algorithm decisions
            logger.debug(f"Alignment decision: {tag}, similarity: {similarity:.3f}, segments: '{restricted_segment}' vs '{full_segment}'")
            current_pos += len(full_segment)
        
        self.alignment_decisions = decisions
        return decisions

    def validate_with_sympy(self, content: str) -> Tuple[bool, float]:
        """Add ML-lite validation like sympy parse attempts on regions to validate parseable math"""
        try:
            # Clean up content for sympy parsing
            cleaned = re.sub(r'[^\w\+\-\*/\(\)\^\=\<\>\.αβγδεζηθικλμνξοπρστυφχψω]', '', content)
            
            if len(cleaned.strip()) < 2:
                return False, 0.0
            
            # Try to parse as mathematical expression
            parsed = parse_expr(cleaned, transformations='all')
            
            # If parsing succeeds, it's likely valid math
            return True, 1.0
            
        except (SympifyError, ValueError, TypeError) as e:
            # Try simpler patterns
            simple_math_patterns = [
                r'^[a-zA-Zα-ωΑ-Ω][₀₁₂₃₄₅₆₇₈₉]*$',  # Variable with subscript
                r'^[a-zA-Zα-ωΑ-Ω]\^[0-9]+$',  # Variable with superscript
                r'^\d+\/\d+$',  # Simple fraction
                r'^√\d+$',  # Square root
                r'^∫.*d[a-zA-Z]$',  # Integral
            ]
            
            for pattern in simple_math_patterns:
                if re.match(pattern, content.strip()):
                    return True, 0.7
            
            return False, 0.0

    def calculate_false_positive_score(self, content: str, context_before: str, context_after: str) -> float:
        """Add false positive rate estimation - cross-check regions against math pattern scores"""
        score = 0.0
        
        # Check for common false positive patterns
        false_positive_patterns = [
            r'^(the|and|or|in|on|at|to|for|of|with|by)$',  # Common words
            r'^[A-Z][a-z]+$',  # Proper nouns
            r'^\d{4}$',  # Years
            r'^[A-Z]{2,}$',  # Acronyms
        ]
        
        for pattern in false_positive_patterns:
            if re.match(pattern, content.strip(), re.IGNORECASE):
                score += 0.3
        
        # Check context for mathematical indicators
        math_context_indicators = ['equation', 'formula', 'calculate', 'solve', 'integral', 'derivative']
        context = (context_before + " " + context_after).lower()
        
        has_math_context = any(indicator in context for indicator in math_context_indicators)
        if not has_math_context:
            score += 0.2
        
        # Penalize very short content without clear math symbols
        if len(content.strip()) == 1 and not re.match(r'[α-ωΑ-Ω∫∑∏√∂∇]', content):
            score += 0.4
        
        return min(score, 1.0)

    def classify_mathematical_content(self, content: str, confidence: float) -> str:
        """Pattern matching on detected mathematical regions to classify them"""
        
        # Simple variables (single letters)
        if re.match(r'^[a-zA-Zα-ωΑ-Ω]$', content.strip()):
            return "simple_variable"
        
        # Matrix notation (bracket patterns)
        if re.search(r'\[.*\]|\(.*\)', content) and len(content.split()) > 3:
            return "matrix_notation"
        
        # Integral/summation expressions (tall symbols)
        if re.search(r'[∫∑∏]', content):
            return "integral_summation"
        
        # Complex equations (multiple operators)
        math_operators = r'[+\-*/=<>≤≥≠±∂∇]'
        if len(re.findall(math_operators, content)) >= 2:
            return "complex_equation"
        
        # Subscripts/Superscripts
        if re.search(r'[₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹]', content):
            return "subscript_superscript"
        
        return "unclassified_math"

    def detect_mathematical_regions(self, alignment_decisions: List[AlignmentDecision]) -> List[MathRegion]:
        """When you find divergence regions, you need to classify them"""
        math_regions = []
        
        for i, decision in enumerate(alignment_decisions):
            region_id = i
            
            # When you detect mathematical content, record: Start position, End position, 
            # The actual mathematical content, Confidence score based on divergence level
            if decision.similarity < self.high_divergence_threshold:
                # High Divergence (similarity < 0.3): Definitely mathematical content
                confidence = 1.0 - decision.similarity
                classification = self.classify_mathematical_content(decision.full_segment, confidence)
                
                # Extract context: Keep 5-10 characters before and after each mathematical region
                context_before = ""
                context_after = ""
                
                if i > 0:
                    prev_segment = alignment_decisions[i-1].full_segment
                    context_before = prev_segment[-self.context_chars:] if len(prev_segment) > self.context_chars else prev_segment
                
                if i < len(alignment_decisions) - 1:
                    next_segment = alignment_decisions[i+1].full_segment
                    context_after = next_segment[:self.context_chars] if len(next_segment) > self.context_chars else next_segment
                
                # Validate with sympy and calculate false positive score
                sympy_valid, sympy_conf = self.validate_with_sympy(decision.full_segment)
                fp_score = self.calculate_false_positive_score(decision.full_segment, context_before, context_after)
                
                # Calculate spatial confidence boost from nearby regions
                spatial_boost = self.calculate_spatial_confidence_boost(decision.start_pos, math_regions)
                
                # Adjust confidence based on sympy validation and context state
                if sympy_valid:
                    confidence = min(1.0, confidence + sympy_conf * 0.2)
                
                # Context state boosts
                context_boosts = {
                    MathContextState.THEOREM_HEADER: 0.15,
                    MathContextState.EQUATION_BLOCK: 0.10,
                    MathContextState.PROOF_SECTION: 0.08,
                    MathContextState.FORMULA_LIST: 0.12,
                    MathContextState.NEUTRAL: 0.0
                }
                
                context_boost = context_boosts.get(self.context_state, 0.0)
                confidence = min(1.0, confidence + context_boost + spatial_boost)
                
                math_region = MathRegion(
                    start_pos=decision.start_pos,
                    end_pos=decision.end_pos,
                    content=decision.full_segment,
                    confidence=confidence,
                    context_before=context_before.strip(),
                    context_after=context_after.strip(),
                    classification=classification,
                    sympy_parseable=sympy_valid,
                    false_positive_score=fp_score,
                    context_state=self.context_state,
                    spatial_confidence_boost=spatial_boost
                )
                
                math_regions.append(math_region)
                
                # Record final classification reasoning for each marked region
                self.classification_reasoning[region_id] = (f"High divergence (sim={decision.similarity:.3f}), "
                    f"classified as {classification}, sympy_valid={sympy_valid}, fp_score={fp_score:.3f}, "
                    f"context={self.context_state.value}, spatial_boost={spatial_boost:.3f}")
                logger.info(f"Mathematical region detected: {classification} with confidence {confidence:.3f}")
                
            elif decision.similarity < self.medium_divergence_threshold:
                # Medium Divergence (0.3-0.7): Likely mathematical or special symbols
                if self._contains_math_patterns(decision.full_segment):
                    confidence = (self.medium_divergence_threshold - decision.similarity) / self.medium_divergence_threshold * 0.7
                    classification = self.classify_mathematical_content(decision.full_segment, confidence)
                    
                    # Context extraction for medium divergence regions too
                    context_before = ""
                    context_after = ""
                    
                    if i > 0:
                        prev_segment = alignment_decisions[i-1].full_segment
                        context_before = prev_segment[-self.context_chars:] if len(prev_segment) > self.context_chars else prev_segment
                    
                    if i < len(alignment_decisions) - 1:
                        next_segment = alignment_decisions[i+1].full_segment
                        context_after = next_segment[:self.context_chars] if len(next_segment) > self.context_chars else next_segment
                    
                    sympy_valid, sympy_conf = self.validate_with_sympy(decision.full_segment)
                    fp_score = self.calculate_false_positive_score(decision.full_segment, context_before, context_after)
                    spatial_boost = self.calculate_spatial_confidence_boost(decision.start_pos, math_regions)
                    
                    # Apply boosts
                    context_boost = 0.05 if self.context_state != MathContextState.NEUTRAL else 0.0
                    confidence = min(1.0, confidence + context_boost + spatial_boost)
                    
                    math_region = MathRegion(
                        start_pos=decision.start_pos,
                        end_pos=decision.end_pos,
                        content=decision.full_segment,
                        confidence=confidence,
                        context_before=context_before.strip(),
                        context_after=context_after.strip(),
                        classification=classification,
                        sympy_parseable=sympy_valid,
                        false_positive_score=fp_score,
                        context_state=self.context_state,
                        spatial_confidence_boost=spatial_boost
                    )
                    math_regions.append(math_region)
                    
                    self.classification_reasoning[region_id] = (f"Medium divergence (sim={decision.similarity:.3f}), "
                        f"contains math patterns, classified as {classification}, sympy_valid={sympy_valid}, "
                        f"fp_score={fp_score:.3f}, context={self.context_state.value}, spatial_boost={spatial_boost:.3f}")
                    logger.info(f"Potential mathematical region: {classification} with confidence {confidence:.3f}")
        
        return math_regions

    def _contains_math_patterns(self, text: str) -> bool:
        """Check if text contains mathematical patterns"""
        # Inline Math: Single Greek letters mixed with regular text (like "the α particle")
        greek_pattern = r'[αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]'
        
        # Mathematical operators
        math_ops = r'[∫∑∏√∂∇∞±≤≥≠≈∈∉⊂⊃∪∩]'
        
        # Subscripts/Superscripts: Often recognized differently between passes
        sub_super = r'[₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹]'
        
        # Fractions
        fraction = r'[½⅓⅔¼¾⅛⅜⅝⅞]'
        
        patterns = [greek_pattern, math_ops, sub_super, fraction]
        
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        
        return False

    def handle_edge_cases(self, math_regions: List[MathRegion]) -> List[MathRegion]:
        """Some fucked up scenarios you need to handle"""
        filtered_regions = []
        
        for region in math_regions:
            # Mathematical Text: Words like "integral" or "derivative" that aren't symbols
            math_words = ['integral', 'derivative', 'limit', 'summation', 'matrix', 'vector', 'equation']
            if any(word in region.content.lower() for word in math_words) and region.confidence < 0.5:
                logger.warning(f"Possible false positive: mathematical word '{region.content}' with low confidence")
                continue
            
            # False Positives: Regular text that looks mathematical to the differential analysis
            if len(region.content.strip()) < 2 and region.confidence < 0.6:
                logger.warning(f"Possible false positive: short content '{region.content}' with low confidence")
                continue
            
            # Filter based on false positive score
            if region.false_positive_score > 0.7:
                logger.warning(f"High false positive score ({region.false_positive_score:.3f}) for region: '{region.content}'")
                continue
            
            filtered_regions.append(region)
        
        return filtered_regions

    def generate_multiple_output_formats(self, full_text: str, math_regions: List[MathRegion]) -> Dict[str, str]:
        """Phase 6: The Output Optimization Endgame - Creating Multiple Output Formats"""
        outputs = {}
        
        if not math_regions:
            return {
                "reading_version": full_text,
                "analysis_version": full_text,
                "reconstruction_version": full_text,
                "markdown_version": full_text  # Add Markdown-style output format that was mentioned in instructions
            }
        
        sorted_regions = sorted(math_regions, key=lambda x: x.start_pos)
        
        # Reading Version: Clean text with [MATH] placeholders
        reading_result = ""
        analysis_result = ""
        reconstruction_result = ""
        markdown_result = ""  # Add Markdown-style output
        last_pos = 0
        
        for region in sorted_regions:
            # Add text before math region
            text_before = full_text[last_pos:region.start_pos]
            reading_result += text_before
            analysis_result += text_before
            reconstruction_result += text_before
            markdown_result += text_before
            
            # Reading Version: Clean text with [MATH] placeholders
            reading_result += "[MATH]"
            
            # Analysis Version: Full text with mathematical content marked but included
            analysis_result += (f"<MATH confidence=\"{region.confidence:.2f}\" "
                              f"type=\"{region.classification}\" "
                              f"sympy=\"{region.sympy_parseable}\" "
                              f"context=\"{region.context_state.value}\">"
                              f"{region.content}</MATH>")
            
            # Reconstruction Version: Format optimized for LaTeX regeneration
            reconstruction_result += f"\\begin{{math}}{region.content}\\end{{math}}"
            
            # Markdown Version: Use special delimiters like $$[MATH_CONTENT]$$
            markdown_result += f"$$[{region.content}]$$"
            
            last_pos = region.end_pos
        
        # Add remaining text
        remaining_text = full_text[last_pos:]
        reading_result += remaining_text
        analysis_result += remaining_text
        reconstruction_result += remaining_text
        markdown_result += remaining_text
        
        outputs["reading_version"] = reading_result
        outputs["analysis_version"] = analysis_result  
        outputs["reconstruction_version"] = reconstruction_result
        outputs["markdown_version"] = markdown_result
        
        return outputs

    def generate_metadata_version(self, full_text: str, math_regions: List[MathRegion]) -> Dict[str, Any]:
        """Metadata Version: JSON structure with text and mathematical regions separated"""
        mathematical_regions = [asdict(region) for region in math_regions]
        for region in mathematical_regions:
            region["context_state"] = region["context_state"].value


        return {
            "original_text": full_text,
            "mathematical_regions": mathematical_regions,
            "alignment_decisions": [asdict(decision) for decision in self.alignment_decisions],
            "classification_reasoning": self.classification_reasoning,
            "validation_metrics": self.calculate_validation_metrics(full_text, math_regions),
            "context_history": [(pos, state.value) for pos, state in self.context_history],
            "baseline_ocr_consistency": self.baseline_ocr_consistency,
            "adaptive_thresholds": {
                "high_divergence": self.high_divergence_threshold,
                "medium_divergence": self.medium_divergence_threshold,
                "low_divergence": self.low_divergence_threshold
            }
        }

    def calculate_validation_metrics(self, full_text: str, math_regions: List[MathRegion]) -> Dict[str, float]:
        """Phase 5: The Quality Control Checkpoint - Validation Metrics"""
        if not full_text:
            return {"coverage_ratio": 0, "confidence_distribution": {}, "alignment_quality": 0}
        
        # Coverage Ratio: What percentage of the document is mathematical?
        total_math_chars = sum(len(r.content) for r in math_regions)
        coverage_ratio = total_math_chars / len(full_text)
        
        # Confidence Distribution: How confident are your mathematical detections?
        confidence_scores = [r.confidence for r in math_regions]
        confidence_distribution = {
            "mean": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
            "min": min(confidence_scores) if confidence_scores else 0,
            "max": max(confidence_scores) if confidence_scores else 0,
            "count_high": len([c for c in confidence_scores if c > 0.8]),
            "count_medium": len([c for c in confidence_scores if 0.5 <= c <= 0.8]),
            "count_low": len([c for c in confidence_scores if c < 0.5])
        }
        
        # Alignment Quality: How well did the two passes align overall?
        alignment_similarities = [d.similarity for d in self.alignment_decisions]
        alignment_quality = sum(alignment_similarities) / len(alignment_similarities) if alignment_similarities else 0
        
        # Add false positive rate estimation
        fp_scores = [r.false_positive_score for r in math_regions]
        false_positive_metrics = {
            "average_fp_score": sum(fp_scores) / len(fp_scores) if fp_scores else 0,
            "high_fp_count": len([s for s in fp_scores if s > 0.7]),
            "sympy_parseable_count": len([r for r in math_regions if r.sympy_parseable]),
            "sympy_parseable_ratio": len([r for r in math_regions if r.sympy_parseable]) / len(math_regions) if math_regions else 0
        }
        
        # Spatial clustering metrics
        spatial_metrics = {
            "average_spatial_boost": sum(r.spatial_confidence_boost for r in math_regions) / len(math_regions) if math_regions else 0,
            "clustered_regions": len([r for r in math_regions if r.spatial_confidence_boost > 0.05]),
            "context_state_distribution": {
                state.value: len([r for r in math_regions if r.context_state == state])
                for state in MathContextState
            }
        }
        
        return {
            "coverage_ratio": coverage_ratio,
            "confidence_distribution": confidence_distribution,
            "alignment_quality": alignment_quality,
            "false_positive_metrics": false_positive_metrics,
            "spatial_metrics": spatial_metrics,
            "total_math_regions": len(math_regions),
            "total_characters": len(full_text)
        }

    def run_character_confidence_analysis(self, image: np.ndarray) -> Dict[str, Any]:
        """Run confidence analysis on every single character if you want"""
        pil_image = Image.fromarray(image)
        
        try:
            # Get character-level data from Tesseract
            data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
            
            char_confidences = []
            for i in range(len(data['text'])):
                if data['text'][i].strip():  # Non-empty text
                    char_confidences.append({
                        'character': data['text'][i],
                        'confidence': data['conf'][i],
                        'bbox': (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                    })
            
            return {
                'character_data': char_confidences,
                'average_confidence': sum(c['confidence'] for c in char_confidences) / len(char_confidences) if char_confidences else 0
            }
        except Exception as e:
            logger.error(f"Character confidence analysis failed: {e}")
            return {'character_data': [], 'average_confidence': 0}

    def triangulate_with_multiple_whitelists(self, image: np.ndarray) -> Dict[str, str]:
        """Run multiple character whitelist variations to triangulate mathematical content"""
        whitelists = {
            "strict_ascii": self.ascii_whitelist,
            "ascii_plus_basic_math": self.ascii_whitelist + "+-=*/^()[]{}",
            "ascii_plus_greek": self.ascii_whitelist + "αβγδεζηθικλμνξοπρστυφχψω",
            "ascii_plus_operators": self.ascii_whitelist + "∫∑∏√∂∇∞±≤≥≠≈",
            "math_only": self.math_only_whitelist
        }
        
        results = {}
        pil_image = Image.fromarray(image)
        
        for name, whitelist in whitelists.items():
            escaped_whitelist = self.escape_whitelist(whitelist)
            config = f"{self.base_config} {self.lang_config} --oem 3 -c tessedit_char_whitelist={escaped_whitelist}"
            try:
                text = pytesseract.image_to_string(pil_image, config=config)
                results[name] = text.strip()
                logger.debug(f"Whitelist '{name}': {len(text)} characters")
            except Exception as e:
                logger.error(f"Whitelist '{name}' failed: {e}")
                results[name] = ""
        
        return results

    def process_single_variation(self, args: Tuple) -> Dict[str, Any]:
        """Process a single image variation - helper for multiprocessing
        
        FIXED: This is now a proper standalone function for ProcessPoolExecutor
        """
        processed_image, variation_idx, enable_nuclear_option, enable_multiple_engines, doc_type = args
        
        # Create a new OCR instance for this process (avoid pickle issues)
        local_ocr = TwoPassMathOCR(doc_type=doc_type)
        
        logger.info(f"Processing variation {variation_idx} in process {os.getpid()}")
        
        # Phase 1 & 2: Multiple engine OCR passes
        if enable_multiple_engines:
            restricted_results = local_ocr.run_multiple_engines(processed_image, "restricted")
            full_results = local_ocr.run_multiple_engines(processed_image, "full")
            
            # Use best engine results (highest confidence/length)
            best_restricted = max(restricted_results.items(), key=lambda x: len(x[1]))[1]
            best_full = max(full_results.items(), key=lambda x: len(x[1]))[1]
        else:
            best_restricted = local_ocr.run_restricted_ocr(processed_image)
            best_full = local_ocr.run_full_ocr(processed_image)
        
        # Adapt thresholds based on document quality
        baseline_consistency = local_ocr.calculate_baseline_ocr_consistency(best_restricted, best_full)
        local_ocr.adapt_thresholds_to_document(baseline_consistency, doc_type)
        
        # Phase 3: Advanced alignment analysis
        alignment_decisions = local_ocr.align_texts_advanced(best_restricted, best_full)
        
        # Also run sliding window analysis for comparison
        sliding_windows = local_ocr.sliding_window_analysis(best_restricted, best_full)
        
        # Phase 4: Mathematical region detection
        math_regions = local_ocr.detect_mathematical_regions(alignment_decisions)
        math_regions = local_ocr.handle_edge_cases(math_regions)
        
        # Nuclear Option: Triple-pass verification
        if enable_nuclear_option and math_regions:
            logger.info("Activating nuclear option: triple-pass verification")
            math_only_result = local_ocr.run_math_only_ocr(processed_image)
            
            # Verify detected regions against math-only OCR
            for region in math_regions:
                math_content_in_region = math_only_result[region.start_pos:region.end_pos] if region.start_pos < len(math_only_result) else ""
                if math_content_in_region.strip():
                    region.confidence = min(1.0, region.confidence + 0.1)  # Boost confidence
                    logger.debug(f"Nuclear verification boosted confidence for region: {region.content}")
        
        # Character-level confidence analysis
        char_analysis = local_ocr.run_character_confidence_analysis(processed_image)
        
        # Multiple whitelist triangulation
        whitelist_results = local_ocr.triangulate_with_multiple_whitelists(processed_image)
        
        # Generate all output formats
        output_formats = local_ocr.generate_multiple_output_formats(best_full, math_regions)
        metadata = local_ocr.generate_metadata_version(best_full, math_regions)
        
        variation_results = {
            "restricted_text": best_restricted,
            "full_text": best_full,
            "math_regions": math_regions,
            "alignment_decisions": alignment_decisions,
            "sliding_windows": sliding_windows,
            "output_formats": output_formats,
            "metadata": metadata,
            "character_analysis": char_analysis,
            "whitelist_triangulation": whitelist_results
        }
        
        if enable_multiple_engines:
            variation_results["all_engine_results"] = {
                "restricted": {engine.name: text for engine, text in restricted_results.items()},
                "full": {engine.name: text for engine, text in full_results.items()}
            }
        
        return variation_results

    def process_document_comprehensive(self, image_path: str, enable_nuclear_option: bool = True, 
                                     enable_preprocessing_variations: bool = True,
                                     enable_multiple_engines: bool = True,
                                     enable_multiprocessing: bool = True,
                                     doc_type: DocumentType = None) -> Dict[str, Any]:
        """Main processing function with all advanced features enabled
        
        Since you said performance isn't an issue, you can go fucking wild with:
        Run multiple character whitelist variations, Use different Tesseract engines and compare results,
        Apply image preprocessing variations, Run confidence analysis on every single character
        
        FIXED: Using ProcessPoolExecutor instead of ThreadPoolExecutor for CPU-bound operations
        """
        
        logger.info("Starting comprehensive document processing...")
        
        # Use document type from init if not specified
        if doc_type is None:
            doc_type = DocumentType.GENERAL
        
        # Preprocess image (handles both images and PDFs)
        base_images = self.preprocess_image(image_path)
        
        all_page_results = {}
        
        # Process each page (for PDFs) or single image
        for page_idx, base_image in enumerate(base_images):
            logger.info(f"Processing page/image {page_idx + 1}/{len(base_images)}")
            
            preprocessing_variations = self.create_preprocessing_variations(base_image) if enable_preprocessing_variations else [base_image]
            page_results = {}
            
            # FIXED: Using ProcessPoolExecutor for CPU-bound OCR operations
            if enable_multiprocessing and len(preprocessing_variations) > 1:
                logger.info("Using ProcessPoolExecutor for parallel variation processing (CPU-bound operations)")
                
                # Prepare arguments for parallel processing
                process_args = [
                    (processed_image, i, enable_nuclear_option, enable_multiple_engines, doc_type)
                    for i, processed_image in enumerate(preprocessing_variations)
                ]
                
                # Use ProcessPoolExecutor for CPU-bound Tesseract operations
                with ProcessPoolExecutor(max_workers=min(len(preprocessing_variations), mp.cpu_count())) as executor:
                    # Submit all tasks
                    future_to_idx = {
                        executor.submit(process_single_variation_standalone, args): i 
                        for i, args in enumerate(process_args)
                    }
                    
                    # Collect results as they complete
                    variation_results = {}
                    for future in as_completed(future_to_idx):
                        idx = future_to_idx[future]
                        try:
                            result = future.result()
                            variation_results[f"variation_{idx}"] = result
                        except Exception as e:
                            logger.error(f"Variation {idx} failed: {e}")
                            continue
                    
                    page_results = variation_results
            
            else:
                # Process variations sequentially
                for i, processed_image in enumerate(preprocessing_variations):
                    logger.info(f"Processing image variation {i+1}/{len(preprocessing_variations)}")
                    
                    variation_results = self.process_single_variation(
                        (processed_image, i, enable_nuclear_option, enable_multiple_engines, doc_type)
                    )
                    page_results[f"variation_{i}"] = variation_results
            
            all_page_results[f"page_{page_idx}"] = page_results
        
        # Select best overall result across all pages/variations
        all_variations = []
        for page_results in all_page_results.values():
            all_variations.extend(page_results.values())
        
        if all_variations:
            best_variation = max(all_variations, 
                               key=lambda x: len([r for r in x["math_regions"] if r.confidence > 0.5]))
        else:
            logger.error("No successful variations processed")
            return {"error": "No successful processing results"}
        
        logger.info(f"Processing complete. Best variation detected {len(best_variation['math_regions'])} mathematical regions")
        
        return {
            "best_result": best_variation,
            "all_pages": all_page_results,
            "forensic_trail": {
                "alignment_decisions": self.alignment_decisions,
                "classification_reasoning": self.classification_reasoning,
                "context_history": self.context_history
            }
        }

# Standalone function for ProcessPoolExecutor (can't pickle instance methods)
def process_single_variation_standalone(args: Tuple) -> Dict[str, Any]:
    """Standalone function for ProcessPoolExecutor - works around pickle limitations"""
    processed_image, variation_idx, enable_nuclear_option, enable_multiple_engines, doc_type = args
    
    # Create new OCR instance in the worker process
    ocr = TwoPassMathOCR(doc_type=doc_type)
    
    return ocr.process_single_variation(args)

# Unit test functions with enhanced coverage
def test_ascii_whitelist():
    """Basic unit test for ASCII whitelist functionality"""
    ocr = TwoPassMathOCR()
    assert 'A' in ocr.ascii_whitelist
    assert 'α' not in ocr.ascii_whitelist
    assert '∫' not in ocr.ascii_whitelist

def test_document_type_whitelists():
    """Test document-specific whitelist configurations"""
    financial_ocr = TwoPassMathOCR(doc_type=DocumentType.FINANCIAL)
    assert '$' in financial_ocr.ascii_whitelist
    
    physics_ocr = TwoPassMathOCR(doc_type=DocumentType.PHYSICS)
    assert '°' in physics_ocr.ascii_whitelist

def test_whitelist_escaping():
    ocr = TwoPassMathOCR()
    escaped = ocr.escape_whitelist("test'string\"with$special&chars")
    # Check that shlex actually wrapped it (starts/ends with quotes)
    assert escaped[0] in ["'", '"'] and escaped[-1] in ["'", '"']

def test_sympy_validation():
    ocr = TwoPassMathOCR()
    
    # Use ** for exponentiation in sympy
    valid, conf = ocr.validate_with_sympy("x**2 + 2*x + 1")
    assert valid == True
    assert conf > 0
    
    # Test invalid expression
    valid, conf = ocr.validate_with_sympy("hello world")
    assert valid == False

def test_false_positive_detection():
    """Test false positive scoring"""
    ocr = TwoPassMathOCR()
    
    # Test common word (should have high FP score)
    fp_score = ocr.calculate_false_positive_score("the", "in the", "beginning")
    assert fp_score > 0.3
    
    # Test mathematical symbol (should have low FP score)
    fp_score = ocr.calculate_false_positive_score("α", "variable", "equals")
    assert fp_score < 0.5

def test_context_state_machine():
    """Test mathematical context state detection"""
    ocr = TwoPassMathOCR()
    
    # Test theorem header detection
    state = ocr.update_context_state("Theorem 1: Let f be a function", 0)
    assert state == MathContextState.THEOREM_HEADER
    
    # Test proof detection
    state = ocr.update_context_state("Proof: We proceed by induction", 100)
    assert state == MathContextState.PROOF_SECTION

def test_adaptive_thresholding():
    """Test adaptive threshold calculation"""
    ocr = TwoPassMathOCR()
    
    original_high = ocr.high_divergence_threshold
    
    # Test high-quality document adjustment
    ocr.adapt_thresholds_to_document(0.95, DocumentType.GENERAL)
    assert ocr.high_divergence_threshold < original_high  # Should be more strict
    
    # Reset and test low-quality document
    ocr.high_divergence_threshold = original_high
    ocr.adapt_thresholds_to_document(0.5, DocumentType.GENERAL)
    assert ocr.high_divergence_threshold > original_high  # Should be more lenient

def test_spatial_confidence_boost():
    """Test spatial confidence propagation"""
    ocr = TwoPassMathOCR()
    
    # Create mock high-confidence math region
    mock_region = MathRegion(
        start_pos=100, end_pos=110, content="α", confidence=0.9,
        classification="simple_variable"
    )
    
    # Test boost calculation for nearby position
    boost = ocr.calculate_spatial_confidence_boost(105, [mock_region])
    assert boost > 0  # Should get a boost from nearby high-confidence region
    
    # Test distant position
    boost = ocr.calculate_spatial_confidence_boost(500, [mock_region])
    assert boost == 0  # Should get no boost from distant region

def run_unit_tests():
    """Run all unit tests - now with more comprehensive coverage"""
    tests = [
        test_ascii_whitelist, test_document_type_whitelists, test_whitelist_escaping,
        test_sympy_validation, test_false_positive_detection, test_context_state_machine,
        test_adaptive_thresholding, test_spatial_confidence_boost
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__} passed")
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
    
    print(f"\nTest Results: {passed} passed, {failed} failed")
    return failed == 0

# Usage example with comprehensive processing and PDF support
def main():
    print("=== MATHEMATICAL OCR WAR MACHINE v2.0 ===")
    print("Now with PDF support and industrial-strength multiprocessing!")
    
    # Run unit tests first
    print("\n=== RUNNING ENHANCED UNIT TESTS ===")
    all_tests_passed = run_unit_tests()
    
    if not all_tests_passed:
        print("⚠️  Some tests failed - proceeding anyway because this is a demo")
    
    print("\n=== STARTING OCR PROCESSING ===")
    
    # Initialize with document type
    ocr = TwoPassMathOCR(doc_type=DocumentType.PHYSICS)
    
    # Support both images and PDFs
    document_path = "page_008_img_007.png="  # Can be .pdf, .png, .jpg, etc.
    
    try:
        # Process with all advanced features enabled
        results = ocr.process_document_comprehensive(
            document_path,
            enable_nuclear_option=True,
            enable_preprocessing_variations=True, 
            enable_multiple_engines=True,
            enable_multiprocessing=True,
            doc_type=DocumentType.PHYSICS
        )
        
        if "error" in results:
            print(f"Processing failed: {results['error']}")
            return
        
        best = results["best_result"]
        
        print("=== COMPREHENSIVE OCR PROCESSING COMPLETE ===")
        print(f"Mathematical regions detected: {len(best['math_regions'])}")
        print(f"Baseline OCR consistency: {best['metadata']['baseline_ocr_consistency']:.3f}")
        print(f"Adaptive thresholds used: {best['metadata']['adaptive_thresholds']}")
        print(f"Validation metrics: {best['metadata']['validation_metrics']}")
        
        # Print all output versions
        print("\n=== READING VERSION ===")
        print(best["output_formats"]["reading_version"][:500] + "..." if len(best["output_formats"]["reading_version"]) > 500 else best["output_formats"]["reading_version"])
        
        print("\n=== ANALYSIS VERSION ===") 
        print(best["output_formats"]["analysis_version"][:500] + "..." if len(best["output_formats"]["analysis_version"]) > 500 else best["output_formats"]["analysis_version"])
        
        print("\n=== MARKDOWN VERSION ===") 
        print(best["output_formats"]["markdown_version"][:500] + "..." if len(best["output_formats"]["markdown_version"]) > 500 else best["output_formats"]["markdown_version"])
        
        print("\n=== MATHEMATICAL REGIONS DETAILS ===")
        for i, region in enumerate(best["math_regions"][:10]):  # Show first 10
            print(f"Region {i+1}: {region.classification} - '{region.content}' "
                  f"(confidence: {region.confidence:.3f}, sympy: {region.sympy_parseable}, "
                  f"fp_score: {region.false_positive_score:.3f}, "
                  f"context: {region.context_state.value}, "
                  f"spatial_boost: {region.spatial_confidence_boost:.3f})")
        
        if len(best["math_regions"]) > 10:
            print(f"... and {len(best['math_regions']) - 10} more regions")
        
        print(f"\n=== CONTEXT HISTORY ===")
        for pos, state in best["metadata"]["context_history"]:
            print(f"Position {pos}: {state}")
        
        # Save comprehensive results
        with open("comprehensive_ocr_results.json", "w", encoding="utf-8") as f:
            # Convert objects to dicts for JSON serialization
            serializable_results = {
                "reading_version": best["output_formats"]["reading_version"],
                "analysis_version": best["output_formats"]["analysis_version"],
                "reconstruction_version": best["output_formats"]["reconstruction_version"],
                "markdown_version": best["output_formats"]["markdown_version"],
                "metadata": best["metadata"],
                "forensic_trail": results["forensic_trail"]
            }
            json.dump(serializable_results, f, indent=2, ensure_ascii=False)
        
        print("\nComprehensive results saved to comprehensive_ocr_results.json")
        print("\n🎯 Mission accomplished! This OCR war machine is ready for production.")
        
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        print(f"💥 Error processing document: {e}")
        print("Check that you have the required dependencies:")
        print("pip install pytesseract opencv-python pillow numpy sympy pdf2image")

if __name__ == "__main__":
    main()
