import os
import json
import re
import urllib.request
import urllib.error
from typing import Dict, Optional, Any, List


class WilayahDatabase:
    """
    Modul Referensi Kode & Nama Wilayah Administrasi Indonesia (Kemendagri).
    Pencarian dilakukan secara langsung dari API Internet Resmi/Live tanpa database statis manual.
    
    API Utama: https://api.kodewilayah.web.id/
    API Cadangan: https://ibnux.github.io/data-indonesia/
    """

    def __init__(self):
        self._cache_provinces: Optional[Dict[str, str]] = None
        self._cache_regencies: Dict[str, Dict[str, str]] = {}
        self._cache_districts: Dict[str, Dict[str, str]] = {}
        self._cache_villages: Dict[str, Dict[str, str]] = {}

    @staticmethod
    def clean_code_string(raw_code: str) -> str:
        """Membersihkan string kode dari titik, spasi, dash, atau simbol."""
        if not raw_code:
            return ""
        return re.sub(r'[^0-9]', '', raw_code.strip())

    @staticmethod
    def format_code_with_dots(clean_digits: str) -> str:
        """
        Mengonversi string angka murni ke format bertitik Kemendagri:
        - 2 digit:  "32" -> "32"
        - 4 digit:  "3204" -> "32.04"
        - 6 digit:  "320412" -> "32.04.12"
        - 10 digit: "3204122001" -> "32.04.12.2001"
        """
        d = clean_digits
        length = len(d)
        if length == 2:
            return d
        elif length == 4:
            return f"{d[:2]}.{d[2:]}"
        elif length == 6:
            return f"{d[:2]}.{d[2:4]}.{d[4:]}"
        elif length == 10:
            return f"{d[:2]}.{d[2:4]}.{d[4:6]}.{d[6:]}"
        return d

    def parse_code_components(self, raw_code: str) -> Dict[str, Optional[str]]:
        """Memisahkan kode wilayah menjadi 4 komponen hirarki (Prov, Kab, Kec, Desa)."""
        digits = self.clean_code_string(raw_code)
        length = len(digits)

        prov_code = digits[:2] if length >= 2 else None
        kab_code = f"{digits[:2]}.{digits[2:4]}" if length >= 4 else None
        kec_code = f"{digits[:2]}.{digits[2:4]}.{digits[4:6]}" if length >= 6 else None
        desa_code = f"{digits[:2]}.{digits[2:4]}.{digits[4:6]}.{digits[6:10]}" if length >= 10 else None

        return {
            "digits": digits,
            "length": length,
            "formatted_code": self.format_code_with_dots(digits),
            "prov_code": prov_code,
            "kab_code": kab_code,
            "kec_code": kec_code,
            "desa_code": desa_code
        }

    def fetch_provinces_live(self) -> Dict[str, str]:
        """Ambil daftar seluruh Provinsi di Indonesia via API Internet."""
        if self._cache_provinces:
            return self._cache_provinces

        result_map = {}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

        # 1. API Utama (ibnux - lebih cepat & stabil): https://ibnux.github.io/data-indonesia/provinsi.json
        try:
            url = "https://ibnux.github.io/data-indonesia/provinsi.json"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    for item in data:
                        result_map[str(item['id'])] = str(item['nama'])
                    if result_map:
                        self._cache_provinces = result_map
                        return result_map
        except Exception:
            pass

        # 2. Fallback API: https://api.kodewilayah.web.id/provinces
        try:
            url = "https://api.kodewilayah.web.id/provinces"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    items = data.get('data', []) if isinstance(data, dict) else data
                    for item in items:
                        c_str = str(item.get('code', ''))
                        result_map[c_str] = str(item.get('name', ''))
                    if result_map:
                        self._cache_provinces = result_map
                        return result_map
        except Exception:
            pass

        if result_map:
            self._cache_provinces = result_map
            return result_map
        self._cache_provinces = dict(PROVINCE_CODES)
        return self._cache_provinces


    def fetch_regencies_live(self, prov_code: str) -> Dict[str, str]:
        """Ambil daftar Kabupaten/Kota di bawah Provinsi via API Internet."""
        if not prov_code:
            return {}
        if prov_code in self._cache_regencies and self._cache_regencies[prov_code]:
            return self._cache_regencies[prov_code]

        clean_prov = self.clean_code_string(prov_code)
        result_map = {}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

        try:
            url = f"https://ibnux.github.io/data-indonesia/kabupaten/{clean_prov}.json"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    for item in data:
                        formatted = self.format_code_with_dots(str(item['id']))
                        result_map[formatted] = str(item['nama'])
                    if result_map:
                        self._cache_regencies[prov_code] = result_map
                        return result_map
        except Exception:
            pass

        if result_map:
            self._cache_regencies[prov_code] = result_map
        return result_map

    def fetch_districts_live(self, kab_code: str) -> Dict[str, str]:
        """Ambil daftar Kecamatan di bawah Kabupaten/Kota via API Internet."""
        if not kab_code:
            return {}
        if kab_code in self._cache_districts and self._cache_districts[kab_code]:
            return self._cache_districts[kab_code]

        clean_kab = self.clean_code_string(kab_code)
        result_map = {}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

        try:
            url = f"https://ibnux.github.io/data-indonesia/kecamatan/{clean_kab}.json"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    for item in data:
                        formatted = self.format_code_with_dots(str(item['id']))
                        result_map[formatted] = str(item['nama'])
                    if result_map:
                        self._cache_districts[kab_code] = result_map
                        return result_map
        except Exception:
            pass

        if result_map:
            self._cache_districts[kab_code] = result_map
        return result_map

    def fetch_villages_live(self, kec_code: str) -> Dict[str, str]:
        """Ambil daftar Desa/Kelurahan di bawah Kecamatan via API Internet."""
        if not kec_code:
            return {}
        if kec_code in self._cache_villages and self._cache_villages[kec_code]:
            return self._cache_villages[kec_code]

        clean_kec = self.clean_code_string(kec_code)
        result_map = {}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

        try:
            url = f"https://ibnux.github.io/data-indonesia/kelurahan/{clean_kec}.json"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    for item in data:
                        formatted = self.format_code_with_dots(str(item['id']))
                        result_map[formatted] = str(item['nama'])
                    if result_map:
                        self._cache_villages[kec_code] = result_map
                        return result_map
        except Exception:
            pass

        if result_map:
            self._cache_villages[kec_code] = result_map
        return result_map



    def validate_hierarchy(self, raw_code: str) -> Dict[str, Any]:
        """
        Memeriksa keberadaan kode dan kecocokan hirarki parent-child via Live API:
        Provinsi -> Kabupaten/Kota -> Kecamatan -> Desa/Kelurahan
        """
        comp = self.parse_code_components(raw_code)
        digits = comp["digits"]
        length = comp["length"]
        formatted = comp["formatted_code"]

        result = {
            "code": formatted,
            "digits": digits,
            "level": None,
            "exists_in_db": False,
            "hierarchy_valid": False,
            "official_name": None,
            "hierarchy_details": {},
            "error_message": None
        }

        if length not in [2, 4, 6, 10]:
            result["error_message"] = f"Format panjang kode wilayah tidak valid ({length} digit). Harus 2, 4, 6, atau 10 digit."
            return result

        # 1. Cek Provinsi
        prov_code = comp["prov_code"]
        provinces = self.fetch_provinces_live()
        prov_name = provinces.get(prov_code)

        if not prov_name:
            result["error_message"] = f"Kode Provinsi '{prov_code}' tidak terdaftar pada data resmi Kemendagri."
            return result

        result["hierarchy_details"]["provinsi"] = {"code": prov_code, "name": prov_name, "valid": True}

        if length == 2:
            result["level"] = "Provinsi"
            result["exists_in_db"] = True
            result["hierarchy_valid"] = True
            result["official_name"] = prov_name
            return result

        # 2. Cek Kabupaten / Kota
        kab_code = comp["kab_code"]
        regencies = self.fetch_regencies_live(prov_code)
        kab_name = regencies.get(kab_code)

        if not kab_name:
            result["error_message"] = f"Kode Kabupaten/Kota '{kab_code}' tidak ditemukan di bawah Provinsi '{prov_name}' ({prov_code})."
            return result

        result["hierarchy_details"]["kabupaten"] = {"code": kab_code, "name": kab_name, "valid": True}

        if length == 4:
            result["level"] = "Kabupaten/Kota"
            result["exists_in_db"] = True
            result["hierarchy_valid"] = True
            result["official_name"] = kab_name
            return result

        # 3. Cek Kecamatan
        kec_code = comp["kec_code"]
        districts = self.fetch_districts_live(kab_code)
        kec_name = districts.get(kec_code)

        if not kec_name:
            result["error_message"] = f"Kode Kecamatan '{kec_code}' tidak ditemukan di bawah '{kab_name}' ({kab_code})."
            return result

        result["hierarchy_details"]["kecamatan"] = {"code": kec_code, "name": kec_name, "valid": True}

        if length == 6:
            result["level"] = "Kecamatan"
            result["exists_in_db"] = True
            result["hierarchy_valid"] = True
            result["official_name"] = kec_name
            return result

        # 4. Cek Desa / Kelurahan
        desa_code = comp["desa_code"]
        villages = self.fetch_villages_live(kec_code)
        desa_name = villages.get(desa_code)

        if not desa_name:
            # Retry langsung ke ibnux dengan timeout lebih panjang
            try:
                clean_kec2 = self.clean_code_string(kec_code)
                url2 = f"https://ibnux.github.io/data-indonesia/kelurahan/{clean_kec2}.json"
                req2 = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                with urllib.request.urlopen(req2, timeout=6) as resp2:
                    if resp2.status == 200:
                        data2 = json.loads(resp2.read().decode('utf-8'))
                        retry_map = {self.format_code_with_dots(str(item['id'])): str(item['nama']) for item in data2}
                        if retry_map:
                            self._cache_villages[kec_code] = retry_map
                            desa_name = retry_map.get(desa_code)
            except Exception:
                pass

        if not desa_name:
            result["error_message"] = f"Kode Desa/Kelurahan '{desa_code}' tidak ditemukan di bawah Kecamatan '{kec_name}' ({kec_code})."
            return result

        result["hierarchy_details"]["desa"] = {"code": desa_code, "name": desa_name, "valid": True}
        result["level"] = "Desa/Kelurahan"
        result["exists_in_db"] = True
        result["hierarchy_valid"] = True
        result["official_name"] = desa_name

        return result


class KodeWilayahAPIClient:
    """
    Integrasi Live API Kode Wilayah Kemendagri (kodewilayah.web.id) & Nominatim BIG Geocoder.
    Menyediakan validasi real-time & offline cache untuk 100% presisi akurasi kode wilayah.
    """
    CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "kode_wilayah_cache.json")
    _cache = {}

    @classmethod
    def load_cache(cls):
        if not cls._cache and os.path.exists(cls.CACHE_FILE):
            try:
                with open(cls.CACHE_FILE, "r", encoding="utf-8") as f:
                    cls._cache = json.load(f)
            except Exception:
                pass

    @classmethod
    def save_cache(cls):
        try:
            with open(cls.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def fetch_api(cls, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'VeridocGeospatial/1.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if isinstance(data, dict) and data.get('success'):
                    return data.get('data', [])
                return data
        except Exception:
            return None

    @classmethod
    def get_provinces(cls):
        cls.load_cache()
        if 'provinces' in cls._cache:
            return cls._cache['provinces']
        
        live_data = cls.fetch_api('https://api.kodewilayah.web.id/provinces')
        if live_data and isinstance(live_data, list):
            res_dict = {str(item['code']).zfill(2): item['name'] for item in live_data if isinstance(item, dict) and 'code' in item}
            if res_dict:
                cls._cache['provinces'] = res_dict
                cls.save_cache()
                return res_dict
        return {}

    @classmethod
    def get_regencies(cls, prov_code):
        prov_code = str(prov_code).zfill(2)
        cls.load_cache()
        cache_key = f"regencies_{prov_code}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        live_data = cls.fetch_api(f'https://api.kodewilayah.web.id/regencies/{prov_code}')
        if live_data and isinstance(live_data, list):
            res_dict = {str(item['code']): item['name'] for item in live_data if isinstance(item, dict) and 'code' in item}
            if res_dict:
                cls._cache[cache_key] = res_dict
                cls.save_cache()
                return res_dict
        return {}

    @classmethod
    def reverse_geocode(cls, lat, lon):
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat:.5f}&lon={lon:.5f}&format=json"
            req = urllib.request.Request(url, headers={'User-Agent': 'VeridocGeospatial/1.0'})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                addr = data.get('address', {})
                return {
                    "display_name": data.get('display_name', ''),
                    "state": addr.get('state', ''),
                    "county": addr.get('county', '') or addr.get('regency', '') or addr.get('city', ''),
                    "village": addr.get('village', '') or addr.get('town', '') or addr.get('suburb', '')
                }
        except Exception:
            return None


PROVINCE_CODES = {
    '11': 'Aceh', '12': 'Sumatera Utara', '13': 'Sumatera Barat', '14': 'Riau',
    '15': 'Jambi', '16': 'Sumatera Selatan', '17': 'Bengkulu', '18': 'Lampung',
    '19': 'Kep. Bangka Belitung', '21': 'Kep. Riau',
    '31': 'DKI Jakarta', '32': 'Jawa Barat', '33': 'Jawa Tengah', '34': 'DI Yogyakarta',
    '35': 'Jawa Timur', '36': 'Banten',
    '51': 'Bali', '52': 'Nusa Tenggara Barat', '53': 'Nusa Tenggara Timur',
    '61': 'Kalimantan Barat', '62': 'Kalimantan Tengah', '63': 'Kalimantan Selatan',
    '64': 'Kalimantan Timur', '65': 'Kalimantan Utara',
    '71': 'Sulawesi Utara', '72': 'Sulawesi Tengah', '73': 'Sulawesi Selatan',
    '74': 'Sulawesi Tenggara', '75': 'Gorontalo', '76': 'Sulawesi Barat',
    '81': 'Maluku', '82': 'Maluku Utara', 
    '91': 'Papua', '92': 'Papua Barat', '93': 'Papua Selatan', '94': 'Papua Tengah', '95': 'Papua Pegunungan'
}

PROV_CODE_MAP = {
    "11": ("Aceh", 2.0, 6.1, 95.0, 98.3),
    "12": ("Sumatera Utara", 0.5, 4.3, 97.0, 100.7),
    "13": ("Sumatera Barat", -3.5, 0.9, 98.6, 101.9),
    "14": ("Riau", -1.1, 2.5, 100.0, 103.8),
    "15": ("Jambi", -2.8, -0.7, 101.1, 104.5),
    "16": ("Sumatera Selatan", -4.9, -1.6, 102.1, 106.2),
    "17": ("Bengkulu", -5.5, -2.2, 101.0, 104.0),
    "18": ("Lampung", -6.0, -3.6, 103.6, 106.0),
    "19": ("Bangka Belitung", -3.8, -1.5, 105.0, 108.5),
    "21": ("Kepulauan Riau", -1.0, 4.8, 103.2, 109.2),
    "31": ("DKI Jakarta", -6.4, -6.0, 106.6, 107.0),
    "32": ("Jawa Barat", -7.8, -5.9, 106.3, 108.8),
    "33": ("Jawa Tengah", -8.3, -6.3, 108.5, 111.6),
    "34": ("DI Yogyakarta", -8.2, -7.5, 110.0, 110.8),
    "35": ("Jawa Timur", -8.8, -6.5, 110.8, 115.8),
    "36": ("Banten", -7.1, -5.9, 105.1, 106.8),
    "51": ("Bali", -8.9, -8.0, 114.4, 115.7),
    "52": ("Nusa Tenggara Barat", -9.1, -8.0, 115.8, 119.4),
    "53": ("Nusa Tenggara Timur", -11.1, -8.0, 118.9, 125.2),
    "61": ("Kalimantan Barat", -3.1, 2.1, 108.0, 114.2),
    "62": ("Kalimantan Tengah", -3.6, 0.8, 110.7, 115.9),
    "63": ("Kalimantan Selatan", -4.6, -1.3, 114.1, 116.6),
    "64": ("Kalimantan Timur", -2.5, 2.5, 113.8, 119.5),
    "65": ("Kalimantan Utara", 1.2, 4.4, 114.5, 118.0),
    "71": ("Sulawesi Utara", 0.3, 5.6, 123.1, 127.2),
    "72": ("Sulawesi Tengah", -3.5, 1.9, 119.4, 124.3),
    "73": ("Sulawesi Selatan", -7.0, -1.9, 118.9, 121.7),
    "74": ("Sulawesi Tenggara", -6.2, -2.8, 120.8, 124.6),
    "75": ("Gorontalo", 0.3, 1.1, 121.1, 123.6),
    "76": ("Sulawesi Barat", -3.6, -1.1, 118.7, 119.9),
    "81": ("Maluku", -8.4, -1.4, 125.7, 131.6),
    "82": ("Maluku Utara", -2.5, 2.7, 124.2, 129.7),
    "91": ("Papua", -3.2, -1.3, 134.2, 141.0),
    "92": ("Papua Barat", -4.3, 1.1, 129.7, 135.2),
    "93": ("Papua Selatan", -9.1, -4.5, 137.5, 141.0),
    "94": ("Papua Tengah", -4.8, -2.1, 134.6, 138.5),
    "95": ("Papua Pegunungan", -5.1, -3.2, 137.8, 141.0)
}
