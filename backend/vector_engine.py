import os
import json
import math
import zipfile
import io
import struct
import xml.etree.ElementTree as ET
from pyproj import Transformer
from shapely.geometry import shape, Point, Polygon, MultiPolygon, LineString

# Province & Region Lookup Table for Indonesia Spatial Location Prediction ("Tebak Lokasi")
INDONESIA_REGIONS_SPATIAL_DB = [
    {"name": "Kabupaten Konawe Selatan", "prov": "Sulawesi Tenggara", "lat_range": (-4.6, -3.7), "lon_range": (121.5, 123.2), "code": "74.05"},
    {"name": "Kabupaten Sumenep", "prov": "Jawa Timur", "lat_range": (-7.4, -6.8), "lon_range": (113.3, 115.3), "code": "35.29"},
    {"name": "Kabupaten Bogor", "prov": "Jawa Barat", "lat_range": (-6.8, -6.3), "lon_range": (106.4, 107.1), "code": "32.01"},
    {"name": "Kota Bandung", "prov": "Jawa Barat", "lat_range": (-6.95, -6.85), "lon_range": (107.5, 107.75), "code": "32.73"},
    {"name": "Kota Surabaya", "prov": "Jawa Timur", "lat_range": (-7.35, -7.15), "lon_range": (112.6, 112.85), "code": "35.78"},
    {"name": "Kabupaten Rembang", "prov": "Jawa Tengah", "lat_range": (-7.0, -6.5), "lon_range": (111.1, 111.7), "code": "33.17"},
    {"name": "Kota Semarang", "prov": "Jawa Tengah", "lat_range": (-7.1, -6.9), "lon_range": (110.3, 110.5), "code": "33.74"},
    {"name": "Kabupaten Badung", "prov": "Bali", "lat_range": (-8.9, -8.4), "lon_range": (115.0, 115.3), "code": "51.03"},
    {"name": "Kota Denpasar", "prov": "Bali", "lat_range": (-8.75, -8.6), "lon_range": (115.15, 115.3), "code": "51.71"},
    {"name": "Kabupaten Sleman", "prov": "DI Yogyakarta", "lat_range": (-7.85, -7.5), "lon_range": (110.2, 110.55), "code": "34.04"},
    {"name": "Kota Medan", "prov": "Sumatera Utara", "lat_range": (3.4, 3.8), "lon_range": (98.5, 98.8), "code": "12.71"},
    {"name": "Kota Makassar", "prov": "Sulawesi Selatan", "lat_range": (-5.25, -5.0), "lon_range": (119.35, 119.55), "code": "73.71"},
    {"name": "Kota Balikpapan", "prov": "Kalimantan Timur", "lat_range": (-1.3, -1.0), "lon_range": (116.7, 117.0), "code": "64.71"},
    {"name": "Kota Samarinda", "prov": "Kalimantan Timur", "lat_range": (-0.6, -0.3), "lon_range": (117.0, 117.3), "code": "64.72"},
    {"name": "Kota Jayapura", "prov": "Papua", "lat_range": (-2.7, -2.4), "lon_range": (140.5, 140.9), "code": "91.71"}
]

PROVINCE_BOUNDS = [
    {"prov": "Aceh", "lat_range": (1.9, 6.1), "lon_range": (94.9, 98.3)},
    {"prov": "Sumatera Utara", "lat_range": (0.3, 4.3), "lon_range": (97.0, 100.7)},
    {"prov": "Sumatera Barat", "lat_range": (-3.5, 0.9), "lon_range": (98.5, 101.9)},
    {"prov": "Riau", "lat_range": (-1.1, 2.5), "lon_range": (100.0, 103.8)},
    {"prov": "Kepulauan Riau", "lat_range": (-0.8, 4.8), "lon_range": (103.1, 109.2)},
    {"prov": "Jambi", "lat_range": (-2.8, -0.7), "lon_range": (101.1, 104.9)},
    {"prov": "Sumatera Selatan", "lat_range": (-4.9, -1.6), "lon_range": (102.0, 106.2)},
    {"prov": "Bengkulu", "lat_range": (-5.5, -2.3), "lon_range": (101.0, 104.0)},
    {"prov": "Lampung", "lat_range": (-6.0, -3.7), "lon_range": (103.5, 106.0)},
    {"prov": "DKI Jakarta", "lat_range": (-6.4, -6.0), "lon_range": (106.6, 107.0)},
    {"prov": "Jawa Barat", "lat_range": (-7.8, -5.9), "lon_range": (106.3, 108.8)},
    {"prov": "Banten", "lat_range": (-7.1, -5.8), "lon_range": (105.1, 106.8)},
    {"prov": "Jawa Tengah", "lat_range": (-8.3, -6.3), "lon_range": (108.5, 111.6)},
    {"prov": "DI Yogyakarta", "lat_range": (-8.2, -7.5), "lon_range": (110.0, 110.8)},
    {"prov": "Jawa Timur", "lat_range": (-8.8, -6.7), "lon_range": (110.9, 115.8)},
    {"prov": "Bali", "lat_range": (-8.9, -8.0), "lon_range": (114.4, 115.7)},
    {"prov": "Nusa Tenggara Barat", "lat_range": (-9.1, -8.0), "lon_range": (115.8, 119.4)},
    {"prov": "Nusa Tenggara Timur", "lat_range": (-11.0, -8.0), "lon_range": (118.9, 125.2)},
    {"prov": "Kalimantan Barat", "lat_range": (-3.1, 2.1), "lon_range": (108.6, 114.2)},
    {"prov": "Kalimantan Tengah", "lat_range": (-3.6, 0.8), "lon_range": (110.7, 115.9)},
    {"prov": "Kalimantan Selatan", "lat_range": (-4.2, -1.3), "lon_range": (114.3, 116.6)},
    {"prov": "Kalimantan Timur", "lat_range": (-2.5, 2.6), "lon_range": (113.8, 119.1)},
    {"prov": "Kalimantan Utara", "lat_range": (1.1, 4.4), "lon_range": (114.5, 118.0)},
    {"prov": "Sulawesi Utara", "lat_range": (0.3, 5.6), "lon_range": (123.1, 127.2)},
    {"prov": "Gorontalo", "lat_range": (0.3, 1.1), "lon_range": (121.1, 123.6)},
    {"prov": "Sulawesi Tengah", "lat_range": (-3.4, 1.4), "lon_range": (119.4, 124.3)},
    {"prov": "Sulawesi Barat", "lat_range": (-3.6, -1.1), "lon_range": (118.7, 119.9)},
    {"prov": "Sulawesi Selatan", "lat_range": (-7.4, -1.9), "lon_range": (118.8, 121.7)},
    {"prov": "Sulawesi Tenggara", "lat_range": (-5.6, -2.7), "lon_range": (120.8, 124.2)},
    {"prov": "Maluku", "lat_range": (-8.4, -1.4), "lon_range": (125.7, 134.9)},
    {"prov": "Maluku Utara", "lat_range": (-2.5, 2.6), "lon_range": (124.2, 129.7)},
    {"prov": "Papua & Papua Barat", "lat_range": (-9.1, 0.7), "lon_range": (130.0, 141.1)}
]

def predict_location_from_coords(lat_dd, lon_dd):
    """Predict administrative location down to Village (Desa/Kelurahan), Kecamatan, Kabupaten, and Province."""
    utm_zone_num = int((lon_dd + 180) / 6) + 1
    utm_zone_let = 'S' if lat_dd < 0 else 'N'
    utm_zone_str = f"Zona {utm_zone_num}{utm_zone_let}"

    # 1. High-Resolution Live Reverse Geocoding (OSM Nominatim API zoom=14 with 2s timeout)
    try:
        import urllib.request
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat_dd}&lon={lon_dd}&zoom=14&addressdetails=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Veridoc-Village-Engine/3.5'})
        with urllib.request.urlopen(req, timeout=2.0) as response:
            data = json.loads(response.read().decode())
            addr = data.get('address', {})
            
            village = addr.get('village') or addr.get('suburb') or addr.get('neighbourhood') or addr.get('hamlet') or addr.get('quarter') or addr.get('residential')
            kecamatan = addr.get('town') or addr.get('district') or addr.get('subdistrict') or addr.get('city_district')
            kabupaten = addr.get('county') or addr.get('city') or addr.get('regency') or addr.get('municipality')
            provinsi = addr.get('state') or addr.get('province')
            country = addr.get('country')
            
            parts = []
            if village:
                v_name = village if village.lower().startswith(('desa', 'kelurahan', 'kel.', 'ds.')) else f"Desa/Kel. {village}"
                parts.append(v_name)
            if kecamatan:
                k_name = kecamatan if kecamatan.lower().startswith(('kecamatan', 'kec.')) else f"Kec. {kecamatan}"
                parts.append(k_name)
            if kabupaten:
                kb_name = kabupaten if any(k in kabupaten.lower() for k in ['kabupaten', 'kota', 'kab.', 'city', 'regency']) else f"Kabupaten {kabupaten}"
                parts.append(kb_name)
            if provinsi:
                parts.append(provinsi)
            if country and country != 'Indonesia':
                parts.append(country)
                
            if parts:
                return {
                    "predicted_location": ", ".join(parts),
                    "village": village or "-",
                    "kecamatan": kecamatan or "-",
                    "kabupaten": kabupaten or "-",
                    "provinsi": provinsi or "-",
                    "utm_zone": utm_zone_str,
                    "lat_dd": round(lat_dd, 6),
                    "lon_dd": round(lon_dd, 6)
                }
    except Exception:
        pass  # Fallback to offline spatial DB if offline

    # 2. Offline Spatial Bounding Box Matcher (Fallback)
    matched_reg = None
    for item in INDONESIA_REGIONS_SPATIAL_DB:
        if (item["lat_range"][0] <= lat_dd <= item["lat_range"][1]) and (item["lon_range"][0] <= lon_dd <= item["lon_range"][1]):
            matched_reg = f"{item['name']}, {item['prov']}"
            break

    matched_prov = None
    if not matched_reg:
        for p in PROVINCE_BOUNDS:
            if (p["lat_range"][0] <= lat_dd <= p["lat_range"][1]) and (p["lon_range"][0] <= lon_dd <= p["lon_range"][1]):
                matched_prov = p["prov"]
                break

    if matched_reg:
        predicted_name = matched_reg
    elif matched_prov:
        predicted_name = f"Wilayah {matched_prov}, Indonesia"
    elif (-11 <= lat_dd <= 6) and (95 <= lon_dd <= 141):
        predicted_name = f"Wilayah Indonesia ({utm_zone_str})"
    else:
        predicted_name = f"Koordinat Geospasial (Lat: {lat_dd:.4f}, Lon: {lon_dd:.4f})"

    return {
        "predicted_location": predicted_name,
        "village": "-",
        "kecamatan": "-",
        "kabupaten": "-",
        "provinsi": "-",
        "utm_zone": utm_zone_str,
        "lat_dd": round(lat_dd, 6),
        "lon_dd": round(lon_dd, 6)
    }



def calculate_approx_area_ha(geometry):
    """Calculate approximate area in Hectares from WGS84 or projected geometry."""
    try:
        if geometry.is_empty: return 0.0
        # Project to local UTM for accurate area measurement
        centroid = geometry.centroid
        lat_dd, lon_dd = centroid.y, centroid.x
        zone_num = int((lon_dd + 180) / 6) + 1
        epsg = 32700 + zone_num if lat_dd < 0 else 32600 + zone_num
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        
        def transform_coords(x, y, z=None):
            return transformer.transform(x, y)

        from shapely.ops import transform
        proj_geom = transform(transform_coords, geometry)
        area_m2 = proj_geom.area
        return round(area_m2 / 10000.0, 2)
    except Exception:
        return 0.0

def parse_geojson_file(content_bytes):
    """Parse GeoJSON file bytes and extract spatial predictions."""
    try:
        data = json.loads(content_bytes.decode('utf-8'))
        features = data.get('features', [])
        if not features and data.get('type') == 'Feature':
            features = [data]
            
        geoms = []
        for f in features:
            if f.get('geometry'):
                try:
                    geoms.append(shape(f['geometry']))
                except Exception:
                    pass

        if not geoms:
            raise ValueError("Tidak ditemukan geometri valid dalam file GeoJSON.")

        from shapely.geometry import GeometryCollection
        gc = GeometryCollection(geoms)
        bounds = gc.bounds  # (minx, miny, maxx, maxy)
        center_lon = (bounds[0] + bounds[2]) / 2.0
        center_lat = (bounds[1] + bounds[3]) / 2.0
        
        loc_info = predict_location_from_coords(center_lat, center_lon)
        area_ha = calculate_approx_area_ha(gc)
        
        geom_type = geoms[0].geom_type if geoms else "Unknown"

        return {
            "status": "success",
            "file_type": "GeoJSON (.geojson)",
            "feature_count": len(geoms),
            "geometry_type": geom_type,
            "predicted_location": loc_info["predicted_location"],
            "utm_zone": loc_info["utm_zone"],
            "center_lat": center_lat,
            "center_lon": center_lon,
            "bbox": list(bounds),
            "area_ha": area_ha,
            "geojson": data
        }
    except Exception as e:
        raise ValueError(f"Gagal membaca file GeoJSON: {str(e)}")

def parse_kml_file(content_bytes):
    """Parse KML file bytes and extract spatial predictions."""
    try:
        root = ET.fromstring(content_bytes.decode('utf-8', errors='replace'))
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        coords_list = []
        for coord_elem in root.findall('.//kml:coordinates', ns) or root.findall('.//coordinates'):
            txt = coord_elem.text or ''
            for pt_str in txt.strip().split():
                parts = pt_str.split(',')
                if len(parts) >= 2:
                    try:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        coords_list.append((lon, lat))
                    except ValueError:
                        pass

        if not coords_list:
            raise ValueError("Tidak ditemukan koordinat valid dalam file KML.")

        lons = [c[0] for c in coords_list]
        lats = [c[1] for c in coords_list]
        
        bounds = [min(lons), min(lats), max(lons), max(lats)]
        center_lon = (bounds[0] + bounds[2]) / 2.0
        center_lat = (bounds[1] + bounds[3]) / 2.0
        
        loc_info = predict_location_from_coords(center_lat, center_lon)

        # Build simple GeoJSON for visualization
        geojson_features = []
        for c in coords_list:
            geojson_features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [c[0], c[1]]},
                "properties": {"name": "KML Vector Point"}
            })

        return {
            "status": "success",
            "file_type": "KML / Google Earth (.kml)",
            "feature_count": len(coords_list),
            "geometry_type": "KML Coordinates",
            "predicted_location": loc_info["predicted_location"],
            "utm_zone": loc_info["utm_zone"],
            "center_lat": center_lat,
            "center_lon": center_lon,
            "bbox": bounds,
            "area_ha": 0.0,
            "geojson": {"type": "FeatureCollection", "features": geojson_features}
        }
    except Exception as e:
        raise ValueError(f"Gagal membaca file KML: {str(e)}")





def validate_polygon_topology(coords_list):
    """
    Modul 1: Pengecekan Topologi Batas (Shapely)
    Mengonversi daftar koordinat TK (lon, lat) menjadi objek Polygon Shapely.
    Melakukan 2 hal:
    1. is_valid check (Self-intersection)
    2. Shoelace Area Calculation
    """
    if len(coords_list) < 3:
        return {"is_valid": False, "error_msg": "Minimal butuh 3 titik untuk membuat poligon (batas wilayah).", "area_sqm": 0.0}
    
    try:
        poly = Polygon(coords_list)
        is_valid = poly.is_valid
        error_msg = ""
        if not is_valid:
            from shapely.validation import explain_validity
            error_msg = explain_validity(poly)
            
        centroid = poly.centroid
        lat_dd, lon_dd = centroid.y, centroid.x
        zone_num = int((lon_dd + 180) / 6) + 1
        epsg = 32700 + zone_num if lat_dd < 0 else 32600 + zone_num
        
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        projected_coords = [transformer.transform(x, y) for x, y in coords_list]
        
        def shoelace_area(pts):
            n = len(pts)
            area = 0.0
            for i in range(n):
                j = (i + 1) % n
                area += pts[i][0] * pts[j][1]
                area -= pts[j][0] * pts[i][1]
            return abs(area) / 2.0
            
        area_sqm = shoelace_area(projected_coords)
        
        return {
            "is_valid": is_valid,
            "error_msg": error_msg,
            "area_sqm": round(area_sqm, 2)
        }
        
    except Exception as e:
        return {"is_valid": False, "error_msg": f"Gagal memproses topologi: {str(e)}", "area_sqm": 0.0}

def inspect_vector_file(file_bytes, filename):
    """Main Entry Point for Vector Inspection & Location Prediction ('Tebak Lokasi')."""
    fn_lower = filename.lower()
    if fn_lower.endswith('.geojson') or fn_lower.endswith('.json'):
        return parse_geojson_file(file_bytes)
    elif fn_lower.endswith('.kml'):
        return parse_kml_file(file_bytes)
    elif fn_lower.endswith('.kmz'):
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            kml_entry = next((f for f in z.namelist() if f.lower().endswith('.kml')), None)
            if not kml_entry:
                raise ValueError("File .kmz tidak berisi file .kml valid.")
            return parse_kml_file(z.read(kml_entry))
    else:
        raise ValueError(f"Format file '{filename}' tidak didukung. Harap unggah file .geojson, .kml, atau .kmz.")
