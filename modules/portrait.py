"""Portrait framing shared by live preview and saved media."""

from typing import Optional, Sequence, Tuple

import cv2
import numpy as np

OUTPUT_WIDTH = 720
OUTPUT_HEIGHT = 1280
OUTPUT_SIZE = (OUTPUT_WIDTH, OUTPUT_HEIGHT)


def compose_portrait(
    frame: np.ndarray,
    focus_bbox: Optional[Sequence[float]] = None,
    output_size: Tuple[int, int] = OUTPUT_SIZE,
) -> np.ndarray:
    """Center-crop a frame to 9:16 and resize it to the requested output."""
    if frame is None or frame.ndim < 2 or frame.size == 0:
        return frame

    height, width = frame.shape[:2]
    target_width, target_height = output_size
    target_ratio = target_width / target_height
    source_ratio = width / height

    if source_ratio > target_ratio:
        crop_width = max(1, min(width, int(round(height * target_ratio))))
        focus_x = width / 2
        if focus_bbox is not None and len(focus_bbox) >= 4:
            focus_x = (float(focus_bbox[0]) + float(focus_bbox[2])) / 2
        left = int(round(focus_x - crop_width / 2))
        left = max(0, min(width - crop_width, left))
        frame = frame[:, left:left + crop_width]
    elif source_ratio < target_ratio:
        crop_height = max(1, min(height, int(round(width / target_ratio))))
        top = max(0, (height - crop_height) // 2)
        frame = frame[top:top + crop_height, :]

    if frame.shape[1] != target_width or frame.shape[0] != target_height:
        frame = cv2.resize(
            frame, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4
        )
    return np.ascontiguousarray(frame)
