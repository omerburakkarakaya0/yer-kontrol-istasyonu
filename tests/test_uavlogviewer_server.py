import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.uavlogviewer_server import UAVLogViewerServer


class UAVLogViewerServerTest(unittest.TestCase):
    def test_discovers_analysis_caches_without_mixing_unrelated_maps(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            primary = root / "main.mbtiles"
            analysis_b = root / "analysis_b.mbtiles"
            analysis_a = root / "analysis_a.mbtiles"
            unrelated = root / "mission_map.mbtiles"
            for path in (primary, analysis_b, analysis_a, unrelated):
                path.touch()

            with patch("core.uavlogviewer_server.config.MAP_MBTILES_PATH", str(primary)), patch(
                "core.uavlogviewer_server.config.ANALYSIS_MBTILES_GLOB", "analysis_*.mbtiles"
            ):
                discovered = UAVLogViewerServer._discover_mbtiles(None)

            self.assertEqual(
                discovered,
                [primary.resolve(), analysis_a.resolve(), analysis_b.resolve()],
            )

    def test_explicit_mbtiles_source_stays_isolated(self):
        with TemporaryDirectory() as directory:
            selected = Path(directory) / "selected.mbtiles"
            selected.touch()

            self.assertEqual(
                UAVLogViewerServer._discover_mbtiles(selected),
                [selected.resolve()],
            )


if __name__ == "__main__":
    unittest.main()
