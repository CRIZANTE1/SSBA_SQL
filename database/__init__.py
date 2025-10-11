from .supabase_config import get_supabase_client, get_supabase_credentials, get_supabase_admin_client
from .supabase_operations import SupabaseOperations
from .supabase_storage import SupabaseStorage
from .matrix_manager import MatrixManager, get_matrix_manager

__all__ = [
    'get_supabase_client',
    'get_supabase_credentials',
    'get_supabase_admin_client',  # <<< ADICIONE ESTA LINHA
    'SupabaseOperations',
    'SupabaseStorage',
    'MatrixManager',
    'get_matrix_manager'
]
