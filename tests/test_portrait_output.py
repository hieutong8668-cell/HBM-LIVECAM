import unittest

import numpy as np

from modules.portrait import compose_portrait


class PortraitOutputTests(unittest.TestCase):
    def test_landscape_frame_becomes_720_by_1280(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        result = compose_portrait(frame)
        self.assertEqual(result.shape, (1280, 720, 3))

    def test_focus_bbox_moves_portrait_crop_toward_face(self):
        frame = np.zeros((90, 160, 3), dtype=np.uint8)
        frame[:, :, 0] = np.arange(160, dtype=np.uint8)[None, :]
        centered = compose_portrait(frame, output_size=(9, 16))
        focused = compose_portrait(
            frame, focus_bbox=(120, 20, 140, 70), output_size=(9, 16)
        )
        self.assertGreater(float(focused[:, :, 0].mean()), float(centered[:, :, 0].mean()))

    def test_existing_portrait_is_not_cropped(self):
        frame = np.arange(90 * 160 * 3, dtype=np.uint8).reshape(160, 90, 3)
        result = compose_portrait(frame, output_size=(90, 160))
        self.assertEqual(result.shape, frame.shape)
        np.testing.assert_array_equal(result, frame)


if __name__ == "__main__":
    unittest.main()
