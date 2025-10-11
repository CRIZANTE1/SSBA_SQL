import streamlit as st
import pandas as pd
from datetime import datetime
from database.supabase_config import get_database_engine, get_supabase_client
from sqlalchemy import text

def format_bytes(bytes_value):
    """Converte bytes para formato legível"""
    if bytes_value is None:
        return "N/A"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

def get_database_size():
    """Calcula o tamanho total do banco de dados"""
    try:
        engine = get_database_engine()
        with engine.connect() as conn:
            # <<< MUDANÇA: Usar pg_class ao invés de pg_tables >>>
            result = conn.execute(text("""
                SELECT 
                    n.nspname as schemaname,
                    c.relname as tablename,
                    pg_total_relation_size(c.oid) as size_bytes
                FROM pg_class c
                LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                  AND c.relkind = 'r'
                  AND n.nspname = 'public'
                ORDER BY size_bytes DESC
            """))
            
            tables = []
            total_size = 0
            
            for row in result:
                size_bytes = row.size_bytes
                total_size += size_bytes
                tables.append({
                    'Schema': row.schemaname,
                    'Tabela': row.tablename,
                    'Tamanho': format_bytes(size_bytes)
                })
            
            return total_size, pd.DataFrame(tables)
    except Exception as e:
        st.error(f"Erro ao obter tamanho do banco: {e}")
        return 0, pd.DataFrame()

def get_storage_usage():
    """Calcula uso de storage por bucket"""
    try:
        client = get_supabase_client()
        buckets = client.storage.list_buckets()
        
        bucket_usage = []
        total_storage = 0
        
        for bucket in buckets:
            bucket_name = bucket['name']
            
            try:
                files = client.storage.from_(bucket_name).list()
                
                bucket_size = 0
                file_count = 0
                
                for file_info in files:
                    # Metadata retorna o tamanho em bytes
                    if 'metadata' in file_info and 'size' in file_info['metadata']:
                        bucket_size += file_info['metadata']['size']
                    file_count += 1
                
                total_storage += bucket_size
                
                bucket_usage.append({
                    'Bucket': bucket_name,
                    'Arquivos': file_count,
                    'Tamanho': format_bytes(bucket_size),
                    'Público': '✅' if bucket.get('public', False) else '❌'
                })
            except Exception as e:
                bucket_usage.append({
                    'Bucket': bucket_name,
                    'Arquivos': 'Erro',
                    'Tamanho': 'N/A',
                    'Público': '❌'
                })
        
        return total_storage, pd.DataFrame(bucket_usage)
    except Exception as e:
        st.error(f"Erro ao obter uso de storage: {e}")
        return 0, pd.DataFrame()

def get_row_counts():
    """Conta linhas em cada tabela"""
    try:
        engine = get_database_engine()
        with engine.connect() as conn:
            # <<< MUDANÇA: Usar relname ao invés de tablename >>>
            result = conn.execute(text("""
                SELECT 
                    schemaname,
                    relname as tablename,
                    n_live_tup as row_count
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY n_live_tup DESC
            """))
            
            tables = []
            total_rows = 0
            
            for row in result:
                row_count = row.row_count or 0
                total_rows += row_count
                tables.append({
                    'Tabela': row.tablename,
                    'Linhas': f"{row_count:,}"
                })
            
            return total_rows, pd.DataFrame(tables)
    except Exception as e:
        st.error(f"Erro ao contar linhas: {e}")
        return 0, pd.DataFrame()

def display_supabase_monitor():
    """Renderiza a interface de monitoramento do Supabase"""
    st.header("📊 Monitoramento de Uso do Supabase")
    
    # Limites do Plano Free
    FREE_LIMITS = {
        'database_size': 500 * 1024 * 1024,  # 500 MB
        'storage_size': 1 * 1024 * 1024 * 1024,  # 1 GB
        'bandwidth': 2 * 1024 * 1024 * 1024,  # 2 GB/mês (egress)
        'rows': 500_000  # Sem limite oficial, mas após 500k pode degradar
    }
    
    st.info("**Plano Free do Supabase** - Limites mensais")
    
    # Calcula métricas
    with st.spinner("Coletando métricas..."):
        db_size, db_tables = get_database_size()
        storage_size, storage_buckets = get_storage_usage()
        total_rows, row_counts = get_row_counts()
    
    # === VISÃO GERAL ===
    st.subheader("📈 Visão Geral")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        db_percent = (db_size / FREE_LIMITS['database_size']) * 100
        st.metric(
            "💾 Banco de Dados",
            format_bytes(db_size),
            f"{db_percent:.1f}% de 500 MB"
        )
        st.progress(min(db_percent / 100, 1.0))
        
        if db_percent > 80:
            st.error("⚠️ Banco de dados acima de 80% do limite!")
        elif db_percent > 60:
            st.warning("⚠️ Banco de dados acima de 60% do limite.")
    
    with col2:
        storage_percent = (storage_size / FREE_LIMITS['storage_size']) * 100
        st.metric(
            "📦 Storage",
            format_bytes(storage_size),
            f"{storage_percent:.1f}% de 1 GB"
        )
        st.progress(min(storage_percent / 100, 1.0))
        
        if storage_percent > 80:
            st.error("⚠️ Storage acima de 80% do limite!")
        elif storage_percent > 60:
            st.warning("⚠️ Storage acima de 60% do limite.")
    
    with col3:
        rows_percent = (total_rows / FREE_LIMITS['rows']) * 100
        st.metric(
            "📊 Total de Linhas",
            f"{total_rows:,}",
            f"{rows_percent:.1f}% de 500k"
        )
        st.progress(min(rows_percent / 100, 1.0))
        
        if rows_percent > 80:
            st.warning("⚠️ Muitas linhas no banco!")
    
    st.divider()
    
    # === DETALHES DO BANCO ===
    with st.expander("💾 Detalhes do Banco de Dados", expanded=False):
        if not db_tables.empty:
            st.dataframe(db_tables, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma tabela encontrada.")
    
    # === DETALHES DO STORAGE ===
    with st.expander("📦 Detalhes do Storage", expanded=False):
        if not storage_buckets.empty:
            st.dataframe(storage_buckets, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum bucket encontrado.")
    
    # === CONTAGEM DE LINHAS ===
    with st.expander("📊 Contagem de Linhas por Tabela", expanded=False):
        if not row_counts.empty:
            st.dataframe(row_counts, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma tabela encontrada.")
    
    st.divider()
    
    # === AÇÕES DE LIMPEZA ===
    st.subheader("🧹 Ações de Manutenção")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Limpar Logs Antigos**")
        st.caption("Remove logs de auditoria com mais de 30 dias")
        
        if st.button("🗑️ Limpar Logs", type="secondary"):
            try:
                engine = get_database_engine()
                with engine.connect() as conn:
                    result = conn.execute(text("""
                        DELETE FROM log_auditoria 
                        WHERE timestamp < NOW() - INTERVAL '30 days'
                        RETURNING id
                    """))
                    deleted = result.rowcount
                    conn.commit()
                
                st.success(f"✅ {deleted} logs removidos!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao limpar logs: {e}")
    
    with col2:
        st.markdown("**Vacuum do Banco**")
        st.caption("Otimiza e recupera espaço do banco")
        st.info("💡 Execute via Dashboard do Supabase:\nSettings > Database > Vacuum")
    
    # === RECOMENDAÇÕES ===
    st.divider()
    st.subheader("💡 Recomendações")
    
    recommendations = []
    
    if db_percent > 70:
        recommendations.append("- 🔴 Considere fazer limpeza de dados antigos ou migrar para plano pago")
    
    if storage_percent > 70:
        recommendations.append("- 🔴 Considere comprimir imagens ou remover arquivos antigos")
    
    if total_rows > 400_000:
        recommendations.append("- ⚠️ Considere arquivar dados históricos em outra tabela")
    
    if not recommendations:
        st.success("✅ Seu uso está dentro dos limites saudáveis!")
    else:
        for rec in recommendations:
            st.warning(rec)
    
    # === INFORMAÇÕES ADICIONAIS ===
    with st.expander("ℹ️ Sobre os Limites do Plano Free"):
        st.markdown("""
        **Limites do Supabase Free Tier:**
        
        - 💾 **Banco de Dados:** 500 MB
        - 📦 **Storage:** 1 GB (total de arquivos)
        - 🌐 **Bandwidth:** 2 GB/mês (egress/download)
        - 🔐 **Autenticação:** 50,000 usuários ativos/mês
        - ⚡ **Edge Functions:** 500,000 invocações/mês
        - 📊 **Realtime:** 200 conexões simultâneas
        
        **Dicas para otimizar:**
        1. Comprima imagens antes de fazer upload
        2. Delete logs antigos regularmente
        3. Use cache no frontend quando possível
        4. Monitore este dashboard semanalmente
        
        [📚 Documentação Oficial](https://supabase.com/pricing)
        """)
    
    st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
