import streamlit as st
import pandas as pd
from datetime import datetime, date
from auth.auth_utils import check_permission, get_user_role
from operations.incident_manager import get_incident_manager
from operations.audit_logger import log_action
from gdrive.google_api_manager import GoogleApiManager
from gdrive.config import ACTION_PLAN_EVIDENCE_FOLDER_ID
from front.dashboard import convert_drive_url_to_displayable

@st.cache_data(ttl=120)
def load_action_plan_data():
    """
    Carrega e une os dados do plano de ação com as descrições das ações de bloqueio
    e informações dos incidentes originais, tratando corretamente colunas de ID duplicadas.
    """
    incident_manager = get_incident_manager()
    action_plan_df = incident_manager.get_all_action_plans()
    blocking_actions_df = incident_manager.get_all_blocking_actions()
    incidents_df = incident_manager.get_all_incidents()

    if action_plan_df.empty:
        return pd.DataFrame()

    # Renomeia colunas de ID ANTES de fazer os merges para evitar conflitos
    blocking_actions_renamed = blocking_actions_df.rename(columns={'id': 'id_acao_bloqueio_ref'})
    incidents_renamed = incidents_df.rename(columns={'id': 'id_incidente_ref'})
    
    # 1. Merge do plano de ação com as ações de bloqueio
    merged_df = pd.merge(
        action_plan_df,
        blocking_actions_renamed[['id_acao_bloqueio_ref', 'descricao_acao', 'id_incidente']],
        left_on='id_acao_bloqueio',
        right_on='id_acao_bloqueio_ref',
        how='left'
    )

    # 2. Merge com os incidentes
    final_df = pd.merge(
        merged_df,
        incidents_renamed[['id_incidente_ref', 'evento_resumo']],
        left_on='id_incidente',
        right_on='id_incidente_ref',
        how='left'
    )
    
    # 3. Limpeza final e preenchimento de valores nulos
    final_df['descricao_acao'] = final_df['descricao_acao'].fillna('Descrição da ação não encontrada')
    final_df['evento_resumo'] = final_df['evento_resumo'].fillna('Incidente original não encontrado')
    
    # Garante que as colunas opcionais existam no DataFrame
    for col in ['url_evidencia', 'detalhes_conclusao']:
        if col not in final_df.columns:
            final_df[col] = ''
        final_df[col] = final_df[col].fillna('')

    # Remove colunas de referência que não são mais necessárias
    final_df = final_df.drop(columns=['id_acao_bloqueio_ref', 'id_incidente_ref'], errors='ignore')

    return final_df


@st.dialog("Editar Ação de Abrangência")
def edit_action_dialog(item_data):
    """Renderiza um formulário em um diálogo para editar um item do plano de ação."""
    st.subheader("Item: " + item_data.get('descricao_acao', ''))
    st.caption("Incidente Original: " + item_data.get('evento_resumo', ''))
    
    prazo_atual = None
    if item_data.get('prazo_inicial') and isinstance(item_data['prazo_inicial'], str):
        try:
            prazo_atual = datetime.strptime(item_data['prazo_inicial'], "%d/%m/%Y").date()
        except (ValueError, TypeError): pass

    with st.form("edit_action_form"):
        status_options = ["Pendente", "Em Andamento", "Concluído", "Cancelado"]
        try:
            current_status_index = status_options.index(item_data.get('status', 'Pendente'))
        except ValueError: current_status_index = 0
        
        new_status = st.selectbox("Status", status_options, index=current_status_index)
        
        detalhes_conclusao = st.text_area(
            "Detalhes da Ação / O que foi feito?",
            value=item_data.get('detalhes_conclusao', ''),
            help="Descreva a ação realizada para concluir esta tarefa. Ficará registrado no histórico."
        )
        st.divider()

        new_prazo = st.date_input("Prazo para Implementação", value=prazo_atual)
        new_responsavel = st.text_input("E-mail do Responsável", value=item_data.get('responsavel_email', ''))
        new_co_responsavel = st.text_input("E-mail do Co-Responsável (Opcional)", value=item_data.get('co_responsavel_email', ''))
        
        st.divider()
        
        uploaded_evidence = st.file_uploader("Anexar Evidência (Foto ou PDF)", type=['jpg', 'png', 'jpeg', 'pdf'])
        current_evidence_url = item_data.get('url_evidencia', '')
        if current_evidence_url:
            st.write("Evidência atual:")
            is_pdf = '.pdf' in current_evidence_url.lower()
            if is_pdf:
                st.markdown(f"📄 **[Ver PDF Anexado]({current_evidence_url})**")
            else:
                thumb_url = convert_drive_url_to_displayable(current_evidence_url)
                if thumb_url: st.image(thumb_url, width=200)
                st.markdown(f"[Ver imagem completa]({current_evidence_url})")

        submitted = st.form_submit_button("Salvar Alterações")

        if submitted:
            if new_status == "Concluído" and not detalhes_conclusao.strip():
                st.error("Para marcar como 'Concluído', é obrigatório preencher o campo 'Detalhes da Ação'.")
                return

            with st.spinner("Salvando..."):
                updates = {
                    "status": new_status,
                    "prazo_inicial": new_prazo.strftime("%d/%m/%Y") if new_prazo else "",
                    "responsavel_email": new_responsavel,
                    "co_responsavel_email": new_co_responsavel,
                    "detalhes_conclusao": detalhes_conclusao
                }
                if uploaded_evidence:
                    api_manager = GoogleApiManager()
                    safe_action_id = "".join(c for c in str(item_data['id']) if c.isalnum())
                    file_extension = uploaded_evidence.name.split('.')[-1]
                    file_name = f"evidencia_acao_{safe_action_id}.{file_extension}"
                    evidence_url = api_manager.upload_file(ACTION_PLAN_EVIDENCE_FOLDER_ID, uploaded_evidence, file_name)
                    if evidence_url:
                        updates["url_evidencia"] = evidence_url; st.toast("Evidência enviada com sucesso!")
                    else:
                        st.error("Falha ao enviar a evidência. As outras alterações não foram salvas."); return
                if new_status == "Concluído" and item_data.get('status') != 'Concluído':
                    updates["data_conclusao"] = datetime.now().strftime("%d/%m/%Y")
                
                incident_manager = get_incident_manager()
                if incident_manager.update_abrangencia_action(item_data['id'], updates):
                    st.success("Ação atualizada com sucesso!")
                    if 'item_to_edit' in st.session_state: del st.session_state.item_to_edit
                    st.rerun()
                else: st.error("Falha ao atualizar a ação.")

def prepare_history_df(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara o DataFrame do histórico para exibição, processando a coluna de evidências."""
    history_df = df.copy()
    history_df['foto_evidencia'] = history_df['url_evidencia'].apply(
        lambda url: convert_drive_url_to_displayable(url) if url and not url.lower().endswith('.pdf') else None
    )
    history_df['pdf_evidencia'] = history_df['url_evidencia'].apply(
        lambda url: url if url and url.lower().endswith('.pdf') else None
    )
    return history_df

def show_plano_acao_page():
    st.title("📋 Plano de Ação de Abrangência")
    check_permission(level='viewer')

    # Verifica se o diálogo deve ser aberto
    if st.session_state.get('item_to_edit'):
        edit_action_dialog(st.session_state.item_to_edit)

    full_action_plan_df = load_action_plan_data()

    # (Lógica de filtros)
    st.subheader("Filtros de Visualização")
    col1, col2 = st.columns(2)
    with col1:
        unit_options = ["Todas"] + sorted(full_action_plan_df['unidade_operacional'].unique().tolist()) if not full_action_plan_df.empty else ["Todas"]
        user_unit = st.session_state.get('unit_name', 'Global')
        default_index = 0
        if user_unit != 'Global' and user_unit in unit_options: default_index = unit_options.index(user_unit)
        selected_unit = st.selectbox("Filtrar por Unidade Operacional:", options=unit_options, index=default_index)
    with col2:
        status_options = ["Todos", "Pendentes", "Concluídos"]
        selected_status_filter = st.selectbox("Filtrar por Status:", options=status_options)
    
    filtered_df = full_action_plan_df.copy()
    if selected_unit != "Todas":
        filtered_df = filtered_df[filtered_df['unidade_operacional'] == selected_unit]
    if selected_status_filter == "Pendentes":
        filtered_df = filtered_df[~filtered_df['status'].str.lower().isin(['concluído', 'cancelado'])]
    elif selected_status_filter == "Concluídos":
        filtered_df = filtered_df[filtered_df['status'].str.lower().isin(['concluído', 'cancelado'])]
    st.divider()

    if filtered_df.empty:
        st.info("Nenhum item encontrado com os filtros selecionados."); st.stop()

    st.subheader("Visão por Cards")
    total_pending = len(filtered_df[~filtered_df['status'].str.lower().isin(['concluído', 'cancelado'])])
    st.metric("Total de Ações Abertas (na visão atual)", total_pending)
    is_editor_or_admin = get_user_role() in ['editor', 'admin']

    # (CSS para borda vermelha)
    st.markdown("""<style>.overdue-container > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] > div {
        border-color: #FF4B4B !important; border-width: 2px !important;}</style>""", unsafe_allow_html=True)

    for incident_id, group in filtered_df.groupby('id_incidente'):
        incident_resumo = group['evento_resumo'].iloc[0]
        total_actions_in_group = len(group)
        completed_actions = len(group[group['status'].str.lower().isin(['concluído', 'cancelado'])])
        expander_title = f"**{incident_resumo}** (`{completed_actions}/{total_actions_in_group}` concluídas)"

        with st.expander(expander_title, expanded=True):
            for _, row in group.iterrows():
                is_overdue = False; status = row['status']
                if status.lower() in ['pendente', 'em andamento']:
                    try:
                        prazo_dt = datetime.strptime(row['prazo_inicial'], "%d/%m/%Y").date()
                        if prazo_dt < date.today(): is_overdue = True
                    except (ValueError, TypeError): pass
                
                container_class = "overdue-container" if is_overdue else ""
                with st.html(f"<div class='{container_class}'>"):
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([4, 2, 1])
                        with col1:
                            overdue_icon = "⚠️ " if is_overdue else ""
                            st.markdown(f"**Ação:** {overdue_icon}{row['descricao_acao']}")
                            st.caption(f"**Responsável:** {row.get('responsavel_email', 'N/A')}")
                            evidence_url = row.get('url_evidencia', '')
                            if evidence_url:
                                is_pdf = '.pdf' in evidence_url.lower(); icon = "📄" if is_pdf else "🖼️"
                                label = "Ver Evidência PDF" if is_pdf else "Ver Foto da Evidência"
                                st.markdown(f"**[{label} {icon}]({evidence_url})**")
                            
                            detalhes = row.get('detalhes_conclusao', '')
                            if detalhes:
                                with st.popover("Ver Detalhes da Ação"):
                                    st.markdown(detalhes)
                        with col2:
                            if status == "Pendente": st.warning(f"**Status:** {status}")
                            elif status == "Em Andamento": st.info(f"**Status:** {status}")
                            else: st.success(f"**Status:** {status}")
                            st.write(f"**Prazo:** {row['prazo_inicial']}")
                        with col3:
                            if is_editor_or_admin:
                                def set_item_to_edit(item_row): st.session_state.item_to_edit = item_row.to_dict()
                                st.button("Editar", key=f"edit_{row['id']}", on_click=set_item_to_edit, args=(row,), width='stretch')
    st.divider()

    with st.expander("📖 Ver Histórico Completo em Tabela", expanded=False):
        st.info("Esta tabela mostra todos os itens do plano de ação com base nos filtros acima.")
        history_df_prepared = prepare_history_df(filtered_df)
        st.dataframe(history_df_prepared, column_config={
            "id": None, "id_acao_bloqueio": None, "id_incidente": None, "url_evidencia": None,
            "unidade_operacional": st.column_config.TextColumn("UO", width="small"),
            "evento_resumo": st.column_config.TextColumn("Incidente Original"),
            "descricao_acao": st.column_config.TextColumn("Ação de Abrangência", width="large"),
            "detalhes_conclusao": "Detalhes da Ação", "status": "Status", 
            "responsavel_email": st.column_config.TextColumn("Responsável"), "prazo_inicial": "Prazo", 
            "data_conclusao": "Conclusão", "foto_evidencia": st.column_config.ImageColumn("Foto Evidência"),
            "pdf_evidencia": st.column_config.LinkColumn("PDF Evidência", display_text="📄 Ver PDF"),
        }, column_order=[ "unidade_operacional", "evento_resumo", "descricao_acao", "detalhes_conclusao", "status", 
            "responsavel_email", "prazo_inicial", "data_conclusao", "foto_evidencia", "pdf_evidencia" ],
        hide_index=True, width='stretch')
