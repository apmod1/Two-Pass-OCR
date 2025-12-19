#!/usr/bin/env python3
"""
pypdf Image OCR Text Extractor
The scrappy underdog approach to PDF text liberation
"""

import pypdf

from PIL import Image
import io
import os
import argparse
from pathlib import Path
import logging
 # The heavy lifter for page-to-image conversion

# Configure logging to track our digital carnage


def extract_embedded_images_pypdf( pdf_path, save_path=None):
    """
    Extract directly embedded images using pypdf's image extraction
    This is pypdf's party trick - finding images hiding in the PDF structure
    Now with the added fuck-you power of actually saving the damn things
    
    Args:
        pdf_path: Path to the PDF file
        save_path: Directory path where images should be saved (creates if doesn't exist)
        
    Returns:
        List of PIL Image objects from embedded images
    """
    images = []
    
    # Create save directory if specified and doesn't exist
    if save_path:
        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Image graveyard established at: {save_dir}")
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            logger.info(f"pypdf found {len(pdf_reader.pages)} pages to ransack")
            
            image_counter = 0  # Global counter for unique filenames
            
            for page_num, page in enumerate(pdf_reader.pages):
                # pypdf stores images in the page's resources under /XObject
                if '/XObject' in page['/Resources']:
                    xobjects = page['/Resources']['/XObject']
                    
                    for obj_name in xobjects:
                        obj = xobjects[obj_name]
                        
                        # Check if this XObject is actually an image
                        if obj.get('/Subtype') == '/Image':
                            try:
                                # Extract the image data - this is where pypdf gets sneaky
                                img_data = obj.get_data()
                                pil_image = None
                                
                                # Try to create PIL Image from the raw data
                                if obj.get('/Filter') in ['/DCTDecode', '/JPXDecode']:
                                    # JPEG or JPEG2000 - can directly load
                                    pil_image = Image.open(io.BytesIO(img_data))
                                    images.append(pil_image)
                                    logger.debug(f"Extracted embedded image from page {page_num + 1}")
                                    
                                elif obj.get('/Filter') == '/FlateDecode':
                                    # PNG-like compressed data - more complex reconstruction
                                    width = obj.get('/Width')
                                    height = obj.get('/Height')
                                    color_space = obj.get('/ColorSpace')
                                    
                                    # Basic image reconstruction (this gets hairy fast)
                                    if color_space == '/DeviceRGB':
                                        mode = 'RGB'
                                    elif color_space == '/DeviceGray':
                                        mode = 'L'
                                    else:
                                        logger.warning(f"Unsupported color space: {color_space}")
                                        continue
                                        
                                    pil_image = Image.frombytes(mode, (width, height), img_data)
                                    images.append(pil_image)
                                    logger.debug(f"Reconstructed compressed image from page {page_num + 1}")
                                
                                # Save the image if we successfully extracted it and have a save path
                                if pil_image and save_path:
                                    # Create a meaningful filename with page info and counter
                                    filename = f"page_{page_num + 1:03d}_img_{image_counter:03d}.png"
                                    save_filepath = save_dir / filename
                                    
                                    # Save as PNG to preserve quality and avoid format fuckery
                                    pil_image.save(save_filepath, 'PNG')
                                    logger.info(f"Image saved: {filename}")
                                    image_counter += 1
                                        
                            except Exception as e:
                                logger.warning(f"Failed to extract embedded image from page {page_num + 1}: {e}")
                                continue
            
            logger.info(f"pypdf extracted {len(images)} embedded images")
            if save_path and images:
                logger.info(f"All {len(images)} images successfully dumped to {save_dir}")
            
    except Exception as e:
        logger.error(f"pypdf image extraction failed like a corrupted hard drive: {e}")
        
    return images


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

pdf_path = "KIC Document 0001_1756228704626.pdf"

extract_embedded_images_pypdf(pdf_path, "foo")