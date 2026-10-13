"""Regression: high-DPI THS WM_PRINT must not clip the render surface."""
import unittest
import test_worker
import ths as m

class CaptureDpi(unittest.TestCase):
    def test_scale_matrix(self):
        for dpi, expected in [(96,(1455,792)),(120,(1819,990)),(144,(2183,1188)),(240,(3638,1980))]:
            with self.subTest(dpi=dpi):
                self.assertEqual(m.capture_pixel_size(1455,792,dpi),expected)

    def test_missing_dpi_fails_closed(self):
        for dpi in [0, None, -1, 900]:
            with self.assertRaisesRegex(RuntimeError,'CAPTURE_DPI_UNAVAILABLE'):
                m.capture_pixel_size(1455,792,dpi)

    def test_native_allocation_is_bounded(self):
        with self.assertRaisesRegex(RuntimeError,'CAPTURE_SIZE_UNSUPPORTED'):
            m.capture_pixel_size(8000,8000,240)
        with self.assertRaisesRegex(RuntimeError,'WINDOW_NOT_CAPTURE_READY'):
            m.capture_pixel_size(0,0,96)
