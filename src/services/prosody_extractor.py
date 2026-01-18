"""Prosody feature extraction service using Parselmouth."""
import logging
import numpy as np
from typing import Optional, Dict, Any
import parselmouth
from parselmouth.praat import call
from scipy import stats

logger = logging.getLogger(__name__)


class ProsodyExtractor:
    """Extract prosodic features from audio using Parselmouth/Praat."""
    
    def __init__(self, target_sample_rate: int = 16000):
        """
        Initialize prosody extractor.
        
        Args:
            target_sample_rate: Sample rate for Parselmouth processing (16kHz recommended)
        """
        self.target_sample_rate = target_sample_rate
    
    def extract_features(
        self, 
        audio: np.ndarray, 
        sample_rate: int
    ) -> Dict[str, Any]:
        """
        Extract prosodic features from audio.
        
        Args:
            audio: Audio data as numpy array (float32, range -1 to 1)
            sample_rate: Original sample rate of the audio
            
        Returns:
            Dictionary of prosodic features, with None for failed extractions
        """
        features = {
            "pitch_mean_hz": None,
            "pitch_min_hz": None,
            "pitch_max_hz": None,
            "pitch_stdev": None,
            "pitch_range_hz": None,
            "final_pitch_slope": None,
            "intensity_mean_db": None,
            "intensity_max_db": None,
            "intensity_stdev": None,
            "final_intensity_slope": None,
            "jitter_local": None,
            "shimmer_local": None,
            "hnr_db": None,
            "voiced_fraction": None,
            "pause_count": None,
            "total_pause_duration_ms": None,
            "speech_rate_syllables_sec": None,
        }
        
        try:
            # Resample if needed
            if sample_rate != self.target_sample_rate:
                audio = self._resample(audio, sample_rate, self.target_sample_rate)
            
            # Create Parselmouth Sound object
            sound = parselmouth.Sound(audio, sampling_frequency=self.target_sample_rate)
            
            # Extract pitch features
            pitch_features = self._extract_pitch_features(sound)
            features.update(pitch_features)
            
            # Extract intensity features
            intensity_features = self._extract_intensity_features(sound)
            features.update(intensity_features)
            
            # Extract voice quality features
            quality_features = self._extract_voice_quality(sound)
            features.update(quality_features)
            
            # Extract rhythm/fluency features
            rhythm_features = self._extract_rhythm_features(sound)
            features.update(rhythm_features)
            
            logger.debug(f"Extracted prosody features: {sum(1 for v in features.values() if v is not None)}/{len(features)} successful")
            
        except Exception as e:
            logger.warning(f"Error extracting prosody features: {e}", exc_info=True)
        
        return features
    
    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate."""
        try:
            # Simple linear interpolation resampling
            duration = len(audio) / orig_sr
            target_length = int(duration * target_sr)
            
            # Use numpy's interp for simple resampling
            orig_time = np.linspace(0, duration, len(audio))
            target_time = np.linspace(0, duration, target_length)
            resampled = np.interp(target_time, orig_time, audio)
            
            return resampled.astype(np.float32)
        except Exception as e:
            logger.warning(f"Resampling failed: {e}")
            return audio
    
    def _extract_pitch_features(self, sound: parselmouth.Sound) -> Dict[str, Optional[float]]:
        """Extract pitch (F0) related features."""
        features = {
            "pitch_mean_hz": None,
            "pitch_min_hz": None,
            "pitch_max_hz": None,
            "pitch_stdev": None,
            "pitch_range_hz": None,
            "final_pitch_slope": None,
        }
        
        try:
            # Extract pitch with reasonable parameters for human speech
            pitch = sound.to_pitch(time_step=0.01, pitch_floor=75.0, pitch_ceiling=600.0)
            
            # Get pitch values (excluding unvoiced frames)
            pitch_values = pitch.selected_array['frequency']
            pitch_values = pitch_values[pitch_values > 0]  # Filter out unvoiced frames
            
            if len(pitch_values) > 0:
                features["pitch_mean_hz"] = float(np.mean(pitch_values))
                features["pitch_min_hz"] = float(np.min(pitch_values))
                features["pitch_max_hz"] = float(np.max(pitch_values))
                features["pitch_stdev"] = float(np.std(pitch_values))
                features["pitch_range_hz"] = float(np.max(pitch_values) - np.min(pitch_values))
                
                # Calculate final pitch slope (last 200ms)
                duration = sound.duration
                if duration >= 0.2:
                    final_slope = self._calculate_final_slope(pitch, duration, window_ms=200)
                    if final_slope is not None:
                        features["final_pitch_slope"] = final_slope
        
        except Exception as e:
            logger.debug(f"Pitch extraction failed: {e}")
        
        return features
    
    def _extract_intensity_features(self, sound: parselmouth.Sound) -> Dict[str, Optional[float]]:
        """Extract intensity (loudness) features."""
        features = {
            "intensity_mean_db": None,
            "intensity_max_db": None,
            "intensity_stdev": None,
            "final_intensity_slope": None,
        }
        
        try:
            intensity = sound.to_intensity(time_step=0.01)
            intensity_values = intensity.values[0]
            intensity_values = intensity_values[intensity_values > 0]  # Filter invalid values
            
            if len(intensity_values) > 0:
                features["intensity_mean_db"] = float(np.mean(intensity_values))
                features["intensity_max_db"] = float(np.max(intensity_values))
                features["intensity_stdev"] = float(np.std(intensity_values))
                
                # Calculate final intensity slope
                duration = sound.duration
                if duration >= 0.2:
                    final_slope = self._calculate_final_slope(intensity, duration, window_ms=200)
                    if final_slope is not None:
                        features["final_intensity_slope"] = final_slope
        
        except Exception as e:
            logger.debug(f"Intensity extraction failed: {e}")
        
        return features
    
    def _extract_voice_quality(self, sound: parselmouth.Sound) -> Dict[str, Optional[float]]:
        """Extract voice quality features (jitter, shimmer, HNR)."""
        features = {
            "jitter_local": None,
            "shimmer_local": None,
            "hnr_db": None,
        }
        
        try:
            # Create PointProcess for jitter/shimmer
            point_process = call(sound, "To PointProcess (periodic, cc)", 75, 600)
            
            # Jitter (pitch perturbation)
            try:
                jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
                if not np.isnan(jitter) and not np.isinf(jitter):
                    features["jitter_local"] = float(jitter)
            except Exception as e:
                logger.debug(f"Jitter calculation failed: {e}")
            
            # Shimmer (amplitude perturbation)
            try:
                shimmer = call([sound, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
                if not np.isnan(shimmer) and not np.isinf(shimmer):
                    features["shimmer_local"] = float(shimmer)
            except Exception as e:
                logger.debug(f"Shimmer calculation failed: {e}")
            
            # Harmonics-to-Noise Ratio
            try:
                harmonicity = sound.to_harmonicity(time_step=0.01, minimum_pitch=75.0)
                hnr_values = harmonicity.values[0]
                hnr_values = hnr_values[~np.isnan(hnr_values) & ~np.isinf(hnr_values)]
                if len(hnr_values) > 0:
                    features["hnr_db"] = float(np.mean(hnr_values))
            except Exception as e:
                logger.debug(f"HNR calculation failed: {e}")
        
        except Exception as e:
            logger.debug(f"Voice quality extraction failed: {e}")
        
        return features
    
    def _extract_rhythm_features(self, sound: parselmouth.Sound) -> Dict[str, Optional[float]]:
        """Extract rhythm and fluency features."""
        features = {
            "voiced_fraction": None,
            "pause_count": None,
            "total_pause_duration_ms": None,
            "speech_rate_syllables_sec": None,
        }
        
        try:
            duration = sound.duration
            
            # Voiced fraction
            pitch = sound.to_pitch(time_step=0.01, pitch_floor=75.0, pitch_ceiling=600.0)
            pitch_values = pitch.selected_array['frequency']
            voiced_frames = np.sum(pitch_values > 0)
            total_frames = len(pitch_values)
            if total_frames > 0:
                features["voiced_fraction"] = float(voiced_frames / total_frames)
            
            # Pause detection (intensity-based)
            intensity = sound.to_intensity(time_step=0.01)
            intensity_values = intensity.values[0]
            
            # Define pause threshold (mean - 1.5 * std)
            valid_intensity = intensity_values[intensity_values > 0]
            if len(valid_intensity) > 0:
                threshold = np.mean(valid_intensity) - 1.5 * np.std(valid_intensity)
                
                # Detect pauses (consecutive frames below threshold)
                is_pause = intensity_values < threshold
                pause_count = 0
                total_pause_duration = 0.0
                in_pause = False
                pause_start = 0
                
                min_pause_frames = int(0.15 / 0.01)  # 150ms minimum
                
                for i, is_p in enumerate(is_pause):
                    if is_p and not in_pause:
                        in_pause = True
                        pause_start = i
                    elif not is_p and in_pause:
                        pause_length = i - pause_start
                        if pause_length >= min_pause_frames:
                            pause_count += 1
                            total_pause_duration += pause_length * 0.01  # Convert to seconds
                        in_pause = False
                
                features["pause_count"] = pause_count
                features["total_pause_duration_ms"] = float(total_pause_duration * 1000)
            
            # Speech rate estimation (syllable counting via intensity peaks)
            if len(valid_intensity) > 0:
                # Smooth intensity
                from scipy.ndimage import gaussian_filter1d
                smoothed = gaussian_filter1d(valid_intensity, sigma=2)
                
                # Find peaks (syllable nuclei)
                from scipy.signal import find_peaks
                peaks, _ = find_peaks(smoothed, distance=5, prominence=2)
                
                syllable_count = len(peaks)
                if duration > 0:
                    features["speech_rate_syllables_sec"] = float(syllable_count / duration)
        
        except Exception as e:
            logger.debug(f"Rhythm feature extraction failed: {e}")
        
        return features
    
    def _calculate_final_slope(
        self, 
        contour: Any, 
        duration: float, 
        window_ms: int = 200
    ) -> Optional[float]:
        """
        Calculate slope over final window of a contour (pitch or intensity).
        
        Args:
            contour: Parselmouth Pitch or Intensity object
            duration: Total duration in seconds
            window_ms: Window size in milliseconds
            
        Returns:
            Slope value (Hz/s for pitch, dB/s for intensity) or None
        """
        try:
            window_sec = window_ms / 1000.0
            start_time = max(0, duration - window_sec)
            
            # Get values in the final window
            times = []
            values = []
            
            # Sample at 10ms intervals
            t = start_time
            while t <= duration:
                try:
                    value = contour.get_value(t)
                    if value is not None and value > 0 and not np.isnan(value):
                        times.append(t)
                        values.append(value)
                except Exception:
                    pass
                t += 0.01
            
            if len(times) >= 3:  # Need at least 3 points for meaningful slope
                # Linear regression
                slope, _, _, _, _ = stats.linregress(times, values)
                if not np.isnan(slope) and not np.isinf(slope):
                    return float(slope)
        
        except Exception as e:
            logger.debug(f"Slope calculation failed: {e}")
        
        return None
