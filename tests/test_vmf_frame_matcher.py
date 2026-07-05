import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tkcopy.utils.vmf_frame_matcher import extract_coarse_source_windows, _run_vmf_scan


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

    def test_run_vmf_scan_uses_embedded_vmf_api_and_writes_results(self):
        calls = {}

        class FakeConfig:
            def __init__(self):
                self.data_dir = None
                self.fps = None
                self.model = None
                self.device = None
                self.batch_size = None
                self.encode_inflight = None
                self.mirror = True
                self.cropdetect = True
                self.use_smooth = True
                self.ensure_dirs_called = False

            def ensure_dirs(self):
                self.ensure_dirs_called = True

        class FakeStore:
            def __init__(self, data_dir):
                self.data_dir = data_dir
                calls["store_data_dir"] = data_dir

        def fake_ensure_extractor(cfg):
            calls["cfg"] = cfg
            return "extractor"

        def fake_index_paths(paths, cfg, store, extractor):
            calls["paths"] = paths
            calls["index_cfg"] = cfg
            calls["index_store"] = store
            calls["extractor"] = extractor

        def fake_find_pairs(cfg, store):
            calls["find_cfg"] = cfg
            calls["find_store"] = store
            return ["pair-result"]

        def fake_to_json(results):
            calls["json_results"] = results
            return json.dumps([{"segments": [{"a_range": [1.0, 2.0], "b_range": [3.0, 4.0]}]}])

        fake_vmf = SimpleNamespace(
            Config=FakeConfig,
            Store=FakeStore,
            ensure_extractor=fake_ensure_extractor,
            index_paths=fake_index_paths,
            find_pairs=fake_find_pairs,
            to_json=fake_to_json,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            viral = root / "viral.mp4"
            source = root / "source.mp4"
            viral.write_bytes(b"viral")
            source.write_bytes(b"source")
            coarse_dir = root / "coarse"
            output_json = coarse_dir / "vmf_results.json"

            with (
                patch("tkcopy.utils.vmf_frame_matcher._prepare_vmf_runtime_env") as prepare_env,
                patch("tkcopy.utils.vmf_frame_matcher._load_embedded_vmf", return_value=fake_vmf),
            ):
                results = _run_vmf_scan(
                    viral,
                    source,
                    coarse_dir,
                    output_json,
                    vmf_fps=3.0,
                    model="dinov2_vits14",
                    device="cpu",
                    batch_size=32,
                    inflight=2,
                )
                written_results = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(results, [{"segments": [{"a_range": [1.0, 2.0], "b_range": [3.0, 4.0]}]}])
        self.assertEqual(written_results, results)
        prepare_env.assert_called_once()
        cfg = calls["cfg"]
        self.assertEqual(calls["paths"], [viral, source])
        self.assertEqual(calls["store_data_dir"], coarse_dir / "index")
        self.assertEqual(cfg.data_dir, coarse_dir / "index")
        self.assertEqual(cfg.fps, 3.0)
        self.assertEqual(cfg.model, "dinov2_vits14")
        self.assertEqual(cfg.device, "cpu")
        self.assertEqual(cfg.batch_size, 32)
        self.assertEqual(cfg.encode_inflight, 2)
        self.assertFalse(cfg.mirror)
        self.assertFalse(cfg.cropdetect)
        self.assertFalse(cfg.use_smooth)
        self.assertTrue(cfg.ensure_dirs_called)
        self.assertEqual(calls["json_results"], ["pair-result"])


if __name__ == "__main__":
    unittest.main()
