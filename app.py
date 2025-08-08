import streamlit as st
import os
import tempfile

# Importer non seulement la fonction principale, mais aussi les sous-fonctions pour les tester
from processing_logic import (
    process_kml_file,
    read_kml_polygons # On importe cette fonction pour l'appeler directement
)

# --- Configuration de la page Streamlit ---
st.set_page_config(page_title="Générateur de Tampons 3D KML", page_icon="🌐", layout="wide")

# --- Interface Utilisateur (inchangée) ---
st.title("🌐 Générateur de Zones Tampons 3D pour KML/KMZ")
st.write("Uploadez un fichier, définissez les paramètres et téléchargez le résultat.")
col1, col2 = st.columns(2)
with col1:
    st.header("1. Uploader votre fichier")
    uploaded_file = st.file_uploader("Choisissez un fichier KML ou KMZ", type=['kml', 'kmz'])
with col2:
    st.header("2. Définir les paramètres")
    buffer_sizes_str = st.text_area("Tailles de tampon (une par ligne)", "12m\n132m\n1km", help="Exemples : 10m, 0.5km, 2nm")
    with st.expander("Paramètres avancés"):
        num_altitudes = st.slider("Nombre de niveaux d'altitude", min_value=2, max_value=50, value=10)
        max_altitude_str = st.text_input("Altitude maximale (en mètres)", "")
        merge_buffers = st.checkbox("Fusionner les zones tampons", value=True)

# --- BOUTON DE TRAITEMENT MODIFIÉ POUR LE DIAGNOSTIC ---
st.header("3. Lancer le traitement")
if st.button("Générer le fichier KML"):
    if uploaded_file is None:
        st.error("❌ Veuillez d'abord uploader un fichier.")
    else:
        with st.spinner('Analyse du fichier KML en cours...'):
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    input_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(input_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    # --- ÉTAPE DE DIAGNOSTIC 1 : LIRE LE KML ---
                    st.info(f"DIAGNOSTIC : Lecture du fichier '{uploaded_file.name}'...")
                    source_polygons = read_kml_polygons(input_path)
                    
                    if not source_polygons:
                        st.error(f"❌ PROBLÈME IDENTIFIÉ : Aucun polygone n'a été trouvé dans le fichier KML.")
                        st.warning("Vérifiez que votre fichier contient bien des balises `<Polygon>` avec des coordonnées.")
                        st.stop() # Arrête l'exécution ici
                    
                    st.success(f"✅ DIAGNOSTIC : {len(source_polygons)} géométrie(s) de type polygone trouvée(s) !")

                    # --- ÉTAPE DE DIAGNOSTIC 2 : VALIDER LES POLYGONES ---
                    st.info("DIAGNOSTIC : Vérification de la validité des géométries...")
                    valid_source_polygons = [p for p in source_polygons if p.is_valid and not p.is_empty]

                    if not valid_source_polygons:
                        st.error(f"❌ PROBLÈME IDENTIFIÉ : {len(source_polygons)} polygone(s) ont été trouvés, mais aucun n'est valide géométriquement.")
                        st.warning("Cela peut arriver si les polygones se croisent eux-mêmes ou ont des erreurs de topologie.")
                        st.stop() # Arrête l'exécution ici
                    
                    st.success(f"✅ DIAGNOSTIC : {len(valid_source_polygons)} polygone(s) sont valides et prêts pour le traitement.")
                    
                    # --- Si on arrive ici, on lance le traitement complet ---
                    st.info("DIAGNOSTIC : Les vérifications sont bonnes. Lancement du traitement complet...")

                    # On reprend la logique normale
                    user_inputs = [line.strip() for line in buffer_sizes_str.split('\n') if line.strip()]
                    buffer_sizes_km, valid_inputs = [], []
                    for u_input in user_inputs:
                        try:
                            from processing_logic import parse_buffer_size
                            buffer_sizes_km.append(parse_buffer_size(u_input))
                            valid_inputs.append(u_input)
                        except ValueError:
                            st.warning(f"⚠️ Taille invalide ignorée : '{u_input}'")
                    
                    max_altitude_m = float('inf')
                    if max_altitude_str.strip():
                        try: max_altitude_m = float(max_altitude_str)
                        except ValueError: st.warning("Altitude maximale invalide, ignorée.")

                    process_kml_file(
                        input_kml_path=input_path,
                        buffer_sizes_km=buffer_sizes_km,
                        user_inputs=valid_inputs,
                        num_altitudes=num_altitudes,
                        max_altitude_m=max_altitude_m,
                        merge_buffers=merge_buffers
                    )
                    
                    output_filename = f"{os.path.splitext(uploaded_file.name)[0]}_zones_tampons_3d.kml"
                    output_path = os.path.join(temp_dir, output_filename)

                    if os.path.exists(output_path):
                        st.success("✅ Traitement terminé avec succès !")
                        with open(output_path, "r", encoding='utf-8') as f:
                            kml_output_data = f.read()
                        st.download_button("📥 Télécharger le fichier KML résultat", kml_output_data, output_filename)
                    else:
                        st.error("❌ Erreur : Le traitement a semblé se terminer, mais le fichier de sortie n'a toujours pas été généré.")
            except Exception as e:
                import traceback
                st.error(f"Une erreur critique est survenue durant le traitement : {e}")
                st.code(traceback.format_exc())
