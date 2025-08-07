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
import argparse

# --- Fonctions utilitaires (inchangées) ---
def parse_buffer_size(buffer_size_str):
    """Analyse une taille de tampon et la convertit en kilomètres."""
    pattern = r"^\s*(\d+(\.\d+)?)\s*(m|ft|km|nm)\s*$"
    match = re.match(pattern, buffer_size_str.lower())
    if not match: raise ValueError(f"Format invalide: '{buffer_size_str}'.")
    value_str, _, unit = match.groups()[:3]
    value = float(value_str)
    conv = {"m": 0.001, "ft": 0.0003048, "km": 1, "nm": 1.852}
    return value * conv[unit]

def compute_mean_latitude(polygon_coords_list):
    """Calcule la latitude moyenne."""
    all_latitudes = [lat for poly in polygon_coords_list for _, lat in poly]
    if not all_latitudes: return 0
    return sum(all_latitudes) / len(all_latitudes)

def calculate_color(distance_km, max_distance):
    """Calcule une couleur KML."""
    norm = 0.5 if max_distance == 0 else distance_km / max_distance
    r = int(255 * (1 - norm)); g = 0; b = int(255 * norm)
    return f"CC{b:02X}{g:02X}{r:02X}" # ABGR format

# --- Fonction de lecture KML/KMZ (inchangée) ---
def read_kml_polygons(file_path):
    """
    Lit un fichier KML ou KMZ et extrait les coordonnées de TOUS les polygones
    trouvés dans des Placemarks (y compris Folders, MultiGeometry).
    (Code inchangé par rapport à la version précédente)
    """
    kml_content_str = None
    try: # Lecture KML/KMZ
        if file_path.lower().endswith('.kmz'):
            if not zipfile.is_zipfile(file_path): print(f"Erreur : {file_path} n'est pas un KMZ valide."); return []
            with zipfile.ZipFile(file_path, 'r') as kmz:
                kml_filename = next((f for f in kmz.namelist() if f.lower() == 'doc.kml'), None) \
                            or next((f for f in kmz.namelist() if f.lower().endswith('.kml')), None)
                if kml_filename:
                    try: kml_content_str = kmz.read(kml_filename).decode('utf-8')
                    except Exception:
                         try: kml_content_str = kmz.read(kml_filename).decode('latin-1')
                         except Exception as e: print(f"Echec décodage {kml_filename} dans {file_path}: {e}"); return []
                else: print(f"Erreur : Aucun .kml dans {file_path}"); return []
        elif file_path.lower().endswith('.kml'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f: kml_content_str = f.read()
            except UnicodeDecodeError:
                 with open(file_path, 'r', encoding='latin-1') as f: kml_content_str = f.read()
        else: print(f"Erreur : Type fichier non supporté : {file_path}."); return []
    except Exception as e: print(f"Erreur lecture {file_path}: {e}"); return []

    if not kml_content_str: return []
    try: # Parsing XML
        root = ET.fromstring(kml_content_str)
        namespace_uri = root.tag.split('}')[0][1:] if '}' in root.tag else 'http://www.opengis.net/kml/2.2'
        namespaces = {'kml': namespace_uri}
    except Exception as e: print(f"Erreur parsing XML {file_path}: {e}"); return []

    # Recherche polygones
    polygons_found = []
    all_coordinates_tags = []
    search_path_direct = './/kml:Placemark/kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates'
    search_path_multi = './/kml:Placemark/kml:MultiGeometry/kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates'
    all_coordinates_tags.extend(root.findall(search_path_direct, namespaces))
    all_coordinates_tags.extend(root.findall(search_path_multi, namespaces))
    processed_coords_texts = set()
    for coordinates_tag in all_coordinates_tags:
        if coordinates_tag.text:
            coords_text = coordinates_tag.text.strip()
            if coords_text in processed_coords_texts: continue
            processed_coords_texts.add(coords_text)
            try:
                polygon_points = [(float(c.split(',')[0]), float(c.split(',')[1])) for c in coords_text.split() if len(c.split(',')) >= 2]
                if len(polygon_points) >= 3: polygons_found.append(Polygon(polygon_points))
            except (ValueError, IndexError, TypeError): continue
    return polygons_found


# --- Fonction de génération de tampons MODIFIÉE : Structure de retour différente si pas de fusion ---
def generate_precise_3d_buffers_for_polygons(shapely_polygons, distance_km, num_altitudes=10, max_altitude_m=float('inf'), merge_buffers=True):
    """
    Génère des tampons 3D.
    Si merge_buffers=True, retourne une liste plate d'anneaux fusionnés.
    Si merge_buffers=False, retourne une liste de tuples: [(poly_source1, [anneaux1]), (poly_source2, [anneaux2]), ...].
    """
    if not shapely_polygons: return []

    all_coords = []
    valid_polygons = [p for p in shapely_polygons if p.is_valid and not p.is_empty]
    if not valid_polygons: return []
    for p in valid_polygons: all_coords.append(list(p.exterior.coords))

    mean_latitude = compute_mean_latitude(all_coords)
    correction_factor = 1 / cos(radians(mean_latitude)) if cos(radians(mean_latitude)) != 0 else 1
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    reverse_transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    buffer_distance_m = distance_km * correction_factor * 1000
    if buffer_distance_m < 0: buffer_distance_m = 0
    effective_max_altitude_for_linspace = min(buffer_distance_m, max_altitude_m)

    if num_altitudes <= 1:
        altitudes = [effective_max_altitude_for_linspace] if effective_max_altitude_for_linspace >= 0 else []
    else:
        altitudes = np.linspace(0, effective_max_altitude_for_linspace, num_altitudes)

    # --- La logique diffère ici ---
    if merge_buffers:
        # --- CAS 1: FUSION -> Retourne List[ring] ---
        all_rings_combined = []
        projected_polygons = [transform(transformer.transform, p) for p in valid_polygons]
        for alt in altitudes:
            # ... (logique de buffering, union, transformation comme avant) ...
            horizontal_distance_m = sqrt(max(0, buffer_distance_m**2 - alt**2))
            buffers_at_this_alt_proj = []
            for proj_poly in projected_polygons:
                try:
                    buffered = proj_poly.buffer(horizontal_distance_m, resolution=16)
                    if buffered.is_valid and not buffered.is_empty: buffers_at_this_alt_proj.append(buffered)
                except Exception: continue
            if not buffers_at_this_alt_proj: continue
            try: merged_geometry_proj = unary_union(buffers_at_this_alt_proj)
            except Exception as e: print(f"Erreur unary_union (alt={alt:.1f}m): {e}"); continue

            geometries_to_transform = []
            if merged_geometry_proj.is_empty: continue
            elif isinstance(merged_geometry_proj, Polygon): geometries_to_transform.append(merged_geometry_proj)
            elif isinstance(merged_geometry_proj, MultiPolygon): geometries_to_transform.extend(list(merged_geometry_proj.geoms))

            for geom_proj in geometries_to_transform:
                if not geom_proj.is_valid or geom_proj.is_empty: continue
                try:
                    geom_geo = transform(reverse_transformer.transform, geom_proj)
                    if geom_geo.geom_type == 'Polygon':
                        ring_coords = [(lon, lat, alt) for lon, lat in geom_geo.exterior.coords]
                        if ring_coords: all_rings_combined.append(ring_coords)
                except Exception as e: print(f"Erreur transfo/ajout alt (alt={alt:.1f}m): {e}"); continue
        return all_rings_combined # Retourne la liste plate

    else:
        # --- CAS 2: PAS DE FUSION -> Retourne List[Tuple(poly, List[ring])] ---
        results_by_poly = []
        for poly_idx, poly in enumerate(valid_polygons):
            rings_for_this_poly = []
            try:
                proj_poly = transform(transformer.transform, poly)
                for alt in altitudes:
                    horizontal_distance_m = sqrt(max(0, buffer_distance_m**2 - alt**2))
                    try:
                        buffered = proj_poly.buffer(horizontal_distance_m, resolution=16)
                        # Gérer Polygon et MultiPolygon issus du buffer d'un seul polygone
                        geometries_to_process = []
                        if buffered.is_valid and not buffered.is_empty:
                            if isinstance(buffered, Polygon): geometries_to_process.append(buffered)
                            elif isinstance(buffered, MultiPolygon): geometries_to_process.extend(list(buffered.geoms))

                        for geom_part in geometries_to_process:
                             if geom_part.is_valid and not geom_part.is_empty and geom_part.geom_type == 'Polygon':
                                 geom_geo = transform(reverse_transformer.transform, geom_part)
                                 ring_coords = [(lon, lat, alt) for lon, lat in geom_geo.exterior.coords]
                                 if ring_coords: rings_for_this_poly.append(ring_coords)
                    except Exception as e_buffer: continue # Ignorer erreur pour cette altitude
            except Exception as e_proj: continue # Ignorer erreur pour ce polygone source

            # Ajouter le résultat pour ce polygone (même si rings_for_this_poly est vide)
            # Passer le polygone source original (non projeté) pour référence potentielle
            results_by_poly.append((poly, rings_for_this_poly))
        return results_by_poly # Retourne la liste de tuples

# --- Fonction d'écriture KML MODIFIÉE pour gérer les deux structures de données ---
def write_kml_with_folders(source_polygons, buffers_by_distance, output_file, merge_buffers=True):
    """
    Écrit un fichier KML.
    Si merge_buffers=True, buffers_by_distance contient {dist_str: (List[ring], color)}.
    Si merge_buffers=False, buffers_by_distance contient {dist_str: (List[Tuple(poly, List[ring])], color)}.
    """
    # --- Ajout du paramètre merge_buffers ---
    kml = simplekml.Kml()
    doc_name = os.path.splitext(os.path.basename(output_file))[0].replace('_zones_tampons_3d', '')
    doc = kml.newdocument(name=doc_name)

    # Ajouter les polygones sources (inchangé)
    source_folder = doc.newfolder(name="Polygones Sources")
    valid_source_polygons = [p for p in source_polygons if p.is_valid and not p.is_empty]
    for idx, poly in enumerate(valid_source_polygons):
        try:
            kml_poly = source_folder.newpolygon(name=f"Source Polygon {idx+1}")
            coords = list(poly.exterior.coords); coords.append(coords[0]) # Assurer fermeture
            kml_poly.outerboundaryis = coords
            kml_poly.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.grey)
            kml_poly.style.linestyle.width = 1
            kml_poly.style.linestyle.color = simplekml.Color.black
        except Exception as e: print(f"Erreur écriture polygone source {idx+1}: {e}")

    # Ajouter les zones tampons, la structure dépend de merge_buffers
    for user_input, data in buffers_by_distance.items():
        buffer_folder = doc.newfolder(name=f"Zone Tampon {user_input}") # Dossier principal par taille

        if merge_buffers:
            # --- CAS 1: FUSION (data = (List[ring], color)) ---
            rings, color = data
            if not rings: continue

            rings_by_alt = {} # Grouper par altitude
            for ring in rings:
                 if ring and len(ring) > 0 and len(ring[0]) >= 3:
                     alt = ring[0][2]
                     if alt not in rings_by_alt: rings_by_alt[alt] = []
                     rings_by_alt[alt].append(ring)

            sorted_alts = sorted(rings_by_alt.keys())
            for alt in sorted_alts: # Écrire les anneaux fusionnés par altitude
                 alt_folder = buffer_folder.newfolder(name = f"Altitude {alt:.1f}m")
                 for ring_idx, ring in enumerate(rings_by_alt[alt]):
                     linestring = alt_folder.newlinestring(name=f"Contour Fusionné {ring_idx+1}")
                     linestring.coords = ring
                     linestring.style.linestyle.color = color
                     linestring.style.linestyle.width = 2
                     linestring.altitudemode = simplekml.AltitudeMode.relativetoground
        else:
            # --- CAS 2: PAS DE FUSION (data = (List[Tuple(poly, List[ring])], color)) ---
            results_by_poly, color = data
            if not results_by_poly: continue

            # Créer un sous-dossier pour chaque polygone source
            for poly_idx, (source_poly, rings_for_this_poly) in enumerate(results_by_poly):
                 if not rings_for_this_poly: continue # Ne pas créer de dossier si pas d'anneaux

                 # Utiliser un identifiant plus stable si possible, sinon l'index
                 poly_folder_name = f"Source Polygon {poly_idx+1}"
                 poly_folder = buffer_folder.newfolder(name=poly_folder_name)

                 # Grouper les anneaux de CE polygone par altitude
                 rings_by_alt = {}
                 for ring in rings_for_this_poly:
                      if ring and len(ring) > 0 and len(ring[0]) >= 3:
                          alt = ring[0][2]
                          if alt not in rings_by_alt: rings_by_alt[alt] = []
                          rings_by_alt[alt].append(ring)

                 sorted_alts = sorted(rings_by_alt.keys())
                 for alt in sorted_alts: # Écrire les anneaux de ce polygone par altitude
                      alt_folder = poly_folder.newfolder(name = f"Altitude {alt:.1f}m")
                      for ring_idx, ring in enumerate(rings_by_alt[alt]):
                          linestring = alt_folder.newlinestring(name=f"Contour {ring_idx+1}")
                          linestring.coords = ring
                          linestring.style.linestyle.color = color
                          linestring.style.linestyle.width = 2
                          linestring.altitudemode = simplekml.AltitudeMode.relativetoground

    try: kml.save(output_file); print(f"Fichier KML sauvegardé : {output_file}")
    except Exception as e: print(f"Erreur sauvegarde KML {output_file}: {e}")

# --- Fonction principale MODIFIÉE pour passer merge_buffers à write_kml ---
def process_kml_file(input_kml_path, buffer_sizes_km, user_inputs, num_altitudes, max_altitude_m=float('inf'), merge_buffers=True):
    """
    Traite un seul fichier KML ou KMZ.
    """
    print(f"\nTraitement du fichier : {input_kml_path}")
    if max_altitude_m != float('inf'): print(f"  Altitude maximale appliquée : {max_altitude_m:.1f}m")
    print(f"  Fusion des zones tampons : {'Activée' if merge_buffers else 'Désactivée'}")
    print(f"  Nombre de niveaux d'altitude : {num_altitudes}")

    source_polygons = read_kml_polygons(input_kml_path)
    if not source_polygons: print(f"Fichier ignoré (aucun polygone lu) : {input_kml_path}"); return

    valid_source_polygons = [p for p in source_polygons if p.is_valid and not p.is_empty]
    if not valid_source_polygons: print(f"Fichier ignoré (aucun polygone valide) : {input_kml_path}"); return
    print(f"  -> Trouvé {len(valid_source_polygons)} polygone(s) valide(s).")

    output_folder = os.path.dirname(input_kml_path)
    base_name = os.path.splitext(os.path.basename(input_kml_path))[0]
    output_file = os.path.join(output_folder, f"{base_name}_zones_tampons_3d.kml")

    buffers_data = {} # Contiendra {user_input: (data_structure, color)}
    max_distance = max(buffer_sizes_km) if buffer_sizes_km else 1

    for radius_km, user_input in zip(buffer_sizes_km, user_inputs):
        print(f"  Génération du tampon : {user_input}...")
        # La structure de retour dépend de merge_buffers
        generated_data = generate_precise_3d_buffers_for_polygons(
            valid_source_polygons, radius_km,
            num_altitudes=num_altitudes,
            max_altitude_m=max_altitude_m,
            merge_buffers=merge_buffers
        )
        color = calculate_color(radius_km, max_distance)
        buffers_data[user_input] = (generated_data, color) # Stocker la structure retournée

        # Afficher le nombre d'anneaux ou de groupes polygone/anneaux
        count_desc = "anneau(x)" if merge_buffers else "groupe(s) polygone/anneaux"
        print(f"    -> {len(generated_data)} {count_desc} généré(s).")


    # --- Passer merge_buffers à write_kml_with_folders ---
    write_kml_with_folders(valid_source_polygons, buffers_data, output_file, merge_buffers)