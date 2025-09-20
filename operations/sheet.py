# operations/sheet.py

import streamlit as st
import pandas as pd
import logging
import random
import gspread
from gspread.exceptions import WorksheetNotFound
from gdrive.google_api_manager import GoogleApiManager
from gdrive.config import SPREADSHEET_ID # Importa o ID da planilha principal

logger = logging.getLogger('abrangencia_app.sheet_operations')

class SheetOperations:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Criando uma nova instância de SheetOperations (Singleton).")
            cls._instance = super(SheetOperations, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        logger.info("Inicializando a conexão com o Google Sheets...")
        if not SPREADSHEET_ID:
            st.error("ID da Planilha Principal não configurado. Verifique seu arquivo secrets.toml.")
            self.spreadsheet = None
            self._initialized = True
            return

        try:
            api_manager = GoogleApiManager()
            self.spreadsheet = api_manager.open_spreadsheet(SPREADSHEET_ID)
            if self.spreadsheet:
                logger.info(f"Conectado com sucesso à planilha: '{self.spreadsheet.title}'")
        except Exception as e:
            st.error(f"Erro inesperado durante a inicialização da conexão com a planilha: {e}")
            self.spreadsheet = None

        self._initialized = True

    def _get_worksheet(self, aba_name: str) -> gspread.Worksheet | None:
        if not self.spreadsheet:
            logger.warning(f"Tentativa de acessar a aba '{aba_name}' mas a planilha não está conectada.")
            return None
        try:
            return self.spreadsheet.worksheet(aba_name)
        except WorksheetNotFound:
            logger.warning(f"A aba '{aba_name}' não foi encontrada na planilha '{self.spreadsheet.title}'.")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao acessar a aba '{aba_name}': {e}", exc_info=True)
            return None

    @st.cache_data(ttl=60)
    def carregar_dados_aba(_self, aba_name: str) -> list | None:
        worksheet = _self._get_worksheet(aba_name)
        if not worksheet: return None
        try:
            return worksheet.get_all_values()
        except Exception as e:
            logger.error(f"Erro ao ler dados da aba '{aba_name}': {e}", exc_info=True)
            return None
            
    def get_df_from_worksheet(self, aba_name: str) -> pd.DataFrame:
        data = self.carregar_dados_aba(aba_name)
        if data and len(data) > 1:
            return pd.DataFrame(data[1:], columns=data[0])
        return pd.DataFrame()

    def adc_dados_aba(self, aba_name: str, new_data: list) -> int | None:
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return None
        try:
            existing_ids = worksheet.col_values(1)[1:]
            while True:
                new_id = random.randint(10000, 99999)
                if str(new_id) not in existing_ids: break
            full_row_to_add = [new_id] + new_data
            worksheet.append_row(full_row_to_add, value_input_option='USER_ENTERED')
            st.cache_data.clear()
            return new_id
        except Exception as e:
            logger.error(f"Erro ao adicionar dados na aba '{aba_name}': {e}", exc_info=True)
            return None

    def adc_dados_aba_em_lote(self, aba_name: str, new_data_list: list) -> bool:
        worksheet = self._get_worksheet(aba_name)
        if not worksheet or not new_data_list: return False
        try:
            rows_to_append = []
            existing_ids = worksheet.col_values(1)[1:]
            for row_data in new_data_list:
                while True:
                    new_id = random.randint(10000, 99999)
                    if str(new_id) not in existing_ids:
                        existing_ids.append(str(new_id))
                        break
                rows_to_append.append([new_id] + row_data)
            worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            st.cache_data.clear()
            return True
        except Exception as e:
            logger.error(f"Erro ao adicionar dados em lote na aba '{aba_name}': {e}", exc_info=True)
            return False

    def update_row_by_id(self, aba_name: str, row_id: str, new_values_dict: dict) -> bool:
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return False
        try:
            header = worksheet.row_values(1)
            id_column_data = worksheet.col_values(1)
            if str(row_id) not in id_column_data: return False
            row_number = id_column_data.index(str(row_id)) + 1
            cells_to_update = []
            for col_name, new_value in new_values_dict.items():
                if col_name in header:
                    col_index = header.index(col_name) + 1
                    cells_to_update.append(gspread.Cell(row_number, col_index, str(new_value)))
            if cells_to_update:
                worksheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
                st.cache_data.clear()
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar linha na aba '{aba_name}': {e}", exc_info=True)
            return False

    # --- MÉTODOS RESTAURADOS ---
    def adc_linha_simples(self, aba_name: str, new_data_row: list) -> bool:
        """
        Adiciona uma única linha de dados a uma aba, sem gerar ou manipular IDs.
        Ideal para abas como 'usuarios'.
        """
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return False
        try:
            worksheet.append_row(new_data_row, value_input_option='USER_ENTERED')
            st.cache_data.clear()
            logger.info(f"Linha adicionada com sucesso na aba '{aba_name}'.")
            return True
        except Exception as e:
            logger.error(f"Erro ao adicionar linha na aba '{aba_name}': {e}", exc_info=True)
            return False

    def excluir_linha_por_indice(self, aba_name: str, row_index: int) -> bool:
        """Exclui uma linha de uma aba pelo seu número de índice."""
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return False
        try:
            worksheet.delete_rows(row_index)
            st.cache_data.clear()
            logger.info(f"Linha {row_index} da aba '{aba_name}' excluída com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao excluir linha {row_index} da aba '{aba_name}': {e}", exc_info=True)
            return False
