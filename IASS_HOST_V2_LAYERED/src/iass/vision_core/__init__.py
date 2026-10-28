"""vision_core: shared low-level OpenCV/image primitives used by both
camera_stream (frame encoding) and ai_perception (geometry math), so neither
layer duplicates basic image-processing utilities."""
from .codec import encode_jpeg, decode_jpeg
from .geometry import iou, center

__all__ = ["encode_jpeg", "decode_jpeg", "iou", "center"]
