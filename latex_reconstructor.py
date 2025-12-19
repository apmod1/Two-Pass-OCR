#!/usr/bin/env python3
"""
LaTeX Reconstruction Engine
The digital necromancer that resurrects academic documents from OCR carnage
"""

import re
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from enum import Enum
import json

# Configure logging for maximum reconstruction intel
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MathContext(Enum):
    """Mathematical context types for smart symbol interpretation"""
    INLINE = "inline"
    DISPLAY = "display"
    EQUATION = "equation"
    ALIGN = "align"

@dataclass
class MathExpression:
    """Structured representation of a mathematical expression"""
    content: str
    context: MathContext
    latex_output: str
    confidence: float
    position: Tuple[int, int]  # Start and end positions in text

@dataclass
class AcademicEnvironment:
    """Structured representation of academic environments"""
    env_type: str          # theorem, lemma, proof, etc.
    number: Optional[str]  # Environment number if applicable
    content: str          # Environment content
    latex_begin: str      # LaTeX begin command
    latex_end: str        # LaTeX end command
    label: Optional[str]  # Generated label
    position: Tuple[int, int]

class MathematicalSymbolMap:
    """
    The grand dictionary of mathematical symbol wisdom
    Every Unicode math symbol and its LaTeX equivalent
    """
    
    def __init__(self):
        # Greek alphabet mapping - the classics
        self.greek_letters = {
            'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
            'ε': r'\varepsilon', 'ζ': r'\zeta', 'η': r'\eta', 'θ': r'\theta',
            'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu',
            'ν': r'\nu', 'ξ': r'\xi', 'ο': r'o', 'π': r'\pi',
            'ρ': r'\rho', 'σ': r'\sigma', 'τ': r'\tau', 'υ': r'\upsilon',
            'φ': r'\varphi', 'χ': r'\chi', 'ψ': r'\psi', 'ω': r'\omega',
            'Α': r'A', 'Β': r'B', 'Γ': r'\Gamma', 'Δ': r'\Delta',
            'Ε': r'E', 'Ζ': r'Z', 'Η': r'H', 'Θ': r'\Theta',
            'Ι': r'I', 'Κ': r'K', 'Λ': r'\Lambda', 'Μ': r'M',
            'Ν': r'N', 'Ξ': r'\Xi', 'Ο': r'O', 'Π': r'\Pi',
            'Ρ': r'P', 'Σ': r'\Sigma', 'Τ': r'T', 'Υ': r'\Upsilon',
            'Φ': r'\Phi', 'Χ': r'X', 'Ψ': r'\Psi', 'Ω': r'\Omega'
        }
        
        # Mathematical operators - the heavy artillery
        self.operators = {
            '≤': r'\leq', '≥': r'\geq', '≠': r'\neq', '≈': r'\approx',
            '±': r'\pm', '∓': r'\mp', '×': r'\times', '÷': r'\div',
            '·': r'\cdot', '∗': r'\ast', '∘': r'\circ', '†': r'\dagger',
            '‡': r'\ddagger', '⊕': r'\oplus', '⊗': r'\otimes',
            '⊙': r'\odot', '⊖': r'\ominus', '∧': r'\wedge', '∨': r'\vee',
            '¬': r'\neg', '∀': r'\forall', '∃': r'\exists', '∄': r'\nexists',
            '∅': r'\emptyset', '∞': r'\infty', '∇': r'\nabla', '∂': r'\partial'
        }
        
        # Set theory and logic symbols
        self.set_symbols = {
            '∈': r'\in', '∉': r'\notin', '⊂': r'\subset', '⊃': r'\supset',
            '⊆': r'\subseteq', '⊇': r'\supseteq', '∪': r'\cup', '∩': r'\cap',
            '∖': r'\setminus', '△': r'\triangle', '⊥': r'\perp', '∥': r'\parallel',
            '⊢': r'\vdash', '⊨': r'\models', '→': r'\to', '←': r'\leftarrow',
            '↔': r'\leftrightarrow', '⇒': r'\Rightarrow', '⇐': r'\Leftarrow',
            '⇔': r'\Leftrightarrow'
        }
        
        # Calculus and analysis symbols
        self.calculus_symbols = {
            '∫': r'\int', '∬': r'\iint', '∭': r'\iiint', '∮': r'\oint',
            '∑': r'\sum', '∏': r'\prod', '∐': r'\coprod', '√': r'\sqrt',
            '∛': r'\sqrt[3]', '∜': r'\sqrt[4]', 'ℝ': r'\mathbb{R}',
            'ℂ': r'\mathbb{C}', 'ℕ': r'\mathbb{N}', 'ℤ': r'\mathbb{Z}',
            'ℚ': r'\mathbb{Q}', '∝': r'\propto', '∆': r'\Delta'
        }
        
        # Combine all symbol mappings
        self.symbol_map = {
            **self.greek_letters,
            **self.operators,
            **self.set_symbols,
            **self.calculus_symbols
        }
        
        # Context-sensitive symbols (these need special handling)
        self.context_sensitive = {
            '|': {
                'absolute_value': r'\left| {content} \right|',
                'cardinality': r'\left| {content} \right|',
                'conditional': r'{prob} \mid {condition}',
                'divisibility': r'{a} \mid {b}'
            },
            '*': {
                'multiplication': r'\cdot',
                'convolution': r'*',
                'complex_conjugate': r'^*'
            },
            '/': {
                'fraction': r'\frac{{{numerator}}}{{{denominator}}}',
                'division': r'/',
                'derivative': r'\frac{d}{d{var}}'
            }
        }

class MathematicalExpressionParser:
    """
    The mathematical language compiler that understands calculus grammar
    This beast can parse complex mathematical expressions and convert them to LaTeX
    """
    
    def __init__(self):
        self.symbol_map = MathematicalSymbolMap()
        
        # Mathematical function patterns
        self.function_patterns = {
            r'\bsin\b': r'\sin',
            r'\bcos\b': r'\cos',
            r'\btan\b': r'\tan',
            r'\bexp\b': r'\exp',
            r'\bln\b': r'\ln',
            r'\blog\b': r'\log',
            r'\bmax\b': r'\max',
            r'\bmin\b': r'\min',
            r'\blim\b': r'\lim',
            r'\bdet\b': r'\det',
            r'\bdim\b': r'\dim'
        }
        
        # Superscript/subscript Unicode mappings
        self.superscript_map = {
            '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
            '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
            'ⁿ': 'n', 'ⁱ': 'i', 'ʲ': 'j', 'ᵏ': 'k'
        }
        
        self.subscript_map = {
            '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
            '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
            'ₙ': 'n', 'ᵢ': 'i', 'ⱼ': 'j', 'ₖ': 'k'
        }
    
    def detect_math_expressions(self, text: str) -> List[Tuple[int, int, str, MathContext]]:
        """
        Detect mathematical expressions in text using pattern recognition
        This is like having mathematical radar that can spot equations in text
        
        Args:
            text: Input text to scan
            
        Returns:
            List of (start, end, expression, context) tuples
        """
        math_expressions = []
        
        # Pattern 1: Standalone equations (likely display math)
        equation_pattern = r'(?:^|\n)\s*([^.!?]*(?:[∑∫∂∇×±≤≥≠≈∞°√∝αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ=+\-*/^_()[\]{}|])+[^.!?]*)\s*(?=\n|$)'
        
        for match in re.finditer(equation_pattern, text, re.MULTILINE):
            start, end = match.span(1)
            expr = match.group(1).strip()
            
            # Check if this looks like a mathematical expression
            if self._is_mathematical_expression(expr):
                context = MathContext.DISPLAY if self._is_display_math(expr) else MathContext.INLINE
                math_expressions.append((start, end, expr, context))
        
        # Pattern 2: Inline mathematical expressions
        inline_pattern = r'(?<!\w)([a-zA-Z](?:[₀-₉ᵢⱼₖₙ]*|[⁰-⁹ⁿⁱʲᵏ]*)[+\-*/=](?:[a-zA-Z₀-₉ᵢⱼₖₙ⁰-⁹ⁿⁱʲᵏαβγδεζηθικλμνξοπρστυφχψω]|\([^)]*\))+)'
        
        for match in re.finditer(inline_pattern, text):
            start, end = match.span(1)
            expr = match.group(1)
            
            # Avoid double-detection with display math
            if not any(start >= ds and end <= de for ds, de, _, _ in math_expressions):
                math_expressions.append((start, end, expr, MathContext.INLINE))
        
        # Pattern 3: Function expressions
        function_pattern = r'(?<!\w)((?:sin|cos|tan|log|ln|exp|max|min|lim|det|dim)\s*\([^)]+\))'
        
        for match in re.finditer(function_pattern, text, re.IGNORECASE):
            start, end = match.span(1)
            expr = match.group(1)
            
            # Avoid double-detection
            if not any(start >= ds and end <= de for ds, de, _, _ in math_expressions):
                math_expressions.append((start, end, expr, MathContext.INLINE))
        
        return sorted(math_expressions, key=lambda x: x[0])
    
    def _is_mathematical_expression(self, text: str) -> bool:
        """Check if text contains mathematical content"""
        math_indicators = [
            len(re.findall(r'[∑∫∂∇×±≤≥≠≈∞°√∝]', text)) > 0,  # Math symbols
            len(re.findall(r'[αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]', text)) > 0,  # Greek letters
            len(re.findall(r'[₀-₉ᵢⱼₖₙ⁰-⁹ⁿⁱʲᵏ]', text)) > 0,  # Super/subscripts
            len(re.findall(r'[a-zA-Z]\s*[=+\-*/]\s*[a-zA-Z0-9]', text)) > 0,  # Equations
            len(re.findall(r'(?:sin|cos|tan|log|ln|exp|max|min|lim)', text, re.IGNORECASE)) > 0  # Functions
        ]
        
        return sum(math_indicators) >= 1
    
    def _is_display_math(self, text: str) -> bool:
        """Determine if expression should be display math"""
        display_indicators = [
            len(text) > 30,  # Long expressions
            '∫' in text,     # Integrals
            '∑' in text,     # Summations
            '∏' in text,     # Products
            '/' in text and len(text) > 10,  # Fractions
            text.count('=') >= 1 and len(text) > 15  # Equations
        ]
        
        return sum(display_indicators) >= 2
    
    def convert_to_latex(self, expression: str, context: MathContext) -> str:
        """
        Convert mathematical expression to LaTeX format
        This is where the symbolic logic magic happens
        
        Args:
            expression: Mathematical expression text
            context: Math context (inline, display, etc.)
            
        Returns:
            LaTeX formatted expression
        """
        latex_expr = expression
        
        # Step 1: Convert Unicode symbols to LaTeX commands
        for unicode_char, latex_cmd in self.symbol_map.symbol_map.items():
            latex_expr = latex_expr.replace(unicode_char, latex_cmd)
        
        # Step 2: Convert superscripts and subscripts
        latex_expr = self._convert_super_subscripts(latex_expr)
        
        # Step 3: Convert mathematical functions
        for pattern, replacement in self.function_patterns.items():
            latex_expr = re.sub(pattern, replacement, latex_expr)
        
        # Step 4: Handle fractions
        latex_expr = self._convert_fractions(latex_expr)
        
        # Step 5: Handle integrals with bounds
        latex_expr = self._convert_integrals(latex_expr)
        
        # Step 6: Handle summations and products
        latex_expr = self._convert_sum_prod(latex_expr)
        
        # Step 7: Add appropriate math delimiters
        if context == MathContext.INLINE:
            latex_expr = f'${latex_expr}$'
        elif context == MathContext.DISPLAY:
            latex_expr = f'\\[{latex_expr}\\]'
        elif context == MathContext.EQUATION:
            latex_expr = f'\\begin{{equation}}\n{latex_expr}\n\\end{{equation}}'
        
        return latex_expr
    
    def _convert_super_subscripts(self, text: str) -> str:
        """Convert Unicode super/subscripts to LaTeX format"""
        result = text
        
        # Convert superscripts
        for unicode_sup, normal in self.superscript_map.items():
            # Pattern: find letter/number followed by superscript
            pattern = r'([a-zA-Z0-9])' + re.escape(unicode_sup)
            replacement = r'\1^{' + normal + '}'
            result = re.sub(pattern, replacement, result)
        
        # Convert subscripts
        for unicode_sub, normal in self.subscript_map.items():
            pattern = r'([a-zA-Z0-9])' + re.escape(unicode_sub)
            replacement = r'\1_{' + normal + '}'
            result = re.sub(pattern, replacement, result)
        
        # Handle sequences of super/subscripts
        result = re.sub(r'([a-zA-Z0-9])\^{([^}]+)}\^{([^}]+)}', r'\1^{\2\3}', result)
        result = re.sub(r'([a-zA-Z0-9])_{([^}]+)}_{([^}]+)}', r'\1_{\2\3}', result)
        
        return result
    
    def _convert_fractions(self, text: str) -> str:
        """Convert fraction notation to LaTeX \\frac"""
        # Simple fractions: a/b where a and b are single terms
        result = re.sub(r'([a-zA-Z0-9π∞αβγδεζηθικλμνξοπρστυφχψω]+)/([a-zA-Z0-9π∞αβγδεζηθικλμνξοπρστυφχψω]+)', 
                       r'\\frac{\1}{\2}', text)
        
        # Complex fractions with parentheses: (expr1)/(expr2)
        result = re.sub(r'\(([^)]+)\)/\(([^)]+)\)', r'\\frac{\1}{\2}', result)
        
        # Mixed fractions: expr/(expr)
        result = re.sub(r'([a-zA-Z0-9π∞αβγδεζηθικλμνξοπρστυφχψω]+)/\(([^)]+)\)', 
                       r'\\frac{\1}{\2}', result)
        
        return result
    
    def _convert_integrals(self, text: str) -> str:
        """Convert integral expressions with bounds"""
        # Pattern: ∫ bounds expression dx
        # This is already converted to \int by symbol mapping
        
        # Handle definite integrals with bounds
        integral_pattern = r'\\int([₀-₉∞αβγδεζηθικλμνξοπρστυφχψω-]+)([⁰-⁹∞αβγδεζηθικλμνξοπρστυφχψω]*)\s*([^d]*)\s*d([a-zA-Z])'
        
        def integral_replacement(match):
            lower_bound = match.group(1)
            upper_bound = match.group(2) if match.group(2) else ''
            integrand = match.group(3).strip()
            variable = match.group(4)
            
            # Convert bounds to normal text (they might have subscript/superscript Unicode)
            lower_bound = self._convert_super_subscripts(lower_bound)
            upper_bound = self._convert_super_subscripts(upper_bound)
            
            if upper_bound:
                return f'\\int_{{{lower_bound}}}^{{{upper_bound}}} {integrand} \\, d{variable}'
            else:
                return f'\\int_{{{lower_bound}}} {integrand} \\, d{variable}'
        
        result = re.sub(integral_pattern, integral_replacement, text)
        
        # Handle indefinite integrals
        result = re.sub(r'\\int\s+([^d]+)\s*d([a-zA-Z])', r'\\int \1 \\, d\2', result)
        
        return result
    
    def _convert_sum_prod(self, text: str) -> str:
        """Convert summation and product notation"""
        # Summation with bounds: ∑(i=1 to n) or ∑i=1^n
        sum_pattern = r'\\sum\s*\(([^=]+)=([^)]+)\s+to\s+([^)]+)\)'
        result = re.sub(sum_pattern, r'\\sum_{\1=\2}^{\3}', text)
        
        # Alternative notation: ∑i=1^n
        sum_pattern2 = r'\\sum([a-zA-Z])=([^\\^]+)\^([^\\s]+)'
        result = re.sub(sum_pattern2, r'\\sum_{\1=\2}^{\3}', result)
        
        # Products follow similar patterns
        prod_pattern = r'\\prod\s*\(([^=]+)=([^)]+)\s+to\s+([^)]+)\)'
        result = re.sub(prod_pattern, r'\\prod_{\1=\2}^{\3}', result)
        
        prod_pattern2 = r'\\prod([a-zA-Z])=([^\\^]+)\^([^\\s]+)'
        result = re.sub(prod_pattern2, r'\\prod_{\1=\2}^{\3}', result)
        
        return result

class AcademicEnvironmentDetector:
    """
    The academic structure recognition specialist
    This digital anthropologist understands academic discourse patterns
    """
    
    def __init__(self):
        # Academic environment patterns and their LaTeX equivalents
        self.environment_patterns = {
            'theorem': {
                'pattern': r'(?i)Theorem\s+(\d+)\.?\s*:?\s*',
                'begin': 'theorem',
                'end': 'theorem',
                'numbered': True,
                'label_prefix': 'thm'
            },
            'lemma': {
                'pattern': r'(?i)Lemma\s+(\d+)\.?\s*:?\s*',
                'begin': 'lemma',
                'end': 'lemma',
                'numbered': True,
                'label_prefix': 'lem'
            },
            'proposition': {
                'pattern': r'(?i)Proposition\s+(\d+)\.?\s*:?\s*',
                'begin': 'proposition',
                'end': 'proposition',
                'numbered': True,
                'label_prefix': 'prop'
            },
            'corollary': {
                'pattern': r'(?i)Corollary\s+(\d+)\.?\s*:?\s*',
                'begin': 'corollary',
                'end': 'corollary',
                'numbered': True,
                'label_prefix': 'cor'
            },
            'definition': {
                'pattern': r'(?i)Definition\s+(\d+)\.?\s*:?\s*',
                'begin': 'definition',
                'end': 'definition',
                'numbered': True,
                'label_prefix': 'def'
            },
            'proof': {
                'pattern': r'(?i)Proof\.?\s*:?\s*',
                'begin': 'proof',
                'end': 'proof',
                'numbered': False,
                'label_prefix': None
            },
            'example': {
                'pattern': r'(?i)Example\s+(\d+)\.?\s*:?\s*',
                'begin': 'example',
                'end': 'example',
                'numbered': True,
                'label_prefix': 'ex'
            },
            'remark': {
                'pattern': r'(?i)Remark\s+(\d+)\.?\s*:?\s*',
                'begin': 'remark',
                'end': 'remark',
                'numbered': True,
                'label_prefix': 'rem'
            }
        }
        
        # Patterns that indicate end of environments
        self.termination_patterns = [
            r'(?i)(?:Theorem|Lemma|Proposition|Corollary|Definition|Example|Remark)\s+\d+',
            r'(?i)Proof\.?\s*:?\s*',
            r'(?i)(?:Section|Chapter|Subsection)',
            r'[□∎◊]',  # QED symbols
            r'(?i)Q\.?\s*E\.?\s*D\.?',  # QED text
            r'\n\s*\n\s*[A-Z]'  # Paragraph break followed by capitalized text
        ]
    
    def detect_environments(self, text: str) -> List[AcademicEnvironment]:
        """
        Detect academic environments in text
        This is pattern recognition for academic discourse structure
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of detected academic environments
        """
        environments = []
        
        for env_name, env_config in self.environment_patterns.items():
            pattern = env_config['pattern']
            
            for match in re.finditer(pattern, text):
                start_pos = match.start()
                
                # Extract environment number if numbered
                number = match.group(1) if env_config['numbered'] and match.groups() else None
                
                # Find the end of this environment
                end_pos = self._find_environment_end(text, start_pos + len(match.group(0)))
                
                if end_pos > start_pos:
                    content = text[start_pos + len(match.group(0)):end_pos].strip()
                    
                    # Generate label if applicable
                    label = None
                    if env_config['label_prefix'] and number:
                        label = f"\\label{{{env_config['label_prefix']}:{number}}}"
                    
                    env = AcademicEnvironment(
                        env_type=env_name,
                        number=number,
                        content=content,
                        latex_begin=f"\\begin{{{env_config['begin']}}}",
                        latex_end=f"\\end{{{env_config['end']}}}",
                        label=label,
                        position=(start_pos, end_pos)
                    )
                    
                    environments.append(env)
        
        # Sort by position and remove overlaps
        environments = sorted(environments, key=lambda x: x.position[0])
        environments = self._remove_overlapping_environments(environments)
        
        return environments
    
    def _find_environment_end(self, text: str, start_pos: int) -> int:
        """Find the end position of an academic environment"""
        # Look for termination patterns
        min_end_pos = len(text)
        
        for pattern in self.termination_patterns:
            match = re.search(pattern, text[start_pos:])
            if match:
                end_pos = start_pos + match.start()
                min_end_pos = min(min_end_pos, end_pos)
        
        # Don't let environments be too short or too long
        min_length = 20
        max_length = 2000
        
        actual_end = max(start_pos + min_length, min(min_end_pos, start_pos + max_length))
        
        return actual_end
    
    def _remove_overlapping_environments(self, environments: List[AcademicEnvironment]) -> List[AcademicEnvironment]:
        """Remove overlapping environments, keeping the most specific ones"""
        if not environments:
            return []
        
        result = []
        for env in environments:
            # Check if this environment overlaps with any existing ones
            overlaps = False
            for existing in result:
                if (env.position[0] < existing.position[1] and 
                    env.position[1] > existing.position[0]):
                    overlaps = True
                    break
            
            if not overlaps:
                result.append(env)
        
        return result

class CrossReferenceReconstructor:
    """
    The academic cross-reference resurrection specialist
    Rebuilds the web of academic citations and references
    """
    
    def __init__(self):
        # Patterns for detecting references to academic environments
        self.reference_patterns = {
            'theorem': r'(?i)(?:by|from|in|see)\s+Theorem\s+(\d+)',
            'lemma': r'(?i)(?:by|from|in|see)\s+Lemma\s+(\d+)',
            'proposition': r'(?i)(?:by|from|in|see)\s+Proposition\s+(\d+)',
            'corollary': r'(?i)(?:by|from|in|see)\s+Corollary\s+(\d+)',
            'definition': r'(?i)(?:by|from|in|see)\s+Definition\s+(\d+)',
            'example': r'(?i)(?:by|from|in|see)\s+Example\s+(\d+)',
            'equation': r'(?i)(?:equation|eq\.?)\s+\(?(\d+)\)?',
            'figure': r'(?i)(?:figure|fig\.?)\s+(\d+)',
            'table': r'(?i)(?:table|tab\.?)\s+(\d+)'
        }
    
    def reconstruct_references(self, text: str, environments: List[AcademicEnvironment]) -> str:
        """
        Convert textual references to LaTeX cross-references
        
        Args:
            text: Document text
            environments: List of detected environments
            
        Returns:
            Text with LaTeX cross-references
        """
        result = text
        
        # Build mapping of environment numbers to labels
        label_map = {}
        for env in environments:
            if env.number and env.label:
                label_key = f"{env.env_type}:{env.number}"
                # Extract label name from \label{name}
                label_match = re.search(r'\\label\{([^}]+)\}', env.label)
                if label_match:
                    label_map[label_key] = label_match.group(1)
        
        # Replace textual references with LaTeX references
        for ref_type, pattern in self.reference_patterns.items():
            for match in re.finditer(pattern, result):
                number = match.group(1)
                label_key = f"{ref_type}:{number}"
                
                if label_key in label_map:
                    label_name = label_map[label_key]
                    # Replace the reference
                    original = match.group(0)
                    if ref_type == 'equation':
                        replacement = original.replace(f"{number}", f"~\\eqref{{{label_name}}}")
                    else:
                        replacement = original.replace(f"{ref_type.title()} {number}", 
                                                     f"{ref_type.title()}~\\ref{{{label_name}}}")
                    result = result.replace(original, replacement)
        
        return result

class LaTeXDocumentReconstructor:
    """
    The master LaTeX resurrection orchestrator
    Combines all reconstruction components into a complete LaTeX document
    """
    
    def __init__(self):
        self.math_parser = MathematicalExpressionParser()
        self.env_detector = AcademicEnvironmentDetector()
        self.ref_reconstructor = CrossReferenceReconstructor()
    
    def reconstruct_document(self, ocr_text: str, 
                           document_title: str = None,
                           author_name: str = None,
                           document_class: str = "article") -> str:
        """
        The master reconstruction function
        This is where OCR chaos becomes LaTeX perfection
        
        Args:
            ocr_text: Raw OCR output text
            document_title: Optional document title
            author_name: Optional author name
            document_class: LaTeX document class
            
        Returns:
            Complete LaTeX document source
        """
        logger.info("🧙‍♂️ Starting LaTeX reconstruction alchemy...")
        
        # Step 1: Clean and preprocess the OCR text
        cleaned_text = self._preprocess_ocr_text(ocr_text)
        logger.info(f"📝 Preprocessed {len(cleaned_text)} characters of OCR text")
        
        # Step 2: Detect academic environments
        environments = self.env_detector.detect_environments(cleaned_text)
        logger.info(f"🎯 Detected {len(environments)} academic environments")
        
        # Step 3: Detect mathematical expressions
        math_expressions = self.math_parser.detect_math_expressions(cleaned_text)
        logger.info(f"🔢 Found {len(math_expressions)} mathematical expressions")
        
        # Step 4: Convert mathematical expressions to LaTeX
        processed_text = cleaned_text
        offset = 0
        
        for start, end, expr, context in reversed(math_expressions):  # Reverse to maintain positions
            latex_expr = self.math_parser.convert_to_latex(expr, context)
            
            # Replace in text
            adjusted_start = start + offset
            adjusted_end = end + offset
            processed_text = (processed_text[:adjusted_start] + 
                            latex_expr + 
                            processed_text[adjusted_end:])
            
            offset += len(latex_expr) - (end - start)
        
        logger.info("🔣 Converted mathematical expressions to LaTeX")
        
        # Step 5: Insert academic environments
        processed_text = self._insert_environments(processed_text, environments)
        logger.info("📚 Inserted academic environment markup")
        
        # Step 6: Reconstruct cross-references
        processed_text = self.ref_reconstructor.reconstruct_references(processed_text, environments)
        logger.info("🔗 Reconstructed cross-references")
        
        # Step 7: Generate complete LaTeX document
        latex_document = self._generate_latex_document(
            processed_text, 
            document_title, 
            author_name, 
            document_class,
            environments,
            math_expressions
        )
        
        logger.info("✨ LaTeX reconstruction complete!")
        return latex_document
    
    def _preprocess_ocr_text(self, text: str) -> str:
        """Clean and prepare OCR text for processing"""
        # Fix common OCR artifacts
        cleaned = text
        
        # Fix ligature artifacts that weren't caught by OCR post-processing
        ligature_fixes = {
            'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl'
        }
        for artifact, fix in ligature_fixes.items():
            cleaned = cleaned.replace(artifact, fix)
        
        # Normalize whitespace
        cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)  # Multiple newlines to double
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)  # Multiple spaces to single
        
        # Fix common punctuation issues
        cleaned = re.sub(r'\s+([.,:;!?])', r'\1', cleaned)  # Remove space before punctuation
        cleaned = re.sub(r'([.!?])\s*([A-Z])', r'\1 \2', cleaned)  # Ensure space after sentence end
        
        return cleaned.strip()
    
    def _insert_environments(self, text: str, environments: List[AcademicEnvironment]) -> str:
        """Insert LaTeX environment markup into text"""
        result = text
        offset = 0
        
        for env in reversed(environments):  # Reverse to maintain positions
            start, end = env.position
            
            # Build environment LaTeX
            env_start = env.latex_begin
            if env.label:
                env_start += f"\n{env.label}"
            env_start += "\n"
            
            env_end = f"\n{env.latex_end}"
            
            # Insert into text
            adjusted_start = start + offset
            adjusted_end = end + offset
            
            result = (result[:adjusted_start] + 
                     env_start + env.content + env_end + 
                     result[adjusted_end:])
            
            offset += len(env_start + env.content + env_end) - (end - start)
        
        return result
    
    def _generate_latex_document(self, content: str, 
                                title: str = None,
                                author: str = None,
                                doc_class: str = "article",
                                environments: List[AcademicEnvironment] = None,
                                math_expressions: List = None) -> str:
        """Generate complete LaTeX document with appropriate packages"""
        
        # Determine required packages based on content analysis
        packages = ['amsmath', 'amssymb', 'amsthm']  # Basic math packages
        
        # Add packages based on detected content
        if environments and any(env.env_type in ['theorem', 'lemma', 'proof'] for env in environments):
            packages.append('amsthm')
        
        if any('\\frac' in content, '\\int' in content, '\\sum' in content):
            packages.append('amsmath')
        
        if '\\mathbb' in content:
            packages.append('amssymb')
        
        # Generate document header
        latex_doc = f"\\documentclass[12pt]{{{doc_class}}}\n\n"
        
        # Add packages
        for package in sorted(set(packages)):
            latex_doc += f"\\usepackage{{{package}}}\n"
        
        latex_doc += "\n"
        
        # Add theorem environments if needed
        if environments:
            env_types = set(env.env_type for env in environments)
            if env_types & {'theorem', 'lemma', 'proposition', 'corollary', 'definition', 'example', 'remark'}:
                latex_doc += "% Theorem environments\n"
                for env_type in sorted(env_types):
                    if env_type != 'proof':  # proof is built-in
                        latex_doc += f"\\newtheorem{{{env_type}}}{{{{env_type.title()}}}}\n"
                latex_doc += "\n"
        
        # Add title and author if provided
        if title:
            latex_doc += f"\\title{{{title}}}\n"
        if author:
            latex_doc += f"\\author{{{author}}}\n"
        
        if title or author:
            latex_doc += "\\date{\\today}\n\n"
        
        # Begin document
        latex_doc += "\\begin{document}\n\n"
        
        # Add title page if title/author provided
        if title or author:
            latex_doc += "\\maketitle\n\n"
        
        # Add the reconstructed content
        latex_doc += content
        
        # End document
        latex_doc += "\n\n\\end{document}\n"
        
        return latex_doc

def main():
    """
    Command line interface for the LaTeX reconstruction engine
    """
    parser = argparse.ArgumentParser(
        description="Reconstruct LaTeX source from OCR text output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python latex_reconstructor.py ocr_output.txt
    python latex_reconstructor.py text.txt --output paper.tex --title "My Paper" --author "Dr. Smith"
    python latex_reconstructor.py extracted.txt --class article --verbose
        """
    )
    
    parser.add_argument('input_file', help='Input text file from OCR output')
    parser.add_argument('--output', '-o', help='Output LaTeX file path')
    parser.add_argument('--title', help='Document title')
    parser.add_argument('--author', help='Document author')
    parser.add_argument('--class', dest='doc_class', default='article', 
                       help='LaTeX document class (default: article)')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate input file
    if not Path(args.input_file).exists():
        logger.error(f"Input file not found: {args.input_file}")
        return 1
    
    # Set default output path
    if not args.output:
        input_path = Path(args.input_file)
        args.output = input_path.stem + '_reconstructed.tex'
    
    try:
        # Read OCR text
        with open(args.input_file, 'r', encoding='utf-8') as f:
            ocr_text = f.read()
        
        logger.info(f"📖 Read {len(ocr_text)} characters from {args.input_file}")
        
        # Initialize reconstructor
        reconstructor = LaTeXDocumentReconstructor()
        
        # Perform reconstruction
        latex_document = reconstructor.reconstruct_document(
            ocr_text,
            document_title=args.title,
            author_name=args.author,
            document_class=args.doc_class
        )
        
        # Save result
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(latex_document)
        
        print(f"\n🎉 LaTeX reconstruction successful!")
        print(f"📄 Original OCR text: {len(ocr_text)} characters")
        print(f"📜 Generated LaTeX: {len(latex_document)} characters")
        print(f"💾 Saved to: {args.output}")
        
        # Show preview
        print(f"\n📖 Preview of reconstructed LaTeX:")
        print("=" * 60)
        preview_lines = latex_document.split('\n')[:30]
        print('\n'.join(preview_lines))
        if len(latex_document.split('\n')) > 30:
            print("...")
        
    except Exception as e:
        logger.error(f"Reconstruction failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())