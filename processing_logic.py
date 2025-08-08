# processing_logic.py
# -*- coding: utf-8 -*-

import sys
import os
import re
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import transform, unary_union
from pyproj import Transformer
import simplekml
from xml.etree import ElementTree as ET
from math import cos, radians, sqrt
import glob
import math
import zipfile

# --- Fonctions utilitaires ---
def parse_buffer_size(buffer_size_str):
    pattern = r"^\s*(\d+(\.\d+)?)\s*(m|ft|km|nm)\s*$"
    match = re.match(pattern, buffer_size_str.lower())
    if not match: raise ValueError(f"Format invalide: '{buffer_size_str}'.")
    value_str, _, unit = match.groups()[:3]
    value = float(value_str)
    conv = {"m": 0.001, "ft": 0.0003048, "km": 1, "nm": 1.852}
    return value * conv[unit]

def compute_mean_latitude(polygon_coords_list):
    all_latitudes = [lat for poly in polygon_coords_list for _, lat in poly]
    if not all_latitudes: return 0
    return sum(all_latitudes) / len(all_latitudes)

def calculate_color(distance_km, max_distance):
    norm = 0.5 if max_distance == 0 else distance_km / max_distance
    r = int(255 * (1 - norm)); g = 0; b = int(255 * norm)
    # Retourne la couleur au format KML (ABGR)
    return f"ff{b:02x}{g:02x}{r:02x}" # Note: alpha 'ff' pour opaque, on le modifiera plus tard pour la transparence

# --- Fonctions de lecture et de traitement ---
def read_kml_polygons(file_path):
    kml_content_str = None
    try:
        if file_path.lower().endswith('.kmz'):
            if not zipfile.is_zipfile(file_path): print(f"Erreur : {file_path} n'est pas un KMZ valide."); return []
            with zipfile.ZipFile(file_path, 'r') as kmz:
                kml_filename = next((f for f in kmz.namelist() if f.lower().endswith('.kml')), None)
                if kml_filename:
                    try: kml_content_str = kmz.read(kml_filename).decode('utf-8')
                    except Exception: kml_content_str = kmz.read(kml_filename).decode('latin-1')
                else: print(f"Erreur : Aucun .kml dans {file_path}"); return []
        elif file_path.lower().endswith('.kml'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f: kml_content_str = f.read()
            except UnicodeDecodeError:
                 with open(file_path, 'r', encoding='latin-1') as f: kml_content_str = f.read()
        else: print(f"Erreur : Type fichier non supporté : {file_path}."); return []
    except Exception as e: print(f"Erreur lecture {file_path}: {e}"); return []

    if not kml_content_str: return []
    try:
        root = ET.fromstring(kml_content_str)
        namespace_uri = root.tag.split('}')[0][1:] if '}' in root.tag else 'http://www.opengis.net/kml/2.2'
        namespaces = {'kml': namespace_uri}
    except Exception as e: print(f"Erreur parsing XML {file_path}: {e}"); return []

    polygons_found = []
    search_paths = [
        './/kml:Placemark/kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates',
        './/kml:Placemark/kml:MultiGeometry/kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates'
    ]
    processed_coords_texts = set()
    for path in search_paths:
        for coordinates_tag in root.findall(path, namespaces):
            if coordinates_tag.text:
                coords_text = coordinates_tag.text.strip()
                if coords_text in processed_coords_texts: continue
                processed_coords_texts.add(coords_text)
                try:
                    polygon_points = [(float(c.split(',')[0]), float(c.split(',')[1])) for c in coords_text.split() if len(c.split(',')) >= 2]
                    if len(polygon_points) >= 3: polygons_found.append(Polygon(polygon_points))
                except (ValueError, IndexError, TypeError): continue
    return polygons_found

def generate_precise_3d_buffers_for_polygons(shapely_polygons, distance_km, num_altitudes=10, max_altitude_m=float('inf'), merge_buffers=True):
    if not shapely_polygons: return []
    valid_polygons = [p for p in shapely_polygons if p.is_valid and not p.is_empty]
    if not valid_polygons: return []

    all_coords = [list(p.exterior.coords) for p in valid_polygons]
    mean_latitude = compute_mean_latitude(all_coords)
    correction_factor = 1 / cos(radians(mean_latitude)) if cos(radians(mean_latitude)) != 0 else 1
    
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    reverse_transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    
    buffer_distance_m = distance_km * correction_factor * 1000
    if buffer_distance_m < 0: buffer_distance_m = 0
    effective_max_altitude_for_linspace = min(buffer_distance_m, max_altitude_m)

    altitudes = np.linspace(0, effective_max_altitude_for_linspace, num_altitudes) if num_altitudes > 1 else [effective_max_altitude_for_linspace]

    if merge_buffers:
        all_rings_combined = []
        projected_polygons = [transform(transformer.transform, p) for p in valid_polygons]
        for alt in altitudes:
            horizontal_distance_m = sqrt(max(0, buffer_distance_m**2 - alt**2))
            buffers_at_this_alt_proj = [p.buffer(horizontal_distance_m, resolution=16) for p in projected_polygons]
            valid_buffers = [b for b in buffers_at_this_alt_proj if b.is_valid and not b.is_empty]
            if not valid_buffers: continue
            
            try: merged_geometry_proj = unary_union(valid_buffers)
            except Exception: continue

            geometries_to_transform = []
            if isinstance(merged_geometry_proj, Polygon): geometries_to_transform.append(merged_geometry_proj)
            elif isinstance(merged_geometry_proj, MultiPolygon): geometries_to_transform.extend(list(merged_geometry_proj.geoms))
            
            for geom_proj in geometries_to_transform:
                try:
                    geom_geo = transform(reverse_transformer.transform, geom_proj)
                    if geom_geo.geom_type == 'Polygon':
                        all_rings_combined.append([(lon, lat, alt) for lon, lat in geom_geo.exterior.coords])
                except Exception: continue
        return all_rings_combined
    else: # No merge
        results_by_poly = []
        for poly in valid_polygons:
            rings_for_this_poly = []
            try:
                proj_poly = transform(transformer.transform, poly)
                for alt in altitudes:
                    horizontal_distance_m = sqrt(max(0, buffer_distance_m**2 - alt**2))
                    buffered = proj_poly.buffer(horizontal_distance_m, resolution=16)
                    geoms_to_process = []
                    if isinstance(buffered, Polygon): geoms_to_process.append(buffered)
                    elif isinstance(buffered, MultiPolygon): geoms_to_process.extend(list(buffered.geoms))

                    for geom_part in geoms_to_process:
                         if geom_part.is_valid and not geom_part.is_empty:
                             geom_geo = transform(reverse_transformer.transform, geom_part)
                             rings_for_this_poly.append([(lon, lat, alt) for lon, lat in geom_geo.exterior.coords])
            except Exception: continue
            results_by_poly.append((poly, rings_for_this_poly))
        return results_by_poly

# --- Fonction d'écriture KML MODIFIÉE pour générer des polygones pleins ---
def write_kml_with_folders(source_polygons, buffers_by_distance, output_file, merge_buffers=True):
    kml = simplekml.Kml()
    doc_name = os.path.splitext(os.path.basename(output_file))[0].replace('_zones_tampons_3d', '')
    doc = kml.newdocument(name=doc_name)

    source_folder = doc.newfolder(name="Polygones Sources")
    for idx, poly in enumerate(p for p in source_polygons if p.is_valid and not p.is_empty):
        try:
            kml_poly = source_folder.newpolygon(name=f"Source Polygon {idx+1}")
            kml_poly.outerboundaryis = list(poly.exterior.coords)
            kml_poly.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.grey)
            kml_poly.style.linestyle.width = 1
        except Exception as e: print(f"Erreur écriture polygone source {idx+1}: {e}")

    for user_input, (data, color) in buffers_by_distance.items():
        buffer_folder = doc.newfolder(name=f"Zone Tampon {user_input}")

        def create_polygon_for_ring(parent, ring, name, color):
            poly = parent.newpolygon(name=name)
            poly.outerboundaryis = ring
            poly.altitudemode = simplekml.AltitudeMode.relativetoground
            poly.style.polystyle.color = simplekml.Color.changealphaint(120, color) # 120/255 = ~47% transp