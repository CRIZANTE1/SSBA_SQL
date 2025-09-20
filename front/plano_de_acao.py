
import streamlit as st
import pandas as pd
from datetime import datetime
from auth.auth_utils import check_permission
from operations.incident_manager import IncidentManager

# --- FUNÇÃO DE INICIALIZAÇÃO SINGLE-TENANT ---
@st.cache_resource
def get_incident_manager():
    """Garante que o IncidentManager seja instanciado apenas uma vez por sessão."""
    return IncidentManager()

def show_plano_acao_page():
    """
    Renderiza a página do Plano de Ação de Abrangência para o ambiente single-tenant.
    """
    st.title("📋 Plano de Ação de Abrangência")

    if not check_permission(level='viewer'):
        st.stop()

    # Usa a função cacheada para obter a instância única do manager
    incident_manager = get_incident_manager()

    # --- CARREGAMENTO E JUNÇÃO DOS DADOS ---
    @st.cache_data(ttl=60)
    def load_action_plan_data():
        """Carrega os dados do plano de ação e as descrições das ações de bloqueio."""
        action_plan_df = incident_manager.sheet_ops.get_df_from_worksheet("plano_de_acao_abrangencia")
        blocking_actions_df = incident_manager.sheet_ops.get_df_from_worksheet("acoes_bloqueio")
        return action_plan_df, blocking_actions_df

    try:
        action_plan_df, blocking_actions_df = load_action_plan_data()
    except Exception as e:
        st.error(f"Falha ao carregar os dados da planilha: {e}")
        st.stop()

    if action_plan_df.empty:
        st.success("🎉 Nenhum item no plano de ação de abrangência.")
        st.stop()

    if blocking_actions_df.empty:
        st.warning("Não foi possível carregar as descrições das ações de bloqueio da planilha central.")
        merged_df = action_plan_df
        merged_df['descricao_acao'] = "Descrição não encontrada"
    else:
        merged_df = pd.merge(
            action_plan_df,
            blocking_actions_df[['id', 'descricao_acao']],
            left_on='id_acao_bloqueio',
            right_on='id',
            how='left'
        ).drop(columns=['id_y']).rename(columns={'id_x': 'id'})
        merged_df['descricao_acao'].fillna('Descrição não encontrada', inplace=True)

    # Armazena o dataframe original no estado da sessão para comparação
    if 'original_action_plan' not in st.session_state:
        st.session_state.original_action_plan = merged_df.copy()

    st.info("Você pode editar o **Status** diretamente na tabela abaixo. As alterações são salvas automaticamente.")

    # --- EXIBIÇÃO E EDIÇÃO COM DATA_EDITOR ---
    edited_df = st.data_editor(
        merged_df,
        column_config={
            "id": None,
            "id_acao_bloqueio": None,
            "unidade_operacional": st.column_config.TextColumn("Unidade", disabled=True),
            "descricao_acao": st.column_config.TextColumn("Ação de Abrangência", disabled=True, width="large"),
            "responsavel_email": st.column_config.TextColumn("Responsável", disabled=True),
            "prazo_inicial": st.column_config.DateColumn("Prazo", disabled=True, format="DD/MM/YYYY"),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=["Pendente", "Em Andamento", "Concluído", "Cancelado"],
                required=True,
            )
        },
        column_order=["unidade_operacional", "descricao_acao", "responsavel_email", "prazo_inicial", "status"],
        use_container_width=True,
        hide_index=True,
        key="action_plan_editor"
    )

    # --- LÓGICA PARA SALVAR ALTERAÇÕES ---
    original_df = st.session_state.original_action_plan

    if not edited_df.equals(original_df):
        with st.spinner("Salvando alterações..."):
            # Encontra as diferenças entre o dataframe original e o editado
            changes = original_df.compare(edited_df)
            
            for index in changes.index:
                action_id = original_df.loc[index, 'id']
                
                # Verifica se a coluna 'status' foi a que mudou
                if ('status', 'other') in changes.columns:
                    new_status = changes.loc[index, ('status', 'other')]
                    
                    updates = {"status": new_status}
                    # Se o status for 'Concluído', adiciona a data de conclusão
                    if new_status == "Concluído":
                        updates["data_conclusao"] = datetime.now().strftime("%d/%m/%Y")

                    success = incident_manager.update_abrangencia_action(action_id, updates)
                    if success:
                        st.toast(f"Status da ação ID {action_id} atualizado para '{new_status}'.")
                    else:
                        st.error(f"Falha ao atualizar o status da ação ID {action_id}.")
            
            # Atualiza o estado da sessão e limpa o cache para refletir a mudança
            st.session_state.original_action_plan = edited_df.copy()
            st.cache_data.clear()
            st.rerun()
