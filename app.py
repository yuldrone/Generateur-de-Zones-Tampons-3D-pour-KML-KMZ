# app.py
import streamlit as st
import os
import tempfile
import traceback

from processing_logic import (
    parse_buffer_size,
    process_kml_file
)

st.set_page_config(page_title="Générateur de Tampons 3D KML", page_icon="🌐", layout="wide")

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
        num_altitudes = st.slider("Nombre de niveaux d'altitude", 2, 50, 10)
        max_altitude_str = st.text_input("Altitude maximale (m)")
        merge_buffers = st.checkbox("Fusionner les zones tampons", True)

st.header("3. Lancer le traitement")
if st.button("Générer le fichier KML"):
    if uploaded_file is None:
        st.error("❌ Veuillez d'abord uploader un fichier.")
    else:
        with st.spinner('Traitement en cours...'):
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    input_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(input_path, "wb") as f: f.write(uploaded_file.getbuffer())

                    user_inputs = [line.strip() for line in buffer_sizes_str.split('\n') if line.strip()]
                    buffer_sizes_km, valid_inputs = [], []
                    for u_input in user_inputs:
                        buffer_sizes_km.append(parse_buffer_size(u_input))
                        valid_inputs.append(u_input)
                    
                    max_altitude_m = float('inf')
                    if max_altitude_str.strip(): max_altitude_m = float(max_altitude_str)
                    
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
                        st.download_button("📥 Télécharger le fichier KML résultat", kml_output_data, output_filename, "application/vnd.google-earth.kml+xml")
                    else:
                        st.error("❌ Erreur : Le fichier de sortie n'a pas été généré.")
            except Exception as e:
                st.error(f"Une erreur critique est survenue : {e}")
                st.code(traceback.format_exc())
