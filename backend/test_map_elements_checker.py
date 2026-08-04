import os
import sys
import unittest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))

from modules.map_elements_checker import inspect_map_elements

class TestMapElementsChecker(unittest.TestCase):
    def setUp(self):
        # Create a synthetic map image for testing
        self.img = Image.new('RGB', (800, 800), color='white')
        draw = ImageDraw.Draw(self.img)
        # Draw border
        draw.rectangle([20, 20, 780, 780], outline='black', width=3)
        # Draw title area
        draw.rectangle([250, 40, 550, 80], fill='lightgray', outline='black')
        # Draw legend box
        draw.rectangle([600, 600, 760, 760], fill='whitesmoke', outline='black')

    def test_inspect_map_elements_structure(self):
        res = inspect_map_elements(self.img, pdf_text="PETA KARTOMETRIK BATAS DESA ALUE LIM Skala 1:25.000 Legenda Keterangan Grid UTM Lintang Bujur North Utara")
        self.assertIn("status", res)
        self.assertIn("items", res)
        self.assertEqual(len(res["items"]), 10)

        names = [item["nama_unsur"] for item in res["items"]]
        expected_names = [
            "Judul Peta", "Legenda / Keterangan", "Kesesuaian Legenda", "Grid Koordinat",
            "Label Koordinat", "Arah Utara", "Skala", "Bingkai Peta", "Diagram Lokasi / Inset", "Kualitas Peta"
        ]
        self.assertEqual(names, expected_names)

        # Verify title detected
        title_item = next(i for i in res["items"] if i["nama_unsur"] == "Judul Peta")
        self.assertEqual(title_item["status"], "Ada")
        self.assertGreaterEqual(title_item["confidence"], 80)

        # Verify scale detected
        scale_item = next(i for i in res["items"] if i["nama_unsur"] == "Skala")
        self.assertEqual(scale_item["status"], "Ada")

if __name__ == "__main__":
    unittest.main()
