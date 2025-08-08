import streamlit as st
import os
import tempfile
import traceback

# On importe TOUTES les fonctions nécessaires pour ré-implémenter le processus
from processing_logic import (
    parse_buffer_size,
    read_kml_polygons,
    generate_precise_3d_buffers_for_polygons,
    get_buffer_color_by_index,
    write_kml_with_folders
)

st.set_page_config(page_title="Générateur de Tampons 3D KML", page_icon="🌐", layout="wide")

st.title("🕵️‍♂️ Générateur de Tampons 3D (Mode Diagnostic Avancé)")
st.write("Uploadez un fichier, définissez les paramètres et suivez le traitement en direct.")
col1, col2 = st.columns(2)
with col1:
    st.header("1. Uploader votre fichier")
    uploaded_file = st.file_uploader("Choisissez un fichier KML ou KMZ", type=['kml', 'kmz'])
with col2:
    st.header("2. Définir les paramètres")
    buffer_sizes_str = st.text_area("Tailles de tampon", "12m\n132m\n1km", help="Exemples : 10m, 0.5km, 2nm")
    with st.expander("Paramètres avancés"):
        num_altitudes = st.slider("Niveaux d'altitude", 2, 50, 10)
        max_altitude_str = st.text_input("Altitude max (m)")
        merge_buffers = st.checkbox("Fusionner les zones", True)

st.header("3. Lancer le traitement et suivre le log")
if st.button("Lancer le diagnostic et la génération"):
    if uploaded_file is None:
        st.error("❌ Veuillez uploader un fichier.")
    else:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                input_path = os.path.join(temp_dir, uploaded_file.name)
                with open(input_path, "wb") as f: f.write(uploaded_file.getbuffer())

                st.info("--- DÉBUT DU TRAITEMENT ---")
                
                # Étape 1: Lecture (on sait qu'elle marche)
                source_polygons = read_kml_polygons(input_path)
                valid_source_polygons = [p for p in source_polygons if p.is_valid and not p.is_empty]
                st.success(f"Lecture réussie : {len(valid_source_polygons)} polygone(s) valide(s) trouvé(s).")

                # Étape 2: Préparation des entrées
                user_inputs = [line.strip() for line in buffer_sizes_str.split('\n') if line.strip()]
                buffer_sizes_km, valid_inputs = [], []
                for u_input in user_inputs:
                    buffer_sizes_km.append(parse_buffer_size(u_input))
                    valid_inputs.append(u_input)
                
                max_altitude_m = float('inf')
                if max_altitude_str.strip(): max_altitude_m = float(max_altitude_str)

                buffers_data = {}
                st.info("--- BOUCLE DE GÉNÉRATION DES TAMPONS ---")
                
                # Étape 3: La boucle de génération, suivie pas à pas
                for index, (r_km, u_input) in enumerate(zip(buffer_sizes_km, valid_inputs)):
                    st.write(f"---")
                    st.subheader(f"Traitement du tampon : '{u_input}'")
                    color = get_buffer_color_by_index(index)
                    
                    st.info(f"Appel de `generate_precise_3d_buffers_for_polygons`...")
                    
                    # C'est l'appel crucial
                    generated_data = generate_precise_3d_buffers_for_polygons(
                        valid_source_polygons, r_km, num_altitudes, max_altitude_m, merge_buffers
                    )
                    
                    # On affiche ce qu'on a reçu
                    if not generated_data:
                        st.error(f"RÉSULTAT : La fonction a retourné un résultat VIDE (`[]`) pour '{u_input}'.")
                    else:
                        st.success(f"RÉSULTAT : La fonction a retourné {len(generated_data)} anneaux/groupes pour '{u_input}'.")
                        # st.write(generated_data[:1]) # Décommenter pour voir le premier anneau généré

                    buffers_data[u_input] = (generated_data, color)

                st.info("--- FIN DE LA BOUCLE ---")
                
                # Étape 4: Écriture du fichier
                st.subheader("Tentative d'écriture du fichier KML final")
                output_folder = temp_dir
                base_name = os.path.splitext(uploaded_file.name)[0]
                output_file = os.path.join(output_folder, f"{base_name}_zones_tampons_3d.kml")
                
                write_kml_with_folders(valid_source_polygons, buffers_data, output_file, merge_buffers)
                
                # Étape 5: Vérification finale
                st.info("Vérification de l'existence du fichier de sortie...")
                if os.path.exists(output_file):
                    st.success("✅ FICHIER KML FINAL GÉNÉRÉ AVEC SUCCÈS !")
                 
