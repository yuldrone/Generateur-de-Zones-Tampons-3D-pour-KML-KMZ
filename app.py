import streamlit as st
import os

st.set_page_config(page_title="Diagnostic des Fichiers", layout="centered")

st.title("🕵️‍♂️ Outil de Diagnostic des Fichiers")

st.write(
    "Cette page nous aide à vérifier quels fichiers sont réellement présents "
    "dans le dépôt de votre application sur le serveur de Streamlit."
)

st.header("Liste des fichiers trouvés à la racine du dépôt :")

try:
    # Obtenir le chemin du répertoire courant
    current_directory = os.path.dirname(os.path.abspath(__file__))
    
    # Lister les fichiers et dossiers
    files_and_dirs = os.listdir(current_directory)
    
    # Afficher la liste
    st.code(files_and_dirs, language=None)
    
    # Vérification cruciale
    st.header("Analyse :")
    if 'processing_logic.py' in files_and_dirs:
        st.success("✅ BONNE NOUVELLE : 'processing_logic.py' est bien présent !")
        st.write("Si l'erreur d'importation persiste, il pourrait s'agir d'une faute de frappe dans le nom du fichier ou d'un problème de cache.")
    else:
        st.error("❌ PROBLÈME IDENTIFIÉ : 'processing_logic.py' est INTROUVABLE.")
        st.warning(
            "Causes possibles :\n"
            "1. Le fichier n'a pas été 'push' (envoyé) sur GitHub.\n"
            "2. Le fichier est dans un sous-dossier.\n"
            "3. Le nom du fichier a une faute de frappe ou une majuscule (doit être `processing_logic.py` exactement)."
        )

except Exception as e:
    st.error(f"Une erreur est survenue lors de la tentative de lecture du dossier : {e}")