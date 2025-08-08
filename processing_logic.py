# --- Fonction d'écriture KML MODIFIÉE pour générer des polygones ---
def write_kml_with_folders(source_polygons, buffers_by_distance, output_file, merge_buffers=True):
    """
    Écrit un fichier KML avec des ZONES POLYGONALES pleines.
    Si merge_buffers=True, buffers_by_distance contient {dist_str: (List[ring], color)}.
    Si merge_buffers=False, buffers_by_distance contient {dist_str: (List[Tuple(poly, List[ring])], color)}.
    """
    kml = simplekml.Kml()
    doc_name = os.path.splitext(os.path.basename(output_file))[0].replace('_zones_tampons_3d', '')
    doc = kml.newdocument(name=doc_name)

    # Ajouter les polygones sources (inchangé)
    source_folder = doc.newfolder(name="Polygones Sources")
    valid_source_polygons = [p for p in source_polygons if p.is_valid and not p.is_empty]
    for idx, poly in enumerate(valid_source_polygons):
        try:
            kml_poly = source_folder.newpolygon(name=f"Source Polygon {idx+1}")
            coords = list(poly.exterior.coords); coords.append(coords[0])
            kml_poly.outerboundaryis = coords
            kml_poly.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.grey)
            kml_poly.style.linestyle.width = 1
            kml_poly.style.linestyle.color = simplekml.Color.black
        except Exception as e: print(f"Erreur écriture polygone source {idx+1}: {e}")

    # Ajouter les zones tampons, la structure dépend de merge_buffers
    for user_input, data in buffers_by_distance.items():
        buffer_folder = doc.newfolder(name=f"Zone Tampon {user_input}")

        if merge_buffers:
            # --- CAS 1: FUSION (data = (List[ring], color)) ---
            rings, color = data
            if not rings: continue

            rings_by_alt = {}
            for ring in rings:
                 if ring and len(ring) > 0 and len(ring[0]) >= 3:
                     alt = ring[0][2]
                     if alt not in rings_by_alt: rings_by_alt[alt] = []
                     rings_by_alt[alt].append(ring)

            sorted_alts = sorted(rings_by_alt.keys())
            for alt in sorted_alts:
                 alt_folder = buffer_folder.newfolder(name=f"Altitude {alt:.1f}m")
                 for ring_idx, ring in enumerate(rings_by_alt[alt]):
                     # MODIFICATION : Remplacer LineString par Polygon
                     poly = alt_folder.newpolygon(name=f"Zone Fusionnée {ring_idx+1}")
                     poly.outerboundaryis = ring
                     poly.altitudemode = simplekml.AltitudeMode.relativetoground
                     
                     # MODIFICATION : Ajouter un style pour le polygone (remplissage + contour)
                     # Remplissage semi-transparent (alpha = 120 sur 255)
                     poly.style.polystyle.color = simplekml.Color.changealphaint(120, color)
                     # Contour de la même couleur que le remplissage, mais opaque
                     poly.style.linestyle.color = color 
                     poly.style.linestyle.width = 2
        else:
            # --- CAS 2: PAS DE FUSION (data = (List[Tuple(poly, List[ring])], color)) ---
            results_by_poly, color = data
            if not results_by_poly: continue

            for poly_idx, (source_poly, rings_for_this_poly) in enumerate(results_by_poly):
                 if not rings_for_this_poly: continue

                 poly_folder_name = f"Source Polygon {poly_idx+1}"
                 poly_folder = buffer_folder.newfolder(name=poly_folder_name)

                 rings_by_alt = {}
                 for ring in rings_for_this_poly:
                      if ring and len(ring) > 0 and len(ring[0]) >= 3:
                          alt = ring[0][2]
                          if alt not in rings_by_alt: rings_by_alt[alt] = []
                          rings_by_alt[alt].append(ring)

                 sorted_alts = sorted(rings_by_alt.keys())
                 for alt in sorted_alts:
                      alt_folder = poly_folder.newfolder(name = f"Altitude {alt:.1f}m")
                      for ring_idx, ring in enumerate(rings_by_alt[alt]):
                          # MODIFICATION : Remplacer LineString par Polygon
                          poly = alt_folder.newpolygon(name=f"Zone {ring_idx+1}")
                          poly.outerboundaryis = ring
                          poly.altitudemode = simplekml.AltitudeMode.relativetoground

                          # MODIFICATION : Ajouter un style pour le polygone (remplissage + contour)
                          poly.style.polystyle.color = simplekml.Color.changealphaint(120, color)
                          poly.style.linestyle.color = color
                          poly.style.linestyle.width = 2

    try: kml.save(output_file); print(f"Fichier KML sauvegardé : {output_file}")
    except Exception as e: print(f"Erreur sauvegarde KML {output_file}: {e}")