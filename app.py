import streamlit as st
import traceback

st.set_page_config(page_title="Débogueur d'Importation", layout="centered")

st.title("🔬 Débogueur d'Importation")
st.write(
    "Ce script tente d'importer `processing_logic.py` et affichera "
    "l'erreur exacte si l'importation échoue."
)

st.header("Résultat de la tentative d'importation :")

try:
    # C'est la ligne qui pose problème.
    # Nous l'enroulons dans un bloc try...except pour voir l'erreur cachée.
    st.info("Tentative d'importation de `processing_logic`...")
    
    from processing_logic import (
        parse_buffer_size,
        process_kml_file
    )
    
    # Si on arrive ici, c'est que l'importation a réussi.
    st.success("✅ L'importation de `processing_logic.py` a réussi !")
    st.write("Le problème est peut-être résolu ou était lié à un état intermittent.")

except Exception as e:
    # Si l'importation échoue, le code dans ce bloc 'except' sera exécuté.
    st.error("❌ ERREUR LORS DE L'IMPORTATION DE `processing_logic.py` !")
    
    st.subheader("Message d'erreur original :")
    # Affiche le message d'erreur de base
    st.code(e, language=None)
    
    st.subheader("Traceback complet (la source du problème) :")
    # Ceci est la partie la plus importante :
    # Elle nous donnera le chemin complet de l'erreur, y compris
    # la ligne exacte dans `processing_logic.py` qui a échoué.
    full_traceback = traceback.format_exc()
    st.code(full_traceback, language='python')
