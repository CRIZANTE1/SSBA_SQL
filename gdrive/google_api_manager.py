"""Light adapter that replaces Google API interactions with Supabase Storage.
This module exists to preserve the previous API surface while removing
dependencies on google-auth, gspread and googleapiclient.
"""

import logging
from database.supabase_storage import SupabaseStorage

logger = logging.getLogger('abrangencia_app.google_api_manager')


class GoogleApiManager:
    """Compatibility adapter — methods mirror the prior GoogleApiManager
    but use Supabase Storage where it makes sense. Functions that referred
    to spreadsheets return None or no-op, since the app now uses Postgres.
    """
    def __init__(self):
        self.storage = SupabaseStorage()

    def open_spreadsheet(self, spreadsheet_id: str):
        # Spreadsheets are now managed in the database. Keep compatibility.
        logger.info("open_spreadsheet() called but spreadsheets are managed by Supabase. Returning None.")
        return None

    def upload_file(self, folder_id: str, arquivo, novo_nome: str = None):
        # Map previous Drive uploads to restricted attachments in Supabase
        filename = novo_nome if novo_nome else getattr(arquivo, 'name', 'upload')
        url = self.storage.upload_restricted_attachment(arquivo, filename)
        return url

    def delete_file_by_url(self, file_url: str) -> bool:
        return self.storage.delete_file_by_url(file_url)

    def create_folder(self, name: str, parent_folder_id: str = None):
        logger.info("create_folder() no-op — Supabase Storage manages buckets/prefixes differently.")
        return None

    def create_spreadsheet(self, name: str, folder_id: str = None):
        logger.info("create_spreadsheet() no-op — spreadsheets are stored in Postgres now.")
        return None

    def setup_sheets_from_config(self, spreadsheet_id: str, config_path: str = "sheets_config.yaml"):
        logger.info("setup_sheets_from_config() no-op in migration adapter.")
        return False
