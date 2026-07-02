import unittest
from pathlib import Path

from tkcopy.utils.vmf_frame_matcher import extract_coarse_source_windows


class VMFFrameMatcherTests(unittest.TestCase):
    def test_extract_coarse_source_windows_handles_path_order_and_merges_padding(self):
        viral = Path("/tmp/viral.mp4")
        source = Path("/tmp/source.mkv")
        raw_results = [
            {
                "a": {"path": str(source)},
                "b": {"path": str(viral)},
                "segments": [
                    {"a_range": [100.0, 120.0], "b_range": [0.0, 20.0]},
                    {"a_range": [125.0, 140.0], "b_range": [21.0, 36.0]},
                ],
            },
            {
                "a": {"path": str(viral)},
                "b": {"path": str(source)},
                "segments": [
                    {"a_range": [40.0, 55.0], "b_range": [280.0, 300.0]},
                ],
            },
        ]

        windows = extract_coarse_source_windows(
            raw_results,
            viral,
            source,
            source_duration=320.0,
            padding_seconds=10.0,
        )

        self.assertEqual(windows, [(90.0, 150.0), (270.0, 310.0)])


if __name__ == "__main__":
    unittest.main()
