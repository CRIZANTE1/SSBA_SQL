import streamlit as st
import google.generativeai as genai
import logging

logging.basicConfig(level=logging.INFO)

def load_models():
    extraction_model = None
    audit_model = None

    try:
        extraction_key = st.secrets.get("general", {}).get("GEMINI_EXTRACTION_KEY")
        audit_key = st.secrets.get("general", {}).get("GEMINI_AUDIT_KEY")
        
        # Opção 1: Usar a mesma chave para ambos
        if extraction_key:
            genai.configure(api_key=extraction_key)
            extraction_model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
            audit_model = genai.GenerativeModel('gemini-2.5-flash')
            logging.info("Modelos carregados com a mesma API key.")
        else:
            st.warning("Chave GEMINI_EXTRACTION_KEY não encontrada.")
            
        return extraction_model, audit_model

    except Exception as e:
        st.error(f"Erro crítico ao carregar os modelos de IA: {e}")
        return None, None





