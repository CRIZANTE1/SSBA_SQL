import streamlit as st
import os
import tempfile
import yaml
import gspread
import logging 
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from .config import get_credentials_dict

# --- 2. Logger adicionado para consistência ---
logger = logging.getLogger('segsisone_app.google_api_manager')

class GoogleApiManager:
    def __init__(self):
        self.SCOPES = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        try:
            credentials_dict = get_credentials_dict()
            self.credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=self.SCOPES
            )
            self.drive_service = build('drive', 'v3', credentials=self.credentials, cache_discovery=False)
            self.sheets_service = build('sheets', 'v4', credentials=self.credentials, cache_discovery=False)
            self.gspread_client = gspread.authorize(self.credentials)
        except Exception as e:
            st.error(f"Erro crítico ao inicializar os serviços do Google: {str(e)}")
            raise

    def open_spreadsheet(self, spreadsheet_id: str):
        try:
            return self.gspread_client.open_by_key(spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f"A planilha com ID '{spreadsheet_id}' não foi encontrada.")
            return None
        except Exception as e:
            st.error(f"Erro ao abrir a planilha com gspread: {e}")
            return None

    # --- 3. Bloco de upload comentado foi REMOVIDO e a função principal foi mantida ---
    def upload_file(self, folder_id: str, arquivo, novo_nome: str = None):
        """Faz upload de um arquivo (UploadedFile do Streamlit) para uma pasta específica no Google Drive."""
        if not folder_id:
            st.error("Erro de programação: ID da pasta não foi fornecido para o upload.")
            return None
        
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(arquivo.name)[1]) as temp_file:
                temp_file.write(arquivo.getvalue())
                temp_file_path = temp_file.name

            file_metadata = {
                'name': novo_nome if novo_nome else arquivo.name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(temp_file_path, mimetype=arquivo.type, resumable=True)
            
            file = self.drive_service.files().create(
                body=file_metadata, media_body=media, fields='id,webViewLink'
            ).execute()
            
            return file.get('webViewLink')
        except Exception as e:
            if "HttpError 404" in str(e):
                st.error(f"Erro no upload: A pasta do Google Drive com ID '{folder_id}' não foi encontrada ou a conta de serviço não tem permissão.")
            else:
                st.error(f"Erro ao fazer upload do arquivo: {str(e)}")
            return None
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def create_folder(self, name: str, parent_folder_id: str = None):
        try:
            file_metadata = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
            if parent_folder_id:
                file_metadata['parents'] = [parent_folder_id]
            folder = self.drive_service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')
        except Exception as e:
            st.error(f"Erro ao criar pasta no Google Drive: {e}")
            return None

    def create_spreadsheet(self, name: str, folder_id: str = None):
        try:
            file_metadata = {'name': name, 'mimeType': 'application/vnd.google-apps.spreadsheet'}
            if folder_id:
                file_metadata['parents'] = [folder_id]
            spreadsheet_file = self.drive_service.files().create(body=file_metadata, fields='id').execute()
            return spreadsheet_file.get('id')
        except Exception as e:
            st.error(f"Erro ao criar nova planilha: {e}")
            return None

    def setup_sheets_from_config(self, spreadsheet_id: str, config_path: str = "sheets_config.yaml"):
        try:
            # Garante que o caminho para o YAML seja relativo ao script atual
            config_full_path = os.path.join(os.path.dirname(__file__), '..', config_path)
            with open(config_full_path, 'r', encoding='utf-8') as f:
                sheets_config = yaml.safe_load(f)

            spreadsheet = self.open_spreadsheet(spreadsheet_id)
            if not spreadsheet: return False
                
            default_sheet = spreadsheet.sheet1
            is_first = True
            for sheet_name, columns in sheets_config.items():
                if is_first:
                    worksheet = default_sheet
                    worksheet.update_title(sheet_name)
                    is_first = False
                else:
                    worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1", cols=len(columns))
                worksheet.update('A1', [columns])
            return True
        except Exception as e:
            st.error(f"Erro ao configurar as abas da nova planilha: {e}")
            return False
            
    def delete_file_by_url(self, file_url: str) -> bool:
        if not file_url or not isinstance(file_url, str):
            logger.warning("URL de arquivo inválida ou vazia fornecida para exclusão.")
            return False
        try:
            file_id = file_url.split('/d/')[1].split('/')[0]
        except IndexError:
            logger.error(f"URL do Google Drive em formato inválido: {file_url}")
            return False
        try:
            logger.info(f"Tentando deletar o arquivo com ID: {file_id}")
            self.drive_service.files().delete(fileId=file_id).execute()
            logger.info(f"Arquivo com ID {file_id} deletado com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar arquivo do Google Drive (ID: {file_id}): {e}")
            st.error(f"Erro ao deletar arquivo do Google Drive: {e}")
            return False
