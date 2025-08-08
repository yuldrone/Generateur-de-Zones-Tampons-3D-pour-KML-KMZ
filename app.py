# app.py
import streamlit as st
import os
import tempfile

# Importer les fonctions de votre script de logique
from processing_logic import (
    parse_buffer_size,
    process_kml_file
)

# --- Configuration de la page Streamlit ---
st.set_page_config(
    page_title="Générateur de Tampons 3D KML",
    page_icon="🌐",
    layout="wide"
)

# --- Interface Utilisateur ---
st.title("🌐 Générateur de Zones Tampons 3D pour KML/KMZ")
st.write("""
Cette application génère des zones tampons 3D (polygones étagés) autour des polygones contenus dans un fichier KML ou KMZ.
Uploadez un fichier, définissez les paramètres et téléchargez le résultat.
""")

col1, col2 = st.columns(2)
with col1:
    st.header("1. Uploader votre fichier")
    uploaded_file = st.file_uploader("Choisissez un fichier KML ou KMZ", type=['kml', 'kmz'])

with col2:
    st.header("2. Définir les paramètres")
    buffer_sizes_str = st.text_area("Tailles de tampon (une par ligne)", "10m\n50m\n0.1km", help="Exemples : 10m, 0.5km, 2nm, 100ft")
    with st.expander("Paramètres avancés"):
        num_altitudes = st.slider("Nombre de niveaux d'altitude (précision 3D)", min_value=2, max_value=50, value=10, help="Plus le nombre est élevé, plus le rendu 3D est lisse.")
        max_altitude_str = st.text_input("Altitude maximale (en mètres)", "", help="Optionnel. Laissez vide pour aucune limite.")
        merge_buffers = st.checkbox("Fusionner les zones tampons qui se chevauchent", value=True)

st.header("3. Lancer le traitement")
if st.button("Générer le fichier KML"):
    if uploaded_file is None:
        st.error("❌ Veuillez d'abord uploader un fichier.")
    else:
        user_inputs = [line.strip() for line in buffer_sizes_str.split('\n') if line.strip()]
        buffer_sizes_km, valid_inputs = [], []
        for u_input in user_inputs:
            try:
                buffer_sizes_km.append(parse_buffer_size(u_input))
                valid_inputs.append(u_input)
            except ValueError:
                st.warning(f"⚠️ Taille invalide ignorée : '{u_input}'")

        if not buffer_sizes_km:
            st.error("❌ Aucune taille de tampon valide n'a été fournie.")
        else:
            with st.spinner('Traitement en cours...'):
                try:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        input_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(input_path, "wb") as f: f.write(uploaded_file.getbuffer())

                        max_altitude_m = float('inf')
                        if max_altitude_str.strip():
                            try: max_altitude_m = float(max_altitude_str)
                            except ValueError: st.warning("Altitude maximale invalide, ignorée.")

                        st.info(f"Fichier d'entrée : {uploaded_file.name}")
                        st.info(f"Tailles demandées : {', '.join(valid_inputs)}")
                        
                        process_kml_file(
                            input_kml_path=input_path,
                            buffer_sizes_km=buffer_sizes_km,
                            user_inputs=valid_inputs,
                            num_altitudes=num_altitudes,
                            max_altitude_m=max_altitude_m,
                            merge_buffers=merge_buffers
                        )
                        
                        base_name = os.path.splitext(uploaded_file.name)[0]
                        output_filename = f"{base_name}_zones_tampons_3d.kml"
                        output_path = os.path.join(temp_dir, output_filename)

                        if os.path.exists(output_path):
                            st.success("✅ Traitement terminé !")
                            with open(output_path, "r", encoding='utf-8') as f:
                                kml_output_data = f.read()
                            st.download_button(
                                label="📥 Télécharger le fichier KML résultat",
                                data=kml_output_data,
                                file_name=output_filename,
                                mime="application/vnd.google-earth.kml+xml"
                            )
                        else:
                            st.error("❌ Erreur : Le fichier de sortie n'a pas été généré.")
                except Exception as e:
                    st.error(f"Une erreur critique est survenue : {e}")
