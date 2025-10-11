import streamlit as st
from functools import wraps
import time

class PerformanceMonitor:
    """Monitora e otimiza performance do app"""
    
    @staticmethod
    def measure_time(func):
        """Decorator para medir tempo de execução"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            
            if st.secrets.get("general", {}).get("DEBUG_MODE", False):
                print(f"⏱️ {func.__name__}: {duration:.2f}s")
            
            return result
        return wrapper
    
    @staticmethod
    def optimize_dataframe(df):
        """Otimiza tipos de dados do DataFrame"""
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    df[col] = df[col].astype('category')
                except:
                    pass
        return df
    
    @staticmethod
    def lazy_load_images(url: str, placeholder: str = "🖼️"):
        """Carrega imagens sob demanda"""
        if f"img_loaded_{url}" not in st.session_state:
            st.session_state[f"img_loaded_{url}"] = False
        
        if st.button(placeholder, key=f"load_{url}"):
            st.session_state[f"img_loaded_{url}"] = True
            st.rerun()
        
        if st.session_state[f"img_loaded_{url}"]:
            st.image(url)

# Cache configuration
CACHE_CONFIG = {
    'usuarios': {
        'ttl': 1800,  # 30 min
        'show_spinner': False
    },
    'incidentes': {
        'ttl': 600,  # 10 min
        'show_spinner': "Carregando incidentes..."
    },
    'plano_acao': {
        'ttl': 300,  # 5 min
        'show_spinner': False
    }
}