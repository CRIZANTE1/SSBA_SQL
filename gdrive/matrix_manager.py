import streamlit as st
import pandas as pd
import logging
import gspread
from operations.sheet import SheetOperations
from operations.audit_logger import log_action

logger = logging.getLogger('abrangencia_app.matrix_manager')

@st.cache_resource
def get_matrix_manager():
    """
    Retorna uma instância única (singleton) do MatrixManager para a sessão do usuário.
    """
    return MatrixManager()

class MatrixManager:
    """
    Gerencia os dados de controle da Planilha Principal: usuários e logs de auditoria.
    A gestão de uma lista explícita de UOs foi removida para simplificação.
    """
    def __init__(self):
        self.sheet_ops = SheetOperations()
        if not self.sheet_ops.spreadsheet:
            raise ConnectionError("Falha na conexão com a Planilha Principal.")

    @st.cache_data(ttl=300)
    def _get_df(_self, sheet_name: str) -> pd.DataFrame:
        logger.info(f"Carregando dados da aba '{sheet_name}' (pode usar cache)...")
        return _self.sheet_ops.get_df_from_worksheet(sheet_name)

    # --- Métodos de Usuários ---

    def get_all_users_df(self) -> pd.DataFrame:
        return self._get_df("usuarios")

    def get_user_info(self, email: str) -> dict | None:
        users_df = self.get_all_users_df()
        if users_df.empty or 'email' not in users_df.columns:
            return None
        
        user_info = users_df[users_df['email'].str.lower().str.strip() == email.lower().strip()]
        return user_info.iloc[0].to_dict() if not user_info.empty else None

    def add_user(self, user_data: list) -> bool:
        logger.info(f"Adicionando novo usuário: {user_data[0]}")
        success = self.sheet_ops.adc_linha_simples("usuarios", user_data)
        if success:
            log_action("ADD_USER", {"email": user_data[0], "role": user_data[2]})
            st.cache_data.clear()
        return success

    def update_user(self, email: str, updates: dict) -> bool:
        logger.info(f"Tentando atualizar usuário '{email}' com dados: {updates}")
        try:
            worksheet = self.sheet_ops.spreadsheet.worksheet("usuarios")
            cell = worksheet.find(email, in_column=1)
            if not cell:
                logger.warning(f"Usuário com e-mail '{email}' não encontrado para atualização.")
                return False

            row_number = cell.row
            header = worksheet.row_values(1)
            cells_to_update = []
            
            for col_name, new_value in updates.items():
                if col_name in header:
                    col_index = header.index(col_name) + 1
                    cells_to_update.append(gspread.Cell(row_number, col_index, str(new_value)))
                
            if cells_to_update:
                worksheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
                log_action("UPDATE_USER", {"email": email, "updates": updates})
                st.cache_data.clear()
                logger.info(f"Usuário '{email}' atualizado com sucesso.")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao atualizar usuário '{email}': {e}", exc_info=True)
            return False

    def remove_user(self, user_email: str) -> bool:
        logger.info(f"Tentando remover usuário: {user_email}")
        try:
            worksheet = self.sheet_ops.spreadsheet.worksheet("usuarios")
            cell = worksheet.find(user_email.strip(), in_column=1)
            if not cell:
                logger.warning(f"Usuário com e-mail '{user_email}' não encontrado para remoção.")
                return False
            
            success = self.sheet_ops.excluir_linha_por_indice("usuarios", cell.row)
            if success:
                log_action("REMOVE_USER", {"email": user_email})
                st.cache_data.clear()
            return success
        except Exception as e:
            logger.error(f"Erro ao remover usuário '{user_email}': {e}", exc_info=True)
            return False

    # --- Métodos de Auditoria ---

    def get_audit_logs(self) -> pd.DataFrame:
        return self._get_df("log_auditoria")
