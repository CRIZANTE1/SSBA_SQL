import streamlit as st
import sys
import os


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from operations.front import front_page
from auth.login_page import show_login_page, show_sidebar

def main():
    
    if show_login_page():
        st.session_state.user = st.session_state.user if 'user' in st.session_state else None
        show_sidebar()
        front_page()

if __name__ == "__main__":
    main()
    st.caption('Copyright 2025, Cristian Ferreira Carlos, Todos os direitos reservados.')
    st.caption('https://www.linkedin.com/in/cristian-ferreira-carlos-256b19161/')
