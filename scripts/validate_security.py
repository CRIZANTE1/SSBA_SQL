"""
Script para validar configurações de segurança do banco de dados.
Verifica a existência de funções auxiliares essenciais no schema 'app'.
"""

from sqlalchemy import text
from database.supabase_config import get_database_engine

def check_functions():
    """Verifica se as funções auxiliares existem"""
    print("\n" + "=" * 60)
    print("VERIFICANDO FUNÇÕES AUXILIARES")
    print("=" * 60)
    
    engine = get_database_engine()
    
    required_functions = [
        'get_user_email',
        'get_user_role',
        'get_user_unit',
        'is_admin',
        'can_edit',
        'belongs_to_unit'
    ]
    
    with engine.connect() as conn:
        all_exist = True
        for func in required_functions:
            result = conn.execute(text(f"""
                SELECT EXISTS(
                    SELECT 1 
                    FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE n.nspname = 'app' 
                      AND p.proname = '{func}'
                )
            """))
            exists = result.scalar()
            status = "✅ EXISTE" if exists else "❌ NÃO EXISTE"
            print(f"app.{func}(): {status}")
            if not exists:
                all_exist = False
        
        return all_exist

if __name__ == '__main__':
    success = check_functions()
    exit(0 if success else 1)