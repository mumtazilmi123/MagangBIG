import re
import math
import html
from typing import Dict, Any, List, Tuple
from pyproj import Transformer
from .wilayah import PROV_CODE_MAP

def sanitize_dms_string(dms_str, dec_sep=',', dir_format='INDONESIA'):
    """
    Sanitasi format string DMS super toleran terhadap kesalahan baca OCR 
    (misal: derajat ° terbaca 0, o, * dan detik " terbaca '').
    """
    if not dms_str:
        return ""
    s = html.unescape(str(dms_str)).replace("&#x27;", "'").replace("&quot;", '"').replace("&amp;", "&").strip()

    # Pre-clean missing leading zero before dot/comma, e.g. " .66" -> " 0.66"
    s = re.sub(r'([\u00b0°\'\s0oO\*])\s*[\.,]([\d]+)', r'\1 0.\2', s)

    # Regex Super Toleran untuk Derajat (°, 0, o, O, *), Menit (', `), Detik (", '', ``)
    pattern = re.compile(
        r'(\d+)\s*[\u00b0°0oO\*\s]\s*(\d+)\s*[\'\u2032`\s]\s*(\d+(?:[\.,]\d+)?)\s*[\"\u2033\'`\s]{0,2}\s*([A-Za-z]+)?',
        re.IGNORECASE
    )
    m = pattern.search(s)
    if m:
        deg = int(m.group(1))
        minute = int(m.group(2))
        sec_raw = m.group(3).replace(',', '.')
        try:
            sec_val = float(sec_raw)
        except ValueError:
            sec_val = 0.0

        dir_raw = (m.group(4) or '').upper().strip()

        if dir_raw in ('S', 'SOUTH', 'LS', 'LC'):
            direction = 'LS' if dir_format == 'INDONESIA' else 'S'
        elif dir_raw in ('U', 'NORTH', 'LU', 'N'):
            direction = 'LU' if dir_format == 'INDONESIA' else 'N'
        elif dir_raw in ('E', 'EAST', 'BT', 'T'):
            direction = 'BT' if dir_format == 'INDONESIA' else 'E'
        elif dir_raw in ('W', 'WEST', 'BD', 'B'):
            direction = 'BD' if dir_format == 'INDONESIA' else 'W'
        else:
            direction = dir_raw

        sec_str = f"{sec_val:05.2f}"
        if dec_sep == ',':
            sec_str = sec_str.replace('.', ',')

        dir_part = f" {direction}" if direction else ""
        return f"{deg}° {minute:02d}' {sec_str}\"{dir_part}"

    s = re.sub(r'\b(E|EAST|T)\b', 'BT', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(W|WEST)\b', 'BD', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(S|SOUTH|LC)\b', 'LS', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(U|NORTH)\b', 'LU', s, flags=re.IGNORECASE)

    if dec_sep == ',':
        s = re.sub(r'(\d+)\.(\d+)', r'\1,\2', s)
    else:
        s = re.sub(r'(\d+),(\d+)', r'\1.\2', s)

    return s.strip()


def clean_zone_display(zone_val, lat_dd=None):
    """Merapikan & mengoreksi hasil OCR Zona UTM (misal '515' -> '51S')."""
    if zone_val is None:
        return '-'
    z_str = html.unescape(str(zone_val)).strip()
    m = re.match(r'^(\d{1,2})\s*([5S])$', z_str, re.IGNORECASE)
    if m:
        num = m.group(1)
        suffix = m.group(2).upper()
        if suffix == '5':
            suffix = 'S'
        return f"{num}{suffix}"
    return z_str if z_str else '-'


def detect_utm_crs_dynamically(lat: float, lon: float) -> Dict[str, Any]:
    """
    [DETEKSI ZONA & EPSG OTOMATIS]
    Menghitung secara matematis Zona UTM (1N-60N / 1S-60S), Kode EPSG resmi, 
    dan Sub-Zona TM-3 BPN berdasarkan nilai koordinat geografis (Lat/Long).
    """
    zone_num = math.floor((lon + 180) / 6) + 1
    hemisphere = 'S' if lat < 0 else 'N'
    utm_zone_str = f"{zone_num}{hemisphere}"

    epsg_code = (32700 + zone_num) if hemisphere == 'S' else (32600 + zone_num)
    crs_epsg_str = f"EPSG:{epsg_code}"

    central_meridian_utm = (zone_num * 6) - 183
    tm3_subzone = 1 if (lon < central_meridian_utm) else 2
    tm3_zone_str = f"TM-3 Zona {zone_num}.{tm3_subzone}"

    return {
        "zone_num": zone_num,
        "hemisphere": hemisphere,
        "utm_zone": utm_zone_str,
        "epsg_code": epsg_code,
        "crs": crs_epsg_str,
        "tm3_zone": tm3_zone_str,
        "central_meridian": central_meridian_utm
    }


def compute_spatial_extent(points: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Menghitung batasan wilayah (bounding box / extent) dan titik pusat (center)
    secara otomatis menyesuaikan sebaran koordinat dari dokumen SKVT.
    """
    if not points:
        return {
            "min_lat": 0.0, "max_lat": 0.0,
            "min_lon": 0.0, "max_lon": 0.0,
            "center_lat": 0.0, "center_lon": 0.0
        }

    lats = [p['lat_dd'] for p in points if isinstance(p, dict) and 'lat_dd' in p]
    lons = [p['lon_dd'] for p in points if isinstance(p, dict) and 'lon_dd' in p]

    if not lats or not lons:
        return {
            "min_lat": 0.0, "max_lat": 0.0,
            "min_lon": 0.0, "max_lon": 0.0,
            "center_lat": 0.0, "center_lon": 0.0
        }

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    return {
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
        "center_lat": (min_lat + max_lat) / 2.0,
        "center_lon": (min_lon + max_lon) / 2.0
    }


def infer_region_codes_for_tk(points_list=None, region_name="", full_text="", villages_list=None):
    """
    Dinamis Resolver Kode Wilayah Kemendagri (Provinsi & Kabupaten/Kota) Seluruh Indonesia.
    """
    if villages_list:
        for v in villages_list:
            v_str = str(v.get('code', '')) if isinstance(v, dict) else str(v)
            m = re.search(r'\b(\d{2})\.(\d{2})\.(\d{2})\.(\d{4})\b', v_str)
            if m:
                return m.group(1), m.group(2)

    if full_text:
        m = re.search(r'\b(\d{2})\.(\d{2})\.(\d{2})\.(\d{4})\b', full_text)
        if m:
            return m.group(1), m.group(2)

    prov_code = "00"
    kab_code = "00"

    if points_list:
        extent = compute_spatial_extent(points_list)
        avg_lat = extent["center_lat"]
        avg_lon = extent["center_lon"]
        if avg_lat != 0.0 and avg_lon != 0.0:
            for pcode, (pname, min_lat, max_lat, min_lon, max_lon) in PROV_CODE_MAP.items():
                if min_lat <= avg_lat <= max_lat and min_lon <= avg_lon <= max_lon:
                    prov_code = pcode
                    break

    return prov_code, kab_code


def format_tk_point_codes(points_list, region_name="", villages_list=None):
    """
    Format ID Titik Batas Koordinat Sesuai Standar Resmi BIG & Kemendagri:
    Pola Susunan: TK [XX.YY].[ZZ.AAAA]-[ZZ.BBBB]-[CCC]
    """
    if not points_list:
        return []

    prov_c, kab_c = infer_region_codes_for_tk(points_list, region_name, "", villages_list)
    xx_yy = f"{prov_c}.{kab_c}"

    zz_aaaa = "19.2006"
    zz_bbbb = "19.2010"

    if villages_list and len(villages_list) >= 2:
        v1_code = str(villages_list[0].get('code', '')) if isinstance(villages_list[0], dict) else str(villages_list[0])
        v2_code = str(villages_list[1].get('code', '')) if isinstance(villages_list[1], dict) else str(villages_list[1])
        m1 = re.search(r'\d{2}\.\d{2}\.(\d{2}\.\d{4})', v1_code)
        m2 = re.search(r'\d{2}\.\d{2}\.(\d{2}\.\d{4})', v2_code)
        if m1: zz_aaaa = m1.group(1)
        if m2: zz_bbbb = m2.group(1)
    elif villages_list and len(villages_list) == 1:
        v1_code = str(villages_list[0].get('code', '')) if isinstance(villages_list[0], dict) else str(villages_list[0])
        m1 = re.search(r'\d{2}\.\d{2}\.(\d{2}\.\d{4})', v1_code)
        if m1:
            zz_aaaa = m1.group(1)
            zz_bbbb = m1.group(1)

    base_prefix = None
    for p in points_list:
        if not isinstance(p, dict):
            continue
        c = str(p.get('code', '')).strip()
        m = re.search(r'\b(?:TK|TKB|PAB)?\s*[\.\s]*(\d{2}\.\d{2})\.(\d{2}\.\d{4})\-(\d{2}\.\d{4})\b', c, re.IGNORECASE)
        if m:
            base_prefix = f"TK {m.group(1)}.{m.group(2)}-{m.group(3)}"
            break

    if not base_prefix:
        base_prefix = f"TK {xx_yy}.{zz_aaaa}-{zz_bbbb}"

    cleaned_points = []
    used_codes = set()

    for i, p in enumerate(points_list):
        if not isinstance(p, dict):
            continue
        raw_c = str(p.get('code', '')).strip()

        m_full = re.search(r'\b(?:TK|TKB|PAB)?\s*[\.\s]*(\d{2}\.\d{2}\.\d{2}\.\d{4}\-\d{2}\.\d{4})\-(\d{1,4})\b', raw_c, re.IGNORECASE)
        if m_full:
            seq_num = int(m_full.group(2))
            code_candidate = f"TK {m_full.group(1)}-{seq_num:03d}"
            if code_candidate not in used_codes:
                code_disp = code_candidate
            else:
                code_disp = f"TK {m_full.group(1)}-{i+1:03d}"
        else:
            code_disp = f"{base_prefix}-{i+1:03d}"

        used_codes.add(code_disp)
        p_copy = dict(p)
        p_copy['code_disp'] = code_disp
        cleaned_points.append(p_copy)

    return cleaned_points
