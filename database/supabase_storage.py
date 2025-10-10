import streamlit as st
import logging
import os
from io import BytesIO
from .supabase_config import get_supabase_client, PUBLIC_IMAGES_BUCKET, RESTRICTED_ATTACHMENTS_BUCKET, ACTION_EVIDENCE_BUCKET

logger = logging.getLogger('abrangencia_app.supabase_storage')

class SupabaseStorage:
    """
    Gerencia operações de upload e download de arquivos no Supabase Storage.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Criando instância única de SupabaseStorage")
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        try:
            self.client = get_supabase_client()
            logger.info("SupabaseStorage inicializado com sucesso")
        except Exception as e:
            logger.critical(f"Falha ao inicializar SupabaseStorage: {e}")
            self.client = None
        
        self._initialized = True

    def upload_file(self, bucket_name: str, file_obj, file_path: str, content_type: str = None) -> str | None:
        """
        Faz upload de um arquivo para o Supabase Storage.
        
        Args:
            bucket_name: Nome do bucket (public-images, restricted-attachments, etc)
            file_obj: Objeto do arquivo (UploadedFile do Streamlit ou BytesIO)
            file_path: Caminho/nome do arquivo no bucket
            content_type: MIME type do arquivo
        
        Returns:
            URL pública do arquivo ou None em caso de erro
        """
        if not self.client:
            logger.error("Cliente Supabase não disponível")
            return None

        try:
            # Obtém os bytes do arquivo
            if hasattr(file_obj, 'getvalue'):
                file_bytes = file_obj.getvalue()
            elif hasattr(file_obj, 'read'):
                file_bytes = file_obj.read()
            else:
                logger.error("Objeto de arquivo inválido")
                return None

            # Define o content-type se não fornecido
            if not content_type and hasattr(file_obj, 'type'):
                content_type = file_obj.type

            # Faz o upload
            logger.info(f"Fazendo upload para bucket '{bucket_name}': {file_path}")
            
            response = self.client.storage.from_(bucket_name).upload(
                path=file_path,
                file=file_bytes,
                file_options={"content-type": content_type} if content_type else None
            )

            # Gera a URL pública
            public_url = self.client.storage.from_(bucket_name).get_public_url(file_path)
            
            logger.info(f"Upload concluído: {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"Erro ao fazer upload para '{bucket_name}/{file_path}': {e}")
            return None

    def upload_public_image(self, file_obj, filename: str) -> str | None:
        """
        Upload de uma imagem pública (fotos de incidentes).
        """
        return self.upload_file(PUBLIC_IMAGES_BUCKET, file_obj, filename)

    def upload_restricted_attachment(self, file_obj, filename: str) -> str | None:
        """
        Upload de um anexo restrito (documentos de análise).
        """
        return self.upload_file(RESTRICTED_ATTACHMENTS_BUCKET, file_obj, filename)

    def upload_action_evidence(self, file_obj, filename: str) -> str | None:
        """
        Upload de evidência de ação (fotos/PDFs de conclusão).
        """
        return self.upload_file(ACTION_EVIDENCE_BUCKET, file_obj, filename)

    def delete_file(self, bucket_name: str, file_path: str) -> bool:
        """
        Deleta um arquivo do Supabase Storage.
        """
        if not self.client:
            return False

        try:
            logger.info(f"Deletando arquivo '{file_path}' do bucket '{bucket_name}'")
            self.client.storage.from_(bucket_name).remove([file_path])
            logger.info("Arquivo deletado com sucesso")
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar arquivo: {e}")
            return False

    def delete_file_by_url(self, file_url: str) -> bool:
        """
        Deleta um arquivo usando sua URL completa.
        Extrai o bucket e o caminho da URL.
        """
        if not file_url or not isinstance(file_url, str):
            return False

        try:
            # Parse da URL do Supabase Storage
            # Formato: https://PROJECT.supabase.co/storage/v1/object/public/BUCKET/PATH
            parts = file_url.split('/storage/v1/object/public/')
            if len(parts) != 2:
                logger.error(f"URL em formato inválido: {file_url}")
                return False

            bucket_and_path = parts[1].split('/', 1)
            if len(bucket_and_path) != 2:
                logger.error(f"Não foi possível extrair bucket e path da URL")
                return False

            bucket_name = bucket_and_path[0]
            file_path = bucket_and_path[1]

            return self.delete_file(bucket_name, file_path)

        except Exception as e:
            logger.error(f"Erro ao processar URL para deleção: {e}")
            return False

    def get_file_url(self, bucket_name: str, file_path: str) -> str:
        """
        Gera a URL pública de um arquivo.
        """
        if not self.client:
            return ""
        
        return self.client.storage.from_(bucket_name).get_public_url(file_path)

    def list_files(self, bucket_name: str, path: str = "") -> list:
        """
        Lista arquivos em um bucket/pasta.
        """
        if not self.client:
            return []

        try:
            files = self.client.storage.from_(bucket_name).list(path)
            return files
        except Exception as e:
            logger.error(f"Erro ao listar arquivos: {e}")
            return []
