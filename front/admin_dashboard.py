
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

# Constante de Configuração do Prazo
PRAZO_ANALISE_DIAS = 30

@st.cache_data(ttl=300)
def load_comprehensive_admin_data():
    """
    Carrega e processa todos os dados, calculando as duas categorias de pendências:
    1. Análises não iniciadas e vencidas.
    2. Ações de planos de ação com prazo vencido.
    """
    from operations.incident_manager import get_incident_manager
    from gdrive.matrix_manager import get_matrix_manager

    incident_manager = get_incident_manager()
    matrix_manager = get_matrix_manager()

    all_incidents_df = incident_manager.get_all_incidents()
    all_actions_df = incident_manager.get_all_action_plans()
    all_units = matrix_manager.get_all_units()
    
    blocking_actions_df = incident_manager.get_all_blocking_actions()
    if not all_actions_df.empty and not blocking_actions_df.empty:
        all_actions_df = pd.merge(
            all_actions_df,
            blocking_actions_df[['id', 'descricao_acao']],
            left_on='id_acao_bloqueio', right_on='id', how='left'
        )
    else:
        all_actions_df['descricao_acao'] = "N/A"
    all_actions_df['descricao_acao'] = all_actions_df['descricao_acao'].fillna("N/A")

    uninitiated_analyses_list = []
    overdue_actions_df = pd.DataFrame()

    if not all_incidents_df.empty and all_units:
        all_incidents_df['data_evento_dt'] = pd.to_datetime(all_incidents_df['data_evento'], format="%d/%m/%Y", errors='coerce')
        deadline_for_analysis = date.today() - timedelta(days=PRAZO_ANALISE_DIAS)
        
        units_who_analyzed_by_incident = {}
        if not all_actions_df.empty:
            actions_with_incident_id = pd.merge(
                all_actions_df, 
                blocking_actions_df[['id', 'id_incidente']], 
                left_on='id_acao_bloqueio', right_on='id', how='left'
            )
            grouped = actions_with_incident_id.groupby('id_incidente')['unidade_operacional'].unique()
            units_who_analyzed_by_incident = {index: set(values) for index, values in grouped.items()}

        set_all_units = set(all_units)
        
        for _, incident in all_incidents_df.iterrows():
            incident_date = incident['data_evento_dt']
            if pd.notna(incident_date) and incident_date.date() < deadline_for_analysis:
                units_that_analyzed = units_who_analyzed_by_incident.get(incident['id'], set())
                pending_units = set_all_units - units_that_analyzed
                if pending_units:
                    uninitiated_analyses_list.append({
                        "Incidente": incident['evento_resumo'],
                        "Data do Incidente": incident['data_evento'],
                        "UOs Pendentes": ", ".join(sorted(list(pending_units))),
                        "count": len(pending_units),
                        "unidades": list(pending_units)
                    })

        if not all_actions_df.empty:
            pending_execution = all_actions_df[~all_actions_df['status'].str.lower().isin(['concluído', 'cancelado'])].copy()
            if not pending_execution.empty:
                pending_execution['prazo_dt'] = pd.to_datetime(pending_execution['prazo_inicial'], format="%d/%m/%Y", errors='coerce')
                overdue_actions_df = pending_execution.dropna(subset=['prazo_dt'])[pending_execution['prazo_dt'].dt.date < date.today()]

    # <<< ESTA É A CORREÇÃO CRÍTICA >>>
    # Define as colunas esperadas ao criar o DataFrame.
    # Se a lista estiver vazia, ele cria um DataFrame vazio com estas colunas, evitando o KeyError.
    expected_cols = ["Incidente", "Data do Incidente", "UOs Pendentes", "count", "unidades"]
    uninitiated_analyses_df = pd.DataFrame(uninitiated_analyses_list, columns=expected_cols)
    
    return uninitiated_analyses_df, overdue_actions_df, all_incidents_df, all_units

def display_admin_summary_dashboard():
    st.header("Dashboard de Resumo Executivo Global")
    
    uninitiated_df, overdue_df, incidents_df, units_list = load_comprehensive_admin_data()

    if not units_list:
        st.info("Nenhuma unidade operacional encontrada. Cadastre usuários e associe-os a unidades.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Unidades Operacionais", len(units_list))
    col2.metric("Total de Incidentes Globais", len(incidents_df))
    col3.metric("Incidentes com Análises Atrasadas", len(uninitiated_df))
    st.divider()

    st.subheader(f"🚨 Análises de Abrangência Atrasadas (Prazo > {PRAZO_ANALISE_DIAS} dias)")
    if uninitiated_df.empty:
        st.success("✅ Todas as unidades estão em dia com o início das análises de abrangência.")
    else:
        st.error(f"Existem {len(uninitiated_df)} incidentes com análises não iniciadas por uma ou mais UOs.", icon="🚨")
        st.dataframe(
            uninitiated_df[['Incidente', 'Data do Incidente', 'UOs Pendentes']],
            width='stretch', hide_index=True
        )
    st.divider()

    st.subheader("⚠️ Ações de Abrangência com Prazo de Execução Vencido")
    if overdue_df.empty:
        st.success("✅ Nenhuma ação de execução com prazo vencido.")
    else:
        st.warning(f"Existem {len(overdue_df)} ações individuais com prazo de execução vencido.", icon="⚠️")
        st.dataframe(
            overdue_df[['unidade_operacional', 'descricao_acao', 'responsavel_email', 'prazo_inicial']].rename(columns={
                'unidade_operacional': 'UO', 'descricao_acao': 'Ação',
                'responsavel_email': 'Responsável', 'prazo_inicial': 'Prazo Vencido'
            }),
            width='stretch', hide_index=True
        )
    st.divider()
    
    st.subheader("Gráfico Consolidado de Pendências por Unidade")
    
    uninitiated_counts = pd.Series(dtype=int)
    if not uninitiated_df.empty:
        uninitiated_counts = uninitiated_df.explode('unidades').groupby('unidades').size().rename("Análises Atrasadas")
    
    overdue_action_counts = pd.Series(dtype=int)
    if not overdue_df.empty:
        overdue_action_counts = overdue_df.groupby('unidade_operacional').size().rename("Ações Vencidas")
    
    df_consolidated = pd.concat([uninitiated_counts, overdue_action_counts], axis=1).fillna(0).astype(int)
    
    if df_consolidated.empty or df_consolidated.sum().sum() == 0:
        st.info("Nenhuma pendência encontrada para gerar o gráfico.")
    else:
        df_consolidated = df_consolidated[df_consolidated.sum(axis=1) > 0]
        st.bar_chart(df_consolidated)
        
        df_consolidated['Total'] = df_consolidated.sum(axis=1)
        most_critical_unit = df_consolidated['Total'].idxmax()
        
        with st.expander(f"🔍 Detalhes da Unidade Mais Crítica: {most_critical_unit}"):
            st.write(f"**Análises Não Iniciadas Atrasadas ({int(df_consolidated.loc[most_critical_unit, 'Análises Atrasadas'])}):**")
            critical_uninitiated = uninitiated_df[uninitiated_df['unidades'].apply(lambda x: most_critical_unit in x)]
            if not critical_uninitiated.empty:
                st.table(critical_uninitiated[['Incidente', 'Data do Incidente']])
            else:
                st.write("Nenhuma.")

            st.write(f"**Ações com Execução Vencida ({int(df_consolidated.loc[most_critical_unit, 'Ações Vencidas'])}):**")
            critical_overdue = overdue_df[overdue_df['unidade_operacional'] == most_critical_unit]
            if not critical_overdue.empty:
                st.table(critical_overdue[['descricao_acao', 'responsavel_email', 'prazo_inicial']])
            else:
                st.write("Nenhuma.")
