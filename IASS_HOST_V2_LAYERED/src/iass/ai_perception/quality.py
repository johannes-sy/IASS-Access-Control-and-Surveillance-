"""Face quality gates used before recognition."""
from dataclasses import dataclass
import cv2
import numpy as np

@dataclass
class QualityResult:
    accepted: bool
    score: float
    blur: float
    brightness: float
    reason: str = "OK"

class FaceQualityGate:
    def __init__(self, min_size=45, min_blur=20.0, min_brightness=25.0, max_brightness=235.0):
        self.min_size = int(min_size)
        self.min_blur = float(min_blur)
        self.min_brightness = float(min_brightness)
        self.max_brightness = float(max_brightness)

    def assess(self, crop):
        if crop is None or crop.size == 0:
            return QualityResult(False, 0.0, 0.0, 0.0, "EMPTY")
        h, w = crop.shape[:2]
        if min(h, w) < self.min_size:
            return QualityResult(False, 0.0, 0.0, 0.0, "TOO_SMALL")
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(np.mean(gray))
        if blur < self.min_blur:
            return QualityResult(False, min(1.0, blur / max(self.min_blur, 1.0)), blur, brightness, "BLURRY")
        if brightness < self.min_brightness:
            return QualityResult(False, brightness / max(self.min_brightness, 1.0), blur, brightness, "TOO_DARK")
        if brightness > self.max_brightness:
            return QualityResult(False, 1.0 - min(1.0, (brightness-self.max_brightness)/25.0), blur, brightness, "OVEREXPOSED")
        sharp_score = min(1.0, blur / max(self.min_blur * 5.0, 1.0))
        light_score = 1.0 - min(1.0, abs(brightness-128.0)/128.0)
        return QualityResult(True, round(0.7*sharp_score + 0.3*light_score, 3), blur, brightness)
