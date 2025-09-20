import streamlit as st
import pandas as pd
import logging
import gspread
from datetime import datetime
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
    Gerencia os dados de controle da Planilha Principal: usuários, solicitações de acesso
    e logs de auditoria.
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

    def get_all_units(self) -> list[str]:
        """
        Retorna uma lista de nomes de unidades operacionais únicas a partir da
        planilha de usuários, excluindo o valor '*' do admin global.
        """
        users_df = self.get_all_users_df()
        if users_df.empty or 'unidade_associada' not in users_df.columns:
            return []

        # Pega valores únicos, remove nulos/NaN, converte para string
        units = users_df['unidade_associada'].dropna().unique()

        # Filtra o valor '*' e strings vazias, e então ordena a lista
        unit_list = sorted([str(unit) for unit in units if unit and str(unit).strip() and str(unit) != '*'])
        
        return unit_list

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

    # --- Métodos de Solicitação de Acesso ---

    def add_access_request(self, email: str, name: str, unit: str) -> bool:
        """Adiciona um novo pedido de acesso à aba de solicitações."""
        requests_df = self.get_pending_access_requests()
        if not requests_df.empty and not requests_df[requests_df['email'].str.lower() == email.lower()].empty:
            logger.warning(f"Solicitação de acesso duplicada para {email}. Nenhuma ação tomada.")
            return True

        logger.info(f"Registrando nova solicitação de acesso para {email} da unidade {unit}.")
        
        request_data = [
            email,
            name,
            unit,
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "pendente"
        ]
        return self.sheet_ops.adc_linha_simples("solicitacoes_acesso", request_data)

    def get_pending_access_requests(self) -> pd.DataFrame:
        """Retorna um DataFrame com todas as solicitações de acesso pendentes."""
        requests_df = self._get_df("solicitacoes_acesso")
        if requests_df.empty or 'status' not in requests_df.columns:
            return pd.DataFrame()
        return requests_df[requests_df['status'].str.lower() == 'pendente']

    def approve_access_request(self, email: str, role: str) -> bool:
        """Aprova uma solicitação: adiciona o usuário e atualiza o status da solicitação."""
        requests_df = self.get_pending_access_requests()
        request_info = requests_df[requests_df['email'].str.lower() == email.lower()]

        if request_info.empty:
            logger.error(f"Tentativa de aprovar solicitação para {email}, mas não foi encontrada.")
            return False

        user_data = request_info.iloc[0]
        new_user = [user_data['email'], user_data['nome'], role, user_data['unidade_solicitada']]

        if not self.add_user(new_user):
            logger.error(f"Falha ao adicionar o usuário {email} após aprovação.")
            return False

        try:
            worksheet = self.sheet_ops.spreadsheet.worksheet("solicitacoes_acesso")
            cell = worksheet.find(email, in_column=1)
            if cell:
                worksheet.update_cell(cell.row, 5, 'aprovado')
                log_action("APPROVE_ACCESS_REQUEST", {"email": email, "assigned_role": role})
                st.cache_data.clear()
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao atualizar status da solicitação para {email}: {e}")
            return False

    # --- Métodos de Auditoria ---

    def get_audit_logs(self) -> pd.DataFrame:
        return self._get_df("log_auditoria")
