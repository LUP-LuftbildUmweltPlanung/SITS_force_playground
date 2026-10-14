import unittest
from unittest.mock import MagicMock, patch

from utils.utils import (
    build_internal_overviews,
    build_delivery_output_path,
    build_udf_output_name,
    validate_overview_options,
)


class UdfOutputNamingTest(unittest.TestCase):
    def test_preserves_year_and_doy_ranges(self):
        self.assertEqual(
            build_udf_output_name(
                "2018-2018_001-365_HL_UDF_SEN2L_PYP.tif",
                "NBR",
                "median",
            ),
            "2018-2018_001-365_NBR_MEDIAN.tif",
        )

    def test_sanitizes_index_and_metric(self):
        self.assertEqual(
            build_udf_output_name(
                "2020-2022_091-273_HL_UDF_SEN2L_PYP.tif",
                "my index",
                "q50/monthly",
            ),
            "2020-2022_091-273_MY-INDEX_Q50-MONTHLY.tif",
        )

    def test_delivery_uses_original_aoi_directory_layout(self):
        aoi = "/data/aoi/germany.shp"
        force_name = "2018-2018_001-365_HL_UDF_SEN2L_PYP.tif"
        product = build_udf_output_name(force_name, "NBR", "median")

        self.assertEqual(
            build_delivery_output_path("/results/nbr", aoi, product),
            "/results/nbr/germany.shp/2018-2018_001-365_NBR_MEDIAN.tif",
        )


class OverviewOptionsTest(unittest.TestCase):
    def test_normalizes_valid_options(self):
        self.assertEqual(
            validate_overview_options([2, "4", 8], "AVERAGE"),
            ((2, 4, 8), "average"),
        )

    def test_rejects_invalid_levels(self):
        for levels in ([], [1, 2], [2, 2], [4, 2]):
            with self.subTest(levels=levels):
                with self.assertRaises(ValueError):
                    validate_overview_options(levels, "average")

    def test_rejects_invalid_resampling(self):
        with self.assertRaisesRegex(ValueError, "overview_resampling"):
            validate_overview_options([2, 4], "not-a-method")

    @patch("utils.utils.subprocess.run")
    @patch("utils.utils.rasterio.open")
    def test_accepts_effective_factor_for_rounded_overview_size(
        self, rasterio_open, subprocess_run
    ):
        dataset = MagicMock()
        dataset.width = 3000
        dataset.count = 1
        dataset.overviews.return_value = [2, 4, 8, 16, 32, 64, 125]
        rasterio_open.return_value.__enter__.return_value = dataset

        build_internal_overviews(
            "one_tile.tif", [2, 4, 8, 16, 32, 64, 128], "average"
        )

        subprocess_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
