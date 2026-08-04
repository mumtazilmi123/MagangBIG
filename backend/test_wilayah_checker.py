import os
import sys
import unittest

# Tambahkan direktori backend ke sys.path
sys.path.insert(0, os.path.dirname(__file__))

from modules.wilayah import WilayahDatabase
from modules.wilayah_checker import audit_wilayah_consistency, calculate_name_similarity, identify_table_columns

class TestWilayahChecker(unittest.TestCase):
    def setUp(self):
        self.db = WilayahDatabase()

    def test_identify_table_columns_flexibility(self):
        header1 = ["No", "Kode Wilayah", "Desa/Kelurahan", "Kecamatan", "Kabupaten/Kota", "Provinsi"]
        cols1 = identify_table_columns(header1)
        self.assertEqual(cols1.get("code"), 1)
        self.assertEqual(cols1.get("desa"), 2)
        self.assertEqual(cols1.get("kecamatan"), 3)
        self.assertEqual(cols1.get("kabupaten"), 4)
        self.assertEqual(cols1.get("provinsi"), 5)

        # Swapped positions
        header2 = ["Desa", "Kec", "Kab", "Kodifikasi", "Prov"]
        cols2 = identify_table_columns(header2)
        self.assertEqual(cols2.get("desa"), 0)
        self.assertEqual(cols2.get("kecamatan"), 1)
        self.assertEqual(cols2.get("kabupaten"), 2)
        self.assertEqual(cols2.get("code"), 3)
        self.assertEqual(cols2.get("provinsi"), 4)

    def test_name_similarity(self):
        self.assertTrue(calculate_name_similarity("Blang Teue", "DESA BLANG TEUE"))
        self.assertTrue(calculate_name_similarity("Blang Mangat", "Kecamatan Blang Mangat"))
        self.assertFalse(calculate_name_similarity("Blang Buloh", "Blang Teue"))

    def test_hierarchy_validation_example_cases(self):
        val = self.db.validate_hierarchy("11.73.03.2017")
        self.assertTrue(val.get("hierarchy_valid"))
        details = val.get("hierarchy_details", {})
        self.assertIsNotNone(details.get("desa", {}).get("name"))
        self.assertEqual(details.get("kecamatan", {}).get("name"), "Blang Mangat")
        self.assertIn("Lhokseumawe", details.get("kabupaten", {}).get("name", ""))

    def test_reverse_code_lookup(self):
        from modules.wilayah_checker import find_code_by_written_names
        # Case: Desa Alue Lim, Kec Blang Mangat, Kab Kota Lhokseumawe -> should find 11.73.03.2017
        found_code = find_code_by_written_names(self.db, "Alue Lim", "Blang Mangat", "Kota Lhokseumawe")
        self.assertEqual(found_code, "11.73.03.2017")

    def test_majority_validation_logic(self):
        # We test similarity and reverse lookup logic
        self.assertTrue(calculate_name_similarity("Alue Lim", "DESA ALUE LIM"))
        self.assertFalse(calculate_name_similarity("Blang Buloh", "Alue Lim"))


if __name__ == "__main__":
    unittest.main()

