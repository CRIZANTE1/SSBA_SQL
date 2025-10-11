import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

class DataCache:
    """
    Gerenciador de cache inteligente usando session_state.
    Mantém dados em memória entre mudanças de página.
    """
    
    @staticmethod
    def get_or_load(key: str, loader_func, ttl_seconds: int = 300, **kwargs):
        """
        Busca dados no cache ou carrega se expirado.
        
        Args:
            key: Chave única do cache
            loader_func: Função que carrega os dados
            ttl_seconds: Tempo de vida do cache em segundos
            **kwargs: Argumentos para loader_func
        """
        cache_key = f"cache_{key}"
        timestamp_key = f"cache_timestamp_{key}"
        
        # Verifica se existe cache válido
        if cache_key in st.session_state:
            cached_time = st.session_state.get(timestamp_key)
            
            if cached_time:
                age = (datetime.now() - cached_time).total_seconds()
                
                if age < ttl_seconds:
                    # Cache ainda válido
                    return st.session_state[cache_key]
        
        # Cache expirado ou inexistente - recarrega
        data = loader_func(**kwargs)
        
        # Salva no cache
        st.session_state[cache_key] = data
        st.session_state[timestamp_key] = datetime.now()
        
        return data
    
    @staticmethod
    def invalidate(key: str):
        """Remove dados do cache"""
        cache_key = f"cache_{key}"
        timestamp_key = f"cache_timestamp_{key}"
        
        if cache_key in st.session_state:
            del st.session_state[cache_key]
        if timestamp_key in st.session_state:
            del st.session_state[timestamp_key]
    
    @staticmethod
    def clear_all():
        """Limpa todo o cache"""
        keys_to_remove = [
            key for key in st.session_state.keys() 
            if key.startswith('cache_')
        ]
        
        for key in keys_to_remove:
            del st.session_state[key]