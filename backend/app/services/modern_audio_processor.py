"""
Modern Audio Processing Module - Python 3.13 Compatible
Replaces deprecated audioop module with modern alternatives using soundfile, numpy, and scipy
"""

import sys
import logging
import numpy as np
from typing import Optional, Tuple, Union

# Setup logging
logger = logging.getLogger(__name__)

# Flag to track availability
AUDIO_PROCESSING_AVAILABLE = False

# Try to import modern audio processing libraries
try:
    import soundfile as sf
    import scipy.signal
    AUDIO_PROCESSING_AVAILABLE = True
    logger.info("✅ Modern audio processing libraries available (soundfile, scipy)")
except ImportError as e:
    logger.warning(f"⚠️ Modern audio processing libraries not available: {e}")
    sf = None
    scipy = None

class ModernAudioProcessor:
    """
    Modern replacement for audioop functions using soundfile, numpy, and scipy
    Compatible with Python 3.13+
    """
    
    def __init__(self):
        self.available = AUDIO_PROCESSING_AVAILABLE
        
    def ratecv(self, fragment: bytes, width: int, nchannels: int, 
               inrate: int, outrate: int, state=None, 
               weightA: int = 1, weightB: int = 0) -> Tuple[bytes, Optional[object]]:
        """
        Modern replacement for audioop.ratecv using scipy
        Convert audio sample rate
        """
        if not self.available:
            logger.warning("Audio processing not available - returning original fragment")
            return fragment, state
            
        try:
            # Convert bytes to numpy array
            if width == 1:
                dtype = np.int8
            elif width == 2:
                dtype = np.int16
            elif width == 4:
                dtype = np.int32
            else:
                raise ValueError(f"Unsupported width: {width}")
                
            # Convert bytes to numpy array
            audio_data = np.frombuffer(fragment, dtype=dtype)
            
            # Reshape for multiple channels
            if nchannels > 1:
                audio_data = audio_data.reshape(-1, nchannels)
            
            # Convert to float for processing
            audio_float = audio_data.astype(np.float32)
            if width == 1:
                audio_float /= 128.0
            elif width == 2:
                audio_float /= 32768.0
            elif width == 4:
                audio_float /= 2147483648.0
            
            # Resample using scipy
            if nchannels == 1:
                resampled = scipy.signal.resample(audio_float, 
                                                 int(len(audio_float) * outrate / inrate))
            else:
                resampled = np.array([scipy.signal.resample(audio_float[:, ch], 
                                                           int(len(audio_float) * outrate / inrate))
                                     for ch in range(nchannels)]).T
            
            # Convert back to original format
            if width == 1:
                resampled = (resampled * 128.0).astype(np.int8)
            elif width == 2:
                resampled = (resampled * 32768.0).astype(np.int16)
            elif width == 4:
                resampled = (resampled * 2147483648.0).astype(np.int32)
            
            # Convert back to bytes
            return resampled.tobytes(), state
            
        except Exception as e:
            logger.error(f"Error in ratecv: {e}")
            return fragment, state
    
    def lin2ulaw(self, fragment: bytes, width: int) -> bytes:
        """
        Modern replacement for audioop.lin2ulaw
        Convert linear samples to u-law encoding
        """
        if not self.available:
            logger.warning("Audio processing not available - returning original fragment")
            return fragment
            
        try:
            # Convert bytes to numpy array
            if width == 1:
                dtype = np.int8
                max_val = 128
            elif width == 2:
                dtype = np.int16
                max_val = 32768
            elif width == 4:
                dtype = np.int32
                max_val = 2147483648
            else:
                raise ValueError(f"Unsupported width: {width}")
                
            audio_data = np.frombuffer(fragment, dtype=dtype)
            
            # Normalize to [-1, 1]
            normalized = audio_data.astype(np.float32) / max_val
            
            # Apply u-law compression
            mu = 255.0
            sign = np.sign(normalized)
            abs_normalized = np.abs(normalized)
            
            # u-law formula: sign(x) * ln(1 + mu * |x|) / ln(1 + mu)
            compressed = sign * np.log(1 + mu * abs_normalized) / np.log(1 + mu)
            
            # Convert to 8-bit u-law
            ulaw_data = (compressed * 127.0).astype(np.int8)
            
            return ulaw_data.tobytes()
            
        except Exception as e:
            logger.error(f"Error in lin2ulaw: {e}")
            return fragment
    
    def ulaw2lin(self, fragment: bytes, width: int) -> bytes:
        """
        Modern replacement for audioop.ulaw2lin
        Convert u-law samples to linear encoding
        """
        if not self.available:
            logger.warning("Audio processing not available - returning original fragment")
            return fragment
            
        try:
            # Convert u-law bytes to numpy array
            ulaw_data = np.frombuffer(fragment, dtype=np.int8).astype(np.float32) / 127.0
            
            # Apply inverse u-law expansion
            mu = 255.0
            sign = np.sign(ulaw_data)
            abs_ulaw = np.abs(ulaw_data)
            
            # Inverse u-law formula: sign(y) * (exp(|y| * ln(1 + mu)) - 1) / mu
            expanded = sign * (np.exp(abs_ulaw * np.log(1 + mu)) - 1) / mu
            
            # Convert to target format
            if width == 1:
                linear_data = (expanded * 128).astype(np.int8)
            elif width == 2:
                linear_data = (expanded * 32768).astype(np.int16)
            elif width == 4:
                linear_data = (expanded * 2147483648).astype(np.int32)
            else:
                raise ValueError(f"Unsupported width: {width}")
                
            return linear_data.tobytes()
            
        except Exception as e:
            logger.error(f"Error in ulaw2lin: {e}")
            return fragment
    
    def mul(self, fragment: bytes, width: int, factor: float) -> bytes:
        """
        Modern replacement for audioop.mul
        Multiply audio samples by a factor
        """
        if not self.available:
            logger.warning("Audio processing not available - returning original fragment")
            return fragment
            
        try:
            # Convert bytes to numpy array
            if width == 1:
                dtype = np.int8
            elif width == 2:
                dtype = np.int16
            elif width == 4:
                dtype = np.int32
            else:
                raise ValueError(f"Unsupported width: {width}")
                
            audio_data = np.frombuffer(fragment, dtype=dtype)
            
            # Apply multiplication with clipping
            multiplied = (audio_data.astype(np.float32) * factor).clip(
                np.iinfo(dtype).min, np.iinfo(dtype).max
            ).astype(dtype)
            
            return multiplied.tobytes()
            
        except Exception as e:
            logger.error(f"Error in mul: {e}")
            return fragment
    
    def add(self, fragment1: bytes, fragment2: bytes, width: int) -> bytes:
        """
        Modern replacement for audioop.add
        Add two audio fragments
        """
        if not self.available:
            logger.warning("Audio processing not available - returning first fragment")
            return fragment1
            
        try:
            # Convert bytes to numpy arrays
            if width == 1:
                dtype = np.int8
            elif width == 2:
                dtype = np.int16
            elif width == 4:
                dtype = np.int32
            else:
                raise ValueError(f"Unsupported width: {width}")
                
            audio1 = np.frombuffer(fragment1, dtype=dtype)
            audio2 = np.frombuffer(fragment2, dtype=dtype)
            
            # Make arrays same length
            min_len = min(len(audio1), len(audio2))
            audio1 = audio1[:min_len]
            audio2 = audio2[:min_len]
            
            # Add with clipping
            added = (audio1.astype(np.float32) + audio2.astype(np.float32)).clip(
                np.iinfo(dtype).min, np.iinfo(dtype).max
            ).astype(dtype)
            
            return added.tobytes()
            
        except Exception as e:
            logger.error(f"Error in add: {e}")
            return fragment1

# Create global instance
modern_audio_processor = ModernAudioProcessor()

# Export compatibility functions
def ratecv(fragment: bytes, width: int, nchannels: int, 
           inrate: int, outrate: int, state=None, 
           weightA: int = 1, weightB: int = 0):
    """Compatibility wrapper for audioop.ratecv"""
    return modern_audio_processor.ratecv(fragment, width, nchannels, inrate, outrate, state, weightA, weightB)

def lin2ulaw(fragment: bytes, width: int):
    """Compatibility wrapper for audioop.lin2ulaw"""
    return modern_audio_processor.lin2ulaw(fragment, width)

def ulaw2lin(fragment: bytes, width: int):
    """Compatibility wrapper for audioop.ulaw2lin"""
    return modern_audio_processor.ulaw2lin(fragment, width)

def mul(fragment: bytes, width: int, factor: float):
    """Compatibility wrapper for audioop.mul"""
    return modern_audio_processor.mul(fragment, width, factor)

def add(fragment1: bytes, fragment2: bytes, width: int):
    """Compatibility wrapper for audioop.add"""
    return modern_audio_processor.add(fragment1, fragment2, width)

# Export all
__all__ = [
    'ModernAudioProcessor',
    'modern_audio_processor',
    'ratecv',
    'lin2ulaw', 
    'ulaw2lin',
    'mul',
    'add',
    'AUDIO_PROCESSING_AVAILABLE'
]
