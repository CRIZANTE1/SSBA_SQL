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
    Gerencia os dados de controle da Planilha Principal: usuários, lista de unidades
    operacionais e logs de auditoria.
    """
    def __init__(self):
        """
        Inicializa o gerenciador, utilizando a conexão Singleton de SheetOperations.
        """
        self.sheet_ops = SheetOperations()
        if not self.sheet_ops.spreadsheet:
            raise ConnectionError("Falha na conexão com a Planilha Principal.")

    @st.cache_data(ttl=300)
    def _get_df(_self, sheet_name: str) -> pd.DataFrame:
        """
        Função interna genérica para carregar e cachear DataFrames de abas específicas.
        O `_self` é uma convenção para métodos em cache dentro de classes.
        """
        logger.info(f"Carregando dados da aba '{sheet_name}' (pode usar cache)...")
        return _self.sheet_ops.get_df_from_worksheet(sheet_name)

    # --- Métodos de Usuários ---

    def get_all_users_df(self) -> pd.DataFrame:
        """Retorna um DataFrame com todos os usuários do sistema."""
        return self._get_df("usuarios")

    def get_user_info(self, email: str) -> dict | None:
        """Busca as informações de um usuário específico pelo e-mail."""
        users_df = self.get_all_users_df()
        if users_df.empty or 'email' not in users_df.columns:
            return None
        
        user_info = users_df[users_df['email'].str.lower().str.strip() == email.lower().strip()]
        return user_info.iloc[0].to_dict() if not user_info.empty else None

    def add_user(self, user_data: list) -> bool:
        """
        Adiciona um novo usuário à aba 'usuarios'.
        Args:
            user_data (list): Uma lista na ordem das colunas, ex: [email, nome, role, unidade_associada]
        """
        logger.info(f"Adicionando novo usuário: {user_data[0]}")
        success = self.sheet_ops.adc_linha_simples("usuarios", user_data)
        if success:
            log_action("ADD_USER", {"email": user_data[0], "role": user_data[2]})
            st.cache_data.clear() # Limpa todo o cache para garantir consistência
        return success

    def update_user(self, email: str, updates: dict) -> bool:
        """
        Atualiza os dados de um usuário existente, localizando-o pelo e-mail.
        Este método é mais robusto do que depender do índice da linha.
        """
        logger.info(f"Tentando atualizar usuário '{email}' com dados: {updates}")
        try:
            worksheet = self.sheet_ops.spreadsheet.worksheet("usuarios")
            cell = worksheet.find(email, in_column=1) # Procura o e-mail na primeira coluna
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
                else:
                    logger.warning(f"Coluna '{col_name}' não encontrada no cabeçalho da aba 'usuarios'.")

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
        """Remove um usuário da planilha localizando a linha pelo e-mail."""
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

    # --- Métodos de Unidades Operacionais ---

    def get_all_units(self) -> list[str]:
        """Retorna uma lista com os nomes de todas as unidades operacionais cadastradas."""
        units_df = self._get_df("unidades_operacionais")
        if units_df.empty or 'nome_unidade' not in units_df.columns:
            return []
        return sorted(units_df['nome_unidade'].dropna().unique().tolist())

    def add_unit(self, unit_name: str) -> bool:
        """Adiciona o nome de uma nova unidade operacional à lista central."""
        logger.info(f"Adicionando nova unidade: {unit_name}")
        success = self.sheet_ops.adc_linha_simples("unidades_operacionais", [unit_name])
        if success:
            log_action("ADD_UNIT", {"unit_name": unit_name})
            st.cache_data.clear()
        return success

    # --- Métodos de Auditoria ---

    def get_audit_logs(self) -> pd.DataFrame:
        """Retorna um DataFrame com todos os logs de auditoria do sistema."""
        return self._get_df("log_auditoria")
