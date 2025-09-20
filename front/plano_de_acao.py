import streamlit as st
import pandas as pd
from auth.auth_utils import check_permission
from operations.incident_manager import IncidentManager
from gdrive.matrix_manager import MatrixManager as GlobalMatrixManager

def show_plano_acao_page():
    """
    Renderiza a página do Plano de Ação de Abrangência, permitindo a visualização
    e atualização do status das ações pertinentes à unidade do usuário.
    """
    st.title("Plano de Ação de Abrangência")

    # --- VERIFICAÇÕES INICIAIS ---
    if not check_permission(level='viewer'):
        st.stop()

    if not st.session_state.get('managers_initialized'):
        st.warning("Selecione uma unidade operacional para visualizar o plano de ação.")
        st.stop()

    # --- INICIALIZAÇÃO DOS MANAGERS ---
    try:
        # Manager da Unidade para ler e escrever no plano de ação local
        unit_spreadsheet_id = st.session_state.get('spreadsheet_id')
        unit_incident_manager = IncidentManager(unit_spreadsheet_id)

        # Manager Global para obter as descrições das ações de bloqueio
        global_matrix_manager = GlobalMatrixManager()
        matrix_spreadsheet_id = global_matrix_manager.spreadsheet.id
        global_incident_manager = IncidentManager(matrix_spreadsheet_id)
    except Exception as e:
        st.error(f"Erro ao inicializar os gerenciadores de dados: {e}")
        st.stop()

    # --- CARREGAMENTO E JUNÇÃO DOS DADOS ---
    @st.cache_data(ttl=60)
    def load_action_plan_data(unit_sheet_id, matrix_sheet_id):
        """Carrega os dados do plano de ação da unidade e as descrições da matriz central."""
        unit_manager = IncidentManager(unit_sheet_id)
        global_manager = IncidentManager(matrix_sheet_id)
        
        action_plan_df = unit_manager.sheet_ops.get_df_from_worksheet("plano_de_acao_abrangencia")
        blocking_actions_df = global_manager.sheet_ops.get_df_from_worksheet("acoes_bloqueio")
        return action_plan_df, blocking_actions_df

    action_plan_df, blocking_actions_df = load_action_plan_data(unit_spreadsheet_id, matrix_spreadsheet_id)

    if action_plan_df.empty:
        st.success("🎉 Nenhum item no plano de ação de abrangência para esta unidade.")
        st.stop()

    if blocking_actions_df.empty:
        st.warning("Não foi possível carregar as descrições das ações de bloqueio da planilha central.")
        # Mesmo com o aviso, exibe os dados que temos
        merged_df = action_plan_df
        merged_df['descricao_acao'] = "Descrição não encontrada"
    else:
        # Junta os dataframes para adicionar a descrição da ação
        merged_df = pd.merge(
            action_plan_df,
            blocking_actions_df[['id', 'descricao_acao']],
            left_on='id_acao_bloqueio',
            right_on='id',
            how='left'
        ).drop(columns=['id_y']).rename(columns={'id_x': 'id'})
        merged_df['descricao_acao'].fillna('Descrição não encontrada', inplace=True)

    # Armazena o dataframe original no estado da sessão para comparação posterior
    if 'original_action_plan' not in st.session_state:
        st.session_state.original_action_plan = merged_df.copy()

    st.info("Você pode editar o **Status** diretamente na tabela abaixo. As alterações são salvas automaticamente.")

    # --- EXIBIÇÃO E EDIÇÃO COM DATA_EDITOR ---
    edited_df = st.data_editor(
        merged_df,
        column_config={
            "id": None, # Oculta a coluna de ID
            "id_acao_bloqueio": None,
            "unidade_operacional": None,
            "descricao_acao": st.column_config.TextColumn("Ação de Abrangência", disabled=True, width="large"),
            "responsavel_email": st.column_config.TextColumn("Responsável", disabled=True),
            "prazo_inicial": st.column_config.DateColumn("Prazo", disabled=True, format="DD/MM/YYYY"),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=["Pendente", "Em Andamento", "Concluído", "Cancelado"],
                required=True,
            )
        },
        column_order=["descricao_acao", "responsavel_email", "prazo_inicial", "status"],
        use_container_width=True,
        hide_index=True,
        key="action_plan_editor"
    )

    # --- LÓGICA PARA SALVAR ALTERAÇÕES ---
    original_df = st.session_state.original_action_plan

    # Compara o dataframe editado com o original para encontrar mudanças
    if not edited_df.equals(original_df):
        with st.spinner("Salvando alterações..."):
            changes = original_df.compare(edited_df)
            
            for index in changes.index:
                action_id = original_df.loc[index, 'id']
                # O .compare() retorna 'self' e 'other' para as colunas alteradas
                # Estamos interessados apenas na coluna 'status'
                if ('status', 'other') in changes.columns:
                    new_status = changes.loc[index, ('status', 'other')]
                    success = unit_incident_manager.update_abrangencia_action(action_id, {"status": new_status})
                    if success:
                        st.toast(f"Status da ação ID {action_id} atualizado para '{new_status}'.")
                    else:
                        st.error(f"Falha ao atualizar o status da ação ID {action_id}.")
            
            # Atualiza o estado da sessão e limpa o cache para refletir a mudança
            st.session_state.original_action_plan = edited_df.copy()
            st.cache_data.clear()
            st.rerun()