import streamlit as st
import pandas as pd
from datetime import datetime
from auth.auth_utils import check_permission, get_user_role
from operations.incident_manager import get_incident_manager
from operations.audit_logger import log_action

@st.cache_data(ttl=120)
def load_action_plan_data():
    """
    Carrega e une os dados do plano de ação com as descrições das ações de bloqueio.
    Esta função é cacheada para melhorar o desempenho.
    """
    incident_manager = get_incident_manager()
    action_plan_df = incident_manager.get_all_action_plans()
    blocking_actions_df = incident_manager.get_all_blocking_actions()

    if action_plan_df.empty:
        return pd.DataFrame()

    # Une os dataframes para obter a descrição da ação
    if not blocking_actions_df.empty:
        merged_df = pd.merge(
            action_plan_df,
            blocking_actions_df[['id', 'descricao_acao']],
            left_on='id_acao_bloqueio',
            right_on='id',
            how='left',
            suffixes=('_plan', '_action')
        ).rename(columns={'id_plan': 'id'})
        
        # Garante que não haja colunas de ID duplicadas ou confusas
        if 'id_action' in merged_df.columns:
            merged_df = merged_df.drop(columns=['id_action'])
            
        merged_df['descricao_acao'].fillna('Descrição da ação original não encontrada', inplace=True)
    else:
        merged_df = action_plan_df
        merged_df['descricao_acao'] = "Descrição indisponível (falha ao carregar ações de bloqueio)"

    return merged_df

def show_plano_acao_page():
    """
    Renderiza a página do Plano de Ação de Abrangência.
    """
    st.title("📋 Plano de Ação de Abrangência")
    check_permission(level='viewer')

    try:
        full_action_plan_df = load_action_plan_data()
    except Exception as e:
        st.error(f"Falha ao carregar os dados da planilha: {e}")
        st.stop()

    if full_action_plan_df.empty:
        st.success("🎉 Nenhum item no plano de ação de abrangência no momento.")
        st.stop()

    # --- Filtros de Visualização ---
    st.subheader("Filtros de Visualização")
    
    # Filtro por Unidade Operacional
    unit_options = ["Todas"] + sorted(full_action_plan_df['unidade_operacional'].unique().tolist())
    
    # Pre-seleciona a unidade do usuário, se não for admin
    user_unit = st.session_state.get('unit_name', 'Global')
    default_index = 0
    if user_unit != 'Global' and user_unit in unit_options:
        default_index = unit_options.index(user_unit)
    
    selected_unit = st.selectbox(
        "Selecione a Unidade Operacional para visualizar:", 
        options=unit_options,
        index=default_index
    )

    # Aplica o filtro
    if selected_unit != "Todas":
        filtered_df = full_action_plan_df[full_action_plan_df['unidade_operacional'] == selected_unit].copy()
    else:
        filtered_df = full_action_plan_df.copy()
        
    if filtered_df.empty:
        st.info(f"Nenhum item no plano de ação para a unidade '{selected_unit}'.")
        st.stop()
        
    st.divider()

    # --- Exibição e Edição com st.data_editor ---
    
    # Determina se a edição é permitida
    is_editor_or_admin = get_user_role() in ['editor', 'admin']
    if is_editor_or_admin:
        st.info("Você pode editar o **Status** diretamente na tabela abaixo. As alterações são salvas automaticamente.")
    else:
        st.info("Visualização em modo somente leitura.")

    # Armazena o dataframe filtrado no estado da sessão para comparação
    if 'original_df_view' not in st.session_state or not filtered_df.equals(st.session_state.get('edited_df_view')):
        st.session_state.original_df_view = filtered_df.copy()

    edited_df = st.data_editor(
        filtered_df,
        column_config={
            "id": None, 
            "id_acao_bloqueio": None,
            "unidade_operacional": st.column_config.TextColumn("Unidade", disabled=True),
            "descricao_acao": st.column_config.TextColumn("Ação de Abrangência", help="A ação a ser implementada", disabled=True, width="large"),
            "responsavel_email": st.column_config.TextColumn("Responsável", disabled=True),
            "prazo_inicial": st.column_config.DateColumn("Prazo", disabled=True, format="DD/MM/YYYY"),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=["Pendente", "Em Andamento", "Concluído", "Cancelado"],
                required=True,
                disabled=not is_editor_or_admin
            ),
            "data_conclusao": st.column_config.TextColumn("Data de Conclusão", disabled=True)
        },
        column_order=["unidade_operacional", "descricao_acao", "responsavel_email", "prazo_inicial", "status", "data_conclusao"],
        width='stretch',
        hide_index=True,
        key="action_plan_editor"
    )
    st.session_state.edited_df_view = edited_df.copy()

    # --- Lógica para Salvar Alterações ---
    if is_editor_or_admin:
        original_df = st.session_state.original_df_view

        # Compara o dataframe editado com o original para encontrar mudanças
        if not edited_df.equals(original_df):
            with st.spinner("Salvando alterações..."):
                try:
                    # `compare` retorna um dataframe com as diferenças
                    changes = original_df.compare(edited_df, keep_shape=True, keep_equal=False)
                    
                    # Itera sobre as linhas que tiveram alguma alteração
                    for index in changes.dropna(how='all').index:
                        action_id = original_df.loc[index, 'id']
                        
                        # Verifica se a coluna 'status' foi alterada
                        if pd.notna(changes.loc[index, ('status', 'self')]):
                            old_status = changes.loc[index, ('status', 'self')]
                            new_status = changes.loc[index, ('status', 'other')]
                            
                            updates = {"status": new_status}
                            # Se a ação foi concluída, adiciona a data de conclusão
                            if new_status == "Concluído":
                                updates["data_conclusao"] = datetime.now().strftime("%d/%m/%Y")
                            
                            incident_manager = get_incident_manager()
                            success = incident_manager.update_abrangencia_action(action_id, updates)
                            
                            if success:
                                st.toast(f"Status da ação atualizado para '{new_status}'.")
                                log_action("UPDATE_ACTION_PLAN_STATUS", {"plan_id": action_id, "old": old_status, "new": new_status})
                            else:
                                st.error(f"Falha ao atualizar o status da ação ID {action_id}.")
                    
                    # Limpa caches e recarrega a página para refletir as mudanças
                    st.cache_data.clear()
                    # Atualiza o dataframe original no estado da sessão para evitar reruns em loop
                    st.session_state.original_df_view = edited_df.copy()
                    st.rerun()

                except Exception as e:
                    st.error(f"Ocorreu um erro ao tentar salvar as alterações: {e}")
