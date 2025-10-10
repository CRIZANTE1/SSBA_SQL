"""Adapter module to provide a backward-compatible SheetOperations
interface while the project migrates from Google Sheets to Supabase.
This file intentionally avoids importing any Google libraries.
"""

import streamlit as st
import pandas as pd
import logging
from database.supabase_operations import SupabaseOperations

logger = logging.getLogger('abrangencia_app.sheet_operations')


class SheetOperations:
    """Thin adapter that maps older sheet-like methods to SupabaseOperations.
    This keeps existing call sites working while removing google deps.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Criando instância única de SheetOperations (adapter).")
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.ops = SupabaseOperations()
        self._initialized = True

    @st.cache_data(ttl=60)
    def carregar_dados_aba(self, aba_name: str) -> list | None:
        df = self.ops.get_table_data(aba_name)
        if df is None or df.empty:
            return None
        # Convert DataFrame to list of rows with header as first row to mimic gspread
        header = df.columns.tolist()
        rows = df.fillna('').astype(str).values.tolist()
        return [header] + rows

    def get_df_from_worksheet(self, aba_name: str) -> pd.DataFrame:
        return self.ops.get_table_data(aba_name)

    def adc_dados_aba(self, aba_name: str, new_data: list) -> int | None:
        # new_data is a list (row) without id — create a dict by mapping header if possible
        # We expect the caller to pass lists matching the table columns order; best-effort: insert as a JSONB payload
        try:
            # If table has columns, attempt to match; otherwise insert as generic row
            df = self.ops.get_table_data(aba_name)
            if df is None or df.empty:
                # Insert into table as a single column 'payload' if exists
                payload = {"payload": str(new_data)}
                row = self.ops.insert_row(aba_name, payload)
            else:
                cols = df.columns.tolist()
                # skip id column if present
                if 'id' in cols and len(new_data) == len(cols) - 1:
                    cols = [c for c in cols if c != 'id']
                if len(cols) != len(new_data):
                    # fallback: attempt to insert by using remaining columns as keys
                    row = self.ops.insert_row(aba_name, {f'col_{i}': v for i, v in enumerate(new_data)})
                else:
                    data = {col: val for col, val in zip(cols, new_data)}
                    row = self.ops.insert_row(aba_name, data)
            return int(row.get('id')) if row and row.get('id') else None
        except Exception:
            logger.exception("Falha ao adicionar dados na tabela %s", aba_name)
            return None

    def adc_dados_aba_em_lote(self, aba_name: str, new_data_list: list) -> bool:
        try:
            # Attempt batch insert if list of dicts provided
            if not new_data_list:
                return False
            if isinstance(new_data_list[0], dict):
                return self.ops.insert_batch(aba_name, new_data_list)
            # Otherwise, map to dicts using table columns
            df = self.ops.get_table_data(aba_name)
            cols = df.columns.tolist() if df is not None else []
            mapped = []
            for row in new_data_list:
                if len(cols) and len(row) == len(cols):
                    mapped.append({col: val for col, val in zip(cols, row)})
                else:
                    mapped.append({f'col_{i}': v for i, v in enumerate(row)})
            return self.ops.insert_batch(aba_name, mapped)
        except Exception:
            logger.exception("Falha ao inserir lote na tabela %s", aba_name)
            return False

    def update_row_by_id(self, aba_name: str, row_id: str, new_values_dict: dict) -> bool:
        try:
            return self.ops.update_row(aba_name, int(row_id), new_values_dict)
        except Exception:
            logger.exception("Falha ao atualizar linha %s na tabela %s", row_id, aba_name)
            return False

    def adc_linha_simples(self, aba_name: str, new_data_row: list) -> bool:
        # map to insert_row using table columns when possible
        try:
            df = self.ops.get_table_data(aba_name)
            cols = df.columns.tolist() if df is not None else []
            if cols and len(new_data_row) == len(cols):
                data = {col: val for col, val in zip(cols, new_data_row)}
            else:
                data = {f'col_{i}': v for i, v in enumerate(new_data_row)}
            row = self.ops.insert_row(aba_name, data)
            return bool(row)
        except Exception:
            logger.exception("Falha ao adicionar linha simples na tabela %s", aba_name)
            return False

    def excluir_linha_por_indice(self, aba_name: str, row_index: int) -> bool:
        try:
            return self.ops.delete_row(aba_name, int(row_index))
        except Exception:
            logger.exception("Falha ao excluir linha %s na tabela %s", row_index, aba_name)
            return False
