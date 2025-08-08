# processing_logic.py
import sys, os, re, numpy as np, simplekml, zipfile, math, colorsys # NOUVEL IMPORT
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import transform, unary_union
from pyproj import Transformer
from xml.etree import ElementTree as ET
from math import cos, radians, sqrt

def parse_buffer_size(s):
    m = re.match(r"^\s*(\d+(\.\d+)?)\s*(m|ft|km|nm)\s*$", s.lower())
    if not m: raise ValueError(f"Format invalide: '{s}'.")
    v, _, u = m.groups()[:3]; c = {"m": 0.001, "ft": 0.0003048, "km": 1, "nm": 1.852}
    return float(v) * c[u]

def compute_mean_latitude(coords):
    lats = [lat for poly in coords for _, lat in poly]
    return sum(lats) / len(lats) if lats else 0

# --- MODIFICATION : Ancienne fonction 'calculate_color' supprimée ---
# --- NOUVELLE FONCTION DE COULEUR ---
def get_buffer_color_by_index(index):
    """
    Retourne une couleur spécifique en fonction de l'index de la zone tampon.
    Suit la séquence demandée, puis génère des couleurs distinctes.
    """
    # Séquence de couleurs prédéfinies
    predefined_colors = [
        simplekml.Color.lightgreen,
        simplekml.Color.cyan,
        simplekml.Color.yellow,
        simplekml.Color.orange,
        simplekml.Color.red,
        simplekml.Color.blue,
        simplekml.Color.firebrick  # Un rouge brique pour "rouge foncé"
    ]
    
    if index < len(predefined_colors):
        return predefined_colors[index]
    else:
        # Pour les couleurs suivantes, on génère des couleurs vives et distinctes
        # en utilisant l'espace colorimétrique HSV (Teinte, Saturation, Valeur)
        # C'est mieux qu'un simple aléatoire car ça évite les couleurs ternes ou similaires.
        hue = (0.6 + (index - len(predefined_colors)) * 0.61803398875) % 1.0
        rgb = colorsys.hsv_to_rgb(hue, 0.9, 0.95) # Saturation et luminosité élevées
        # Conversion du format RGB (0-1) au format KML (0-255)
        return simplekml.Color.rgb(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))

def read_kml_polygons(path):
    content = None
    try:
        if path.lower().endswith('.kmz'):
            with zipfile.ZipFile(path, 'r') as z:
                kml_file = next((f for f in z.namelist() if f.lower().endswith('.kml')), None)
                if kml_file: content = z.read(kml_file)
        elif path.lower().endswith('.kml'):
            with open(path, 'rb') as f: content = f.read()
    except Exception as e: print(f"Erreur lecture {path}: {e}"); return []
    if not content: return []
    try: content_str = content.decode('utf-8')
    except UnicodeDecodeError: content_str = content.decode('latin-1')
    root = ET.fromstring(content_str)
    ns = {'kml': root.tag.split('}')[0][1:] if '}' in root.tag else 'http://www.opengis.net/kml/2.2'}
    paths = ['.//kml:Placemark//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates']
    polys = []
    for p in paths:
        for coords_tag in root.findall(p, ns):
            if coords_tag.text:
                pts = [(float(c.split(',')[0]), float(c.split(',')[1])) for c in coords_tag.text.strip().split() if len(c.split(',')) >= 2]
                if len(pts) >= 3: polys.append(Polygon(pts))
    return polys

def generate_precise_3d_buffers_for_polygons(polys, dist_km, num_alts=10, max_alt_m=float('inf'), merge=True):
    valid_polys = [p for p in polys if p.is_valid and not p.is_empty]
    if not valid_polys: return []
    mean_lat = compute_mean_latitude([list(p.exterior.coords) for p in valid_polys])
    corr = 1 / cos(radians(mean_lat)) if cos(radians(mean_lat)) != 0 else 1
    trans_fwd = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
    trans_back = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True).transform
    buf_m = dist_km * corr * 1000
    eff_max_alt = min(buf_m, max_alt_m)
    alts = np.linspace(0, eff_max_alt, num_alts) if num_alts > 1 else [eff_max_alt]
    
    if merge:
        all_rings = []
        proj_polys = [transform(trans_fwd, p) for p in valid_polys]
        for alt in alts:
            h_dist = sqrt(max(0, buf_m**2 - alt**2))
            buffers = [p.buffer(h_dist, resolution=16) for p in proj_polys]
            merged = unary_union([b for b in buffers if b.is_valid and not b.is_empty])
            geoms = list(merged.geoms) if isinstance(merged, MultiPolygon) else [merged]
            for g in geoms:
                if g.is_valid and not g.is_empty:
                    g_geo = transform(trans_back, g)
                    all_rings.append([(lon, lat, alt) for lon, lat in g_geo.exterior.coords])
        return all_rings
    else:
        results = []
        for poly in valid_polys:
            rings = []
            proj_poly = transform(trans_fwd, poly)
            for alt in alts:
                h_dist = sqrt(max(0, buf_m**2 - alt**2))
                buffered = proj_poly.buffer(h_dist, resolution=16)
                geoms = list(buffered.geoms) if isinstance(buffered, MultiPolygon) else [buffered]
                for g in geoms:
                    if g.is_valid and not g.is_empty:
                        g_geo = transform(trans_back, g)
                        rings.append([(lon, lat, alt) for lon, lat in g_geo.exterior.coords])
            results.append((poly, rings))
        return results

# --- MODIFICATION : Mise à jour des styles dans cette fonction ---
def write_kml_with_folders(src_polys, bufs_data, out_file, merge=True):
    kml = simplekml.Kml()
    doc = kml.newdocument(name=os.path.splitext(os.path.basename(out_file))[0])
    src_f = doc.newfolder(name="Polygones Sources")
    for i, p in enumerate(p for p in src_polys if p.is_valid and not p.is_empty):
        poly = src_f.newpolygon(name=f"Source {i+1}"); poly.outerboundaryis = list(p.exterior.coords)
        # Style du polygone original
        poly.style.polystyle.color = simplekml.Color.changealphaint(80, simplekml.Color.white) # Remplissage blanc très transparent
        poly.style.linestyle.color = simplekml.Color.white # Contour blanc
        poly.style.linestyle.width = 2 # Largeur 2 pixels

    def create_poly(parent, ring, name, color):
        poly = parent.newpolygon(name=name); poly.outerboundaryis = ring
        poly.altitudemode = simplekml.AltitudeMode.relativetoground
        # Style des polygones de tampon
        poly.style.polystyle.color = simplekml.Color.changealphaint(120, color) # Remplissage coloré semi-transparent (120/255)
        poly.style.linestyle.color = color # Contour de la même couleur
        poly.style.linestyle.width = 2 # Largeur 2 pixels

    for u_input, (data, color) in bufs_data.items():
        buf_f = doc.newfolder(name=f"Zone Tampon {u_input}")
        if merge:
            rings_by_alt = {}
            for ring in data:
                if ring: rings_by_alt.setdefault(ring[0][2], []).append(ring)
            for alt in sorted(rings_by_alt.keys()):
                alt_f = buf_f.newfolder(name=f"Altitude {alt:.1f}m")
                for i, ring in enumerate(rings_by_alt[alt]): create_poly(alt_f, ring, f"Zone {i+1}", color)
        else:
            for i, (src_poly, rings) in enumerate(data):
                if not rings: continue
                poly_f = buf_f.newfolder(name=f"Source Polygon {i+1}")
                rings_by_alt = {}
                for ring in rings:
                    if ring: rings_by_alt.setdefault(ring[0][2], []).append(ring)
                for alt in sorted(rings_by_alt.keys()):
                    alt_f = poly_f.newfolder(name=f"Altitude {alt:.1f}m")
                    for j, ring in enumerate(rings_by_alt[alt]): create_poly(alt_f, ring, f"Zone {j+1}", color)
    kml.save(out_file)
    print(f"KML sauvegardé : {out_file}")

# --- MODIFICATION : Utilise la nouvelle fonction de couleur ---
def process_kml_file(input_kml_path, buffer_sizes_km, user_inputs, num_altitudes, max_altitude_m=float('inf'), merge_buffers=True):
    print(f"Traitement: {input_kml_path}")
    source_polygons = read_kml_polygons(input_kml_path)
    valid_source_polygons = [p for p in source_polygons if p.is_valid and not p.is_empty]
    if not valid_source_polygons: print("Aucun polygone valide trouvé."); return
    
    output_folder = os.path.dirname(input_kml_path)
    base_name = os.path.splitext(os.path.basename(input_kml_path))[0]
    output_file = os.path.join(output_folder, f"{base_name}_zones_tampons_3d.kml")
    
    buffers_data = {}
    
    # On itère avec un index pour pouvoir choisir la bonne couleur
    for index, (r_km, u_input) in enumerate(zip(buffer_sizes_km, user_inputs)):
        # On utilise la nouvelle fonction de couleur basée sur l'index
        color = get_buffer_color_by_index(index)
        
        data = generate_precise_3d_buffers_for_polygons(valid_source_polygons, r_km, num_altitudes, max_altitude_m, merge_buffers)
        buffers_data[u_input] = (data, color)
    
    write_kml_with_folders(valid_source_polygons, buffers_data, output_file, merge_buffers)
