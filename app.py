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
    st.info("Tentative d'importation de `processing_logic`...")
    
    from processing_logic import (
        parse_buffer_size,
        process_kml_file
    )
    
    st.success("✅ L'importation de `processing_logic.py` a réussi !")
    st.write("C'est inattendu, le problème est peut-être résolu. Essayez de remettre le code original de l'application.")

except Exception as e:
    st.error("❌ ERREUR LORS DE L'IMPORTATION DE `processing_logic.py` !")
    
    st.subheader("Message d'erreur original :")
    st.code(e, language=None)
    
    st.subheader("Traceback complet (la source du problème) :")
    # Affiche le traceback complet qui nous dira la ligne exacte du problème.
    full_traceback = traceback.format_exc()
    st.code(full_traceback, language='python')
