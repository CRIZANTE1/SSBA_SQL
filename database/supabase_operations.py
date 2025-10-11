import streamlit as st
import pandas as pd
import logging
from datetime import datetime
from sqlalchemy import text
from .supabase_config import get_database_engine

logger = logging.getLogger('abrangencia_app.supabase_operations')

class SupabaseOperations:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Criando instância única de SupabaseOperations")
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        try:
            # Cria engine sem RLS por padrão
            # RLS será aplicado quando necessário via get_engine_with_rls()
            self.engine = get_database_engine()
            logger.info("SupabaseOperations inicializado com sucesso")
        except Exception as e:
            logger.critical(f"Falha ao inicializar SupabaseOperations: {e}")
            self.engine = None
        
        self._initialized = True

    def get_engine_with_rls(self):
        """
        MELHORADO: Valida se o usuário está autenticado antes de criar engine
        """
        user_email = None
        
        if hasattr(st, 'session_state'):
            user_email = st.session_state.get('user_info', {}).get('email')
            if not user_email:
                user_email = st.session_state.get('user_info_custom', {}).get('email')
        
        # <<< ADICIONAR VALIDAÇÃO >>>
        if not user_email:
            logger.critical("⚠️ TENTATIVA DE ACESSO SEM AUTENTICAÇÃO!")
            raise PermissionError("Usuário não autenticado. RLS não pode ser aplicado.")
        
        logger.info(f"✅ Criando engine com RLS para usuário: {user_email}")
        return get_database_engine(user_email)

    @st.cache_data(ttl=300)  # Reduzido para 5 minutos
    def get_table_data(_self, table_name: str) -> pd.DataFrame:
        """Carrega todos os dados de uma tabela (com RLS aplicado)"""
        if not _self.engine:
            logger.error("Database engine não está disponível")
            return pd.DataFrame()
        
        try:
            engine = _self.get_engine_with_rls()
            query = text(f"SELECT * FROM {table_name}")
            with engine.connect() as conn:
                df = pd.read_sql(query, conn)
            return df
        except Exception as e:
            logger.error(f"Erro ao carregar dados da tabela '{table_name}': {e}")
            return pd.DataFrame()

    def insert_row(self, table_name: str, data: dict) -> dict | None:
        """Insere uma linha (com RLS aplicado)"""
        if not self.engine:
            return None
        
        try:
            engine = self.get_engine_with_rls()
            columns = ', '.join(data.keys())
            placeholders = ', '.join([f':{key}' for key in data.keys()])
            query = text(f"""
                INSERT INTO {table_name} ({columns})
                VALUES ({placeholders})
                RETURNING *
            """)
            
            with engine.connect() as conn:
                result = conn.execute(query, data)
                conn.commit()
                row = result.fetchone()
                
                if row:
                    st.cache_data.clear()
                    return dict(row._mapping)
            
            return None
        except Exception as e:
            logger.error(f"Erro ao inserir na tabela '{table_name}': {e}")
            return None

    def insert_row_without_rls(self, table_name: str, data: dict) -> dict | None:
        """Insere uma linha (sem RLS aplicado)"""
        if not self.engine:
            return None
        
        try:
            engine = self.engine
            columns = ', '.join(data.keys())
            placeholders = ', '.join([f':{key}' for key in data.keys()])
            query = text(f"""
                INSERT INTO {table_name} ({columns})
                VALUES ({placeholders})
                RETURNING *
            """)
            
            with engine.connect() as conn:
                result = conn.execute(query, data)
                conn.commit()
                row = result.fetchone()
                
                if row:
                    return dict(row._mapping)
            
            return None
        except Exception as e:
            logger.error(f"Erro ao inserir na tabela '{table_name}' sem RLS: {e}")
            return None

    def insert_batch(self, table_name: str, data_list: list[dict]) -> bool:
        """Insere múltiplas linhas de uma vez (com RLS aplicado)"""
        if not self.engine or not data_list:
            return False
        
        try:
            engine = self.get_engine_with_rls()
            columns = ', '.join(data_list[0].keys())
            placeholders = ', '.join([f':{key}' for key in data_list[0].keys()])
            query = text(f"""
                INSERT INTO {table_name} ({columns})
                VALUES ({placeholders})
            """)
            
            with engine.connect() as conn:
                conn.execute(query, data_list)
                conn.commit()
            
            st.cache_data.clear()
            return True
        except Exception as e:
            logger.error(f"Erro ao inserir lote na tabela '{table_name}': {e}")
            return False

    def update_row(self, table_name: str, row_id: int, updates: dict) -> bool:
        """Atualiza uma linha específica pelo ID (com RLS aplicado)"""
        if not self.engine or not updates:
            return False
        
        try:
            engine = self.get_engine_with_rls()
            set_clause = ', '.join([f"{key} = :{key}" for key in updates.keys()])
            query = text(f"""
                UPDATE {table_name}
                SET {set_clause}
                WHERE id = :id
            """)
            
            params = {**updates, 'id': row_id}
            
            with engine.connect() as conn:
                conn.execute(query, params)
                conn.commit()
            
            st.cache_data.clear()
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar linha na tabela '{table_name}': {e}")
            return False

    def delete_row(self, table_name: str, row_id: int) -> bool:
        """Deleta uma linha pelo ID (com RLS aplicado)"""
        if not self.engine:
            return False
        
        try:
            engine = self.get_engine_with_rls()
            query = text(f"DELETE FROM {table_name} WHERE id = :id")
            
            with engine.connect() as conn:
                conn.execute(query, {'id': row_id})
                conn.commit()
            
            st.cache_data.clear()
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar linha da tabela '{table_name}': {e}")
            return False

    def get_by_field_cached(self, table_name: str, field: str, value, ttl: int = 600) -> pd.DataFrame:
        """
        Versão cacheada de get_by_field para reduzir queries repetidas.
    
        Args:
            ttl: Tempo de cache em segundos (padrão: 10 minutos)
        """
        @st.cache_data(ttl=ttl)
        def _cached_query(_self, _table, _field, _value):
            return _self.get_by_field(_table, _field, _value)
        
        return _cached_query(self, table_name, field, value)

    def get_by_field(self, table_name: str, field: str, value) -> pd.DataFrame:
        """Busca registros por um campo específico (com RLS aplicado)"""
        if not self.engine:
            return pd.DataFrame()
        
        try:
            engine = self.get_engine_with_rls()
            query = text(f"SELECT * FROM {table_name} WHERE {field} = :value")
            
            with engine.connect() as conn:
                df = pd.read_sql(query, conn, params={'value': value})
            
            return df
        except Exception as e:
            logger.error(f"Erro ao buscar na tabela '{table_name}': {e}")
            return pd.DataFrame()

    def execute_query(self, query: str, params: dict = None) -> pd.DataFrame:
        """Executa uma query customizada (com RLS aplicado)"""
        if not self.engine:
            return pd.DataFrame()
        
        try:
            engine = self.get_engine_with_rls()
            with engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params or {})
            return df
        except Exception as e:
            logger.error(f"Erro ao executar query customizada: {e}")
            return pd.DataFrame()

    def execute_non_query(self, query: str, params: dict = None) -> bool:
        """Executa uma query que não retorna dados (com RLS aplicado)"""
        if not self.engine:
            return False
        
        try:
            engine = self.get_engine_with_rls()
            with engine.connect() as conn:
                conn.execute(text(query), params or {})
                conn.commit()
            
            st.cache_data.clear()
            return True
        except Exception as e:
            logger.error(f"Erro ao executar non-query: {e}")
            return False