# app.py
import streamlit as st
import os
import tempfile

# Importer les fonctions de votre script de logique
# Assurez-vous que processing_logic.py est dans le même dossier
from processing_logic import (
    parse_buffer_size,
    process_kml_file,
    write_kml_with_folders # Importé pour être sûr qu'il est disponible, même si appelé par process_kml_file
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
Cette application génère des zones tampons 3D (en forme de demi-sphères représentées par des polygones étagés) autour des polygones contenus dans un fichier KML ou KMZ.
Uploadez un fichier, définissez les paramètres et téléchargez le résultat.
""")

# --- Colonnes pour l'agencement ---
col1, col2 = st.columns(2)

with col1:
    st.header("1. Uploader votre fichier")
    uploaded_file = st.file_uploader(
        "Choisissez un fichier KML ou KMZ",
        type=['kml', 'kmz']
    )

with col2:
    st.header("2. Définir les paramètres")
    
    # Champ pour les tailles de tampon
    buffer_sizes_str = st.text_area(
        "Tailles de tampon (une par ligne)",
        "10m\n50m\n0.1km",
        help="Entrez une ou plusieurs tailles de tampon. Exemples : 10m, 0.5km, 2nm, 100ft"
    )

    # Paramètres avancés dans un "expander"
    with st.expander("Paramètres avancés"):
        num_altitudes = st.slider(
            "Nombre de niveaux d'altitude (précision 3D)",
            min_value=2, max_value=50, value=10,
            help="Nombre de 'tranches' pour dessiner la demi-sphère. Plus le nombre est élevé, plus le rendu est lisse."
        )
        
        max_altitude_str = st.text_input(
            "Altitude maximale (en mètres)",
            "",
            help="Optionnel. Limite la hauteur de la demi-sphère. Laissez vide pour aucune limite."
        )

        merge_buffers = st.checkbox(
            "Fusionner les zones tampons qui se chevauchent",
            value=True,
            help="Si coché, les tampons de polygones différents qui se touchent formeront une seule et même zone."
        )


# --- Bouton de traitement et logique principale ---
st.header("3. Lancer le traitement")
if st.button("Générer le fichier KML des zones tampons"):

    # --- Validation des entrées ---
    if uploaded_file is None:
        st.error("❌ Veuillez d'abord uploader un fichier KML ou KMZ.")
    else:
        # Nettoyer et parser les tailles de tampon
        user_inputs = [line.strip() for line in buffer_sizes_str.split('\n') if line.strip()]
        buffer_sizes_km = []
        valid_inputs = []
        
        for u_input in user_inputs:
            try:
                radius_km = parse_buffer_size(u_input)
                buffer_sizes_km.append(radius_km)
                valid_inputs.append(u_input)
            except ValueError:
                st.warning(f"⚠️ Taille de tampon ignorée car invalide : '{u_input}'")

        if not buffer_sizes_km:
            st.error("❌ Aucune taille de tampon valide n'a été fournie.")
        else:
            with st.spinner('Traitement en cours... Veuillez patienter...'):
                try:
                    # Gérer les fichiers dans un répertoire temporaire
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # 1. Sauvegarder le fichier uploadé
                        input_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(input_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        # 2. Parser l'altitude max
                        max_altitude_m = float('inf')
                        if max_altitude_str.strip():
                            try:
                                max_altitude_m = float(max_altitude_str)
                            except ValueError:
                                st.warning("Altitude maximale invalide, elle sera ignorée.")

                        # 3. Appeler votre fonction de traitement principale
                        st.info(f"Fichier d'entrée : {uploaded_file.name}")
                        st.info(f"Tailles de tampon demandées : {', '.join(valid_inputs)}")
                        st.info(f"Fusion des zones : {'Activée' if merge_buffers else 'Désactivée'}")
                        
                        process_kml_file(
                            input_kml_path=input_path,
                            buffer_sizes_km=buffer_sizes_km,
                            user_inputs=valid_inputs,
                            num_altitudes=num_altitudes,
                            max_altitude_m=max_altitude_m,
                            merge_buffers=merge_buffers
                        )
                        
                        # 4. Préparer le fichier de sortie pour le téléchargement
                        base_name = os.path.splitext(uploaded_file.name)[0]
                        output_filename = f"{base_name}_zones_tampons_3d.kml"
                        output_path = os.path.join(temp_dir, output_filename)

                        if os.path.exists(output_path):
                            st.success("✅ Traitement terminé avec succès !")
                            
                            with open(output_path, "r", encoding='utf-8') as f:
                                kml_output_data = f.read()

                            st.download_button(
                                label="📥 Télécharger le fichier KML résultat",
                                data=kml_output_data,
                                file_name=output_filename,
                                mime="application/vnd.google-earth.kml+xml"
                            )
                        else:
                            st.error("❌ Une erreur est survenue. Le fichier de sortie n'a pas pu être généré. Vérifiez les logs si possible.")

                except Exception as e:
                    st.error(f"Une erreur critique est survenue durant le traitement : {e}")