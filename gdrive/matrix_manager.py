import streamlit as st
import pandas as pd
import logging
from operations.sheet import SheetOperations
from gdrive.config import SPREADSHEET_ID, CENTRAL_LOG_SHEET_NAME
from fuzzywuzzy import process
from operations.audit_logger import log_action
import gspread

logger = logging.getLogger('segsisone_app.matrix_manager')

@st.cache_data(ttl=300)
def load_central_sheets_data():
    """
    Carrega TODAS as abas de dados da Planilha Principal (single-tenant).
    """
    logger.info("Carregando dados da Planilha Principal (pode usar cache)...")
    try:
        sheet_ops = SheetOperations()
        if not sheet_ops.spreadsheet:
            st.error("Erro Crítico: Não foi possível conectar à Planilha Principal.")
            return None, None, None, None

        users_data = sheet_ops.carregar_dados_aba("usuarios")
        functions_data = sheet_ops.carregar_dados_aba("funcoes")
        matrix_data = sheet_ops.carregar_dados_aba("matriz_treinamentos")
        log_data = sheet_ops.carregar_dados_aba(CENTRAL_LOG_SHEET_NAME)
        
        logger.info("Dados da Planilha Principal carregados com sucesso.")
        return users_data, functions_data, matrix_data, log_data
        
    except Exception as e:
        logger.critical(f"Falha crítica ao carregar dados da Planilha Principal: {e}", exc_info=True)
        return None, None, None, None

class MatrixManager:
    def __init__(self):
        """
        Gerencia os dados de controle da Planilha Principal:
        - Usuários (para controle de acesso)
        - Funções e Matriz de Treinamentos (para lógica de negócio)
        - Logs de Auditoria
        """
        self.users_df = pd.DataFrame()
        self.functions_df = pd.DataFrame()
        self.training_matrix_df = pd.DataFrame()
        self.log_df = pd.DataFrame()
        self.data_loaded_successfully = False
        self._load_data_from_cache()

    def _load_data_from_cache(self):
        """
        Carrega os dados da função em cache e os transforma em DataFrames robustos.
        """
        users_data, functions_data, matrix_data, log_data = load_central_sheets_data()

        user_cols = ['email', 'nome', 'role']
        func_cols = ['id', 'nome_funcao', 'descricao']
        matrix_cols = ['id', 'id_funcao', 'norma_obrigatoria']
        log_cols = ['timestamp', 'user_email', 'user_role', 'action', 'details', 'target_uo']

        if users_data and len(users_data) > 1:
            self.users_df = pd.DataFrame(users_data[1:], columns=users_data[0])
            for col in user_cols:
                if col not in self.users_df.columns: self.users_df[col] = None
            if 'email' in self.users_df.columns:
                self.users_df['email'] = self.users_df['email'].str.lower().str.strip()
        else:
            self.users_df = pd.DataFrame(columns=user_cols)

        if functions_data and len(functions_data) > 1:
            self.functions_df = pd.DataFrame(functions_data[1:], columns=functions_data[0])
            for col in func_cols:
                if col not in self.functions_df.columns: self.functions_df[col] = None
        else:
            self.functions_df = pd.DataFrame(columns=func_cols)

        if matrix_data and len(matrix_data) > 1:
            self.training_matrix_df = pd.DataFrame(matrix_data[1:], columns=matrix_data[0])
            for col in matrix_cols:
                if col not in self.training_matrix_df.columns: self.training_matrix_df[col] = None
        else:
            self.training_matrix_df = pd.DataFrame(columns=matrix_cols)

        if log_data and len(log_data) > 1:
            self.log_df = pd.DataFrame(log_data[1:], columns=log_data[0])
            for col in log_cols:
                if col not in self.log_df.columns: self.log_df[col] = None
        else:
            self.log_df = pd.DataFrame(columns=log_cols)
        
        self.data_loaded_successfully = True

    def get_user_info(self, email: str) -> dict | None:
        if self.users_df.empty: return None
        user_info = self.users_df[self.users_df['email'] == email.lower().strip()]
        return user_info.iloc[0].to_dict() if not user_info.empty else None

    def get_all_users(self) -> list:
        return self.users_df.to_dict(orient='records') if not self.users_df.empty else []

    def get_audit_logs(self) -> pd.DataFrame:
        return self.log_df

    def add_user(self, user_data: list) -> bool:
        try:
            sheet_ops = SheetOperations(SPREADSHEET_ID)
            success = sheet_ops.adc_linha_simples("usuarios", user_data)
            if success:
                log_action("ADD_USER", {"email": user_data[0], "role": user_data[2]})
                load_central_sheets_data.clear()
                return True
            return False
        except Exception as e:
            logger.error(f"Falha ao adicionar novo usuário: {e}")
            return False

    def remove_user(self, user_email: str) -> bool:
        if self.users_df.empty: return False
        user_row = self.users_df[self.users_df['email'] == user_email.lower().strip()]
        if user_row.empty: return False
        row_to_delete = user_row.index[0] + 2
        try:
            sheet_ops = SheetOperations(SPREADSHEET_ID)
            success = sheet_ops.excluir_linha_por_indice("usuarios", row_to_delete)
            if success:
                log_action("REMOVE_USER", {"email": user_email})
                load_central_sheets_data.clear()
                return True
            return False
        except Exception as e:
            logger.error(f"Falha ao remover usuário '{user_email}': {e}")
            return False

    def find_closest_function(self, employee_cargo: str, score_cutoff: int = 80) -> str | None:
        if self.functions_df.empty or not employee_cargo: return None
        function_names = self.functions_df['nome_funcao'].tolist()
        best_match = process.extractOne(employee_cargo, function_names)
        if best_match and best_match[1] >= score_cutoff:
            return best_match[0]
        return None

    def get_required_trainings_for_function(self, function_name: str) -> list:
        if self.functions_df.empty or self.training_matrix_df.empty: return []
        function = self.functions_df[self.functions_df['nome_funcao'].str.lower() == function_name.lower()]
        if function.empty: return []
        function_id = function.iloc[0]['id']
        required_df = self.training_matrix_df[self.training_matrix_df['id_funcao'] == function_id]
        return required_df['norma_obrigatoria'].dropna().tolist()

    def add_function(self, name, description):
        if not self.functions_df.empty and name.lower() in self.functions_df['nome_funcao'].str.lower().values:
            return None, f"A função '{name}' já existe."
        sheet_ops = SheetOperations(SPREADSHEET_ID)
        new_id = sheet_ops.adc_dados_aba("funcoes", [name, description])
        if new_id:
            log_action("ADD_FUNCTION", {"function_id": new_id, "name": name})
            load_central_sheets_data.clear()
            return new_id, "Função adicionada com sucesso."
        return None, "Falha ao adicionar função."

    def add_training_to_function(self, function_id, required_norm):
        if not self.training_matrix_df.empty and not self.training_matrix_df[(self.training_matrix_df['id_funcao'] == str(function_id)) & (self.training_matrix_df['norma_obrigatoria'] == required_norm)].empty:
            return None, "Este treinamento já está mapeado para esta função."
        sheet_ops = SheetOperations(SPREADSHEET_ID)
        new_id = sheet_ops.adc_dados_aba("matriz_treinamentos", [str(function_id), required_norm])
        if new_id:
            log_action("MAP_TRAINING", {"map_id": new_id, "function_id": function_id, "norm": required_norm})
            load_central_sheets_data.clear()
            return new_id, "Treinamento mapeado com sucesso."
        return None, "Falha ao mapear treinamento."
