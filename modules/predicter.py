import importlib.util
import os

import numpy

# Keras 3 defaults to the TensorFlow backend, which has no Python 3.14 wheels.
# opennsfw2 only runs inference, so any installed backend works; pick one that
# is actually present before opennsfw2 imports keras.
if "KERAS_BACKEND" not in os.environ:
    for _backend in ("torch", "tensorflow", "jax"):
        if importlib.util.find_spec(_backend) is not None:
            os.environ["KERAS_BACKEND"] = _backend
            break

# TensorFlow is only needed when the optional NSFW filter is used. Keep it
# out of the normal app startup, and configure GPU memory before Keras loads it.
if os.environ.get("KERAS_BACKEND") == "tensorflow":
    try:
        import tensorflow as _tensorflow

        for _gpu in _tensorflow.config.experimental.list_physical_devices("GPU"):
            _tensorflow.config.experimental.set_memory_growth(_gpu, True)
    except Exception as _error:
        print(f"[nsfw] TensorFlow GPU memory growth unavailable: {_error}", flush=True)

import opennsfw2
from PIL import Image
import cv2  # Add OpenCV import
import modules.globals  # Import globals to access the color correction toggle
from modules.gpu_processing import gpu_cvt_color

from modules.typing import Frame

MAX_PROBABILITY = 0.85

# Preload the model once for efficiency
model = None

def predict_frame(target_frame: Frame) -> bool:
    # Convert the frame to RGB before processing if color correction is enabled
    if modules.globals.color_correction:
        target_frame = gpu_cvt_color(target_frame, cv2.COLOR_BGR2RGB)
        
    image = Image.fromarray(target_frame)
    image = opennsfw2.preprocess_image(image, opennsfw2.Preprocessing.YAHOO)
    global model
    if model is None: 
        model = opennsfw2.make_open_nsfw_model()
        
    views = numpy.expand_dims(image, axis=0)
    _, probability = model.predict(views)[0]
    return probability > MAX_PROBABILITY


def predict_image(target_path: str) -> bool:
    return opennsfw2.predict_image(target_path) > MAX_PROBABILITY


def predict_video(target_path: str) -> bool:
    _, probabilities = opennsfw2.predict_video_frames(video_path=target_path, frame_interval=100)
    return any(probability > MAX_PROBABILITY for probability in probabilities)
