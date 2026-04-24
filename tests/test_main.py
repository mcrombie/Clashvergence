import types
import unittest
from unittest.mock import patch

import main as clash_main


class MainCliTests(unittest.TestCase):
    def test_build_map_generation_overrides_uses_seed_when_map_seed_is_absent(self):
        args = types.SimpleNamespace(
            map_style=None,
            map_seed=None,
            map_regions=None,
            map_landmasses=None,
            map_water=None,
            map_rivers=None,
            map_mountains=None,
            map_climate=None,
            map_richness=None,
            map_chokepoints=None,
            map_diversity=None,
            map_starts=None,
            seed="run-seed",
        )

        overrides = clash_main.build_map_generation_overrides(args)
        self.assertEqual(overrides, {"seed": "run-seed"})

    def test_build_map_generation_overrides_prefers_map_seed(self):
        args = types.SimpleNamespace(
            map_style=None,
            map_seed="map-specific-seed",
            map_regions=None,
            map_landmasses=None,
            map_water=None,
            map_rivers=None,
            map_mountains=None,
            map_climate=None,
            map_richness=None,
            map_chokepoints=None,
            map_diversity=None,
            map_starts=None,
            seed="run-seed",
        )

        overrides = clash_main.build_map_generation_overrides(args)
        self.assertEqual(overrides, {"seed": "map-specific-seed"})

    def test_should_generate_ai_narrative_honors_explicit_modes(self):
        self.assertTrue(clash_main.should_generate_ai_narrative(types.SimpleNamespace(ai_narrative="on")))
        self.assertFalse(clash_main.should_generate_ai_narrative(types.SimpleNamespace(ai_narrative="off")))

    def test_should_generate_ai_narrative_auto_uses_environment_gate(self):
        with patch("main.is_ai_interpretation_enabled", return_value=True):
            self.assertTrue(clash_main.should_generate_ai_narrative(types.SimpleNamespace(ai_narrative="auto")))
        with patch("main.is_ai_interpretation_enabled", return_value=False):
            self.assertFalse(clash_main.should_generate_ai_narrative(types.SimpleNamespace(ai_narrative="auto")))


if __name__ == "__main__":
    unittest.main()
