import streamlit as st
import pandas as pd
from datetime import date, datetime
from auth.auth_utils import check_permission
from operations.incident_manager import get_incident_manager, IncidentManager
from operations.audit_logger import log_action
from database.matrix_manager import get_matrix_manager
from operations.data_loader import DataCache

def convert_drive_url_to_displayable(url: str) -> str | None:
    # Generalized for Supabase or any http(S) public URL.
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    # If it's a valid HTTP(S) URL, return it directly so Streamlit can render it.
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return None

@st.cache_data(ttl=3600)  # Cache de 1 hora para URLs de imagens
def get_cached_image_url(url: str) -> str:
    """Cache de URLs de imagens para reduzir requisições"""
    return url

@st.dialog("Análise de Abrangência do Incidente", width="large")
def abrangencia_dialog(incident, incident_manager: IncidentManager):
    st.subheader(incident.get('evento_resumo'))
    st.caption(f"Alerta: {incident.get('numero_alerta')} | Data: {pd.to_datetime(incident.get('data_evento'), dayfirst=True).strftime('%d/%m/%Y')}")
    st.divider()
    st.markdown(f"**O que aconteceu?**"); st.write(incident.get('o_que_aconteceu'))
    st.markdown(f"**Por que aconteceu?**"); st.write(incident.get('por_que_aconteceu'))
    st.divider()
    blocking_actions = incident_manager.get_blocking_actions_by_incident(incident['id'])
    
    if blocking_actions.empty:
        st.success("Não há ações de bloqueio sugeridas para este incidente."); 
        if st.button("Fechar"): st.rerun()
        return

    st.subheader("Selecione as ações aplicáveis e defina os responsáveis")
    st.info("Ative uma ação para habilitar os campos e incluí-la no plano de ação.")

    def force_fragment_rerun(): pass
    
    matrix_manager = get_matrix_manager()
    user_map, user_names = matrix_manager.get_utilities_users()
    
    # <<< MUDANÇA AQUI: Permite que utilities tenha pessoas sem unidade >>>
    if not user_names:
        st.warning("A lista de responsáveis (aba 'utilities') não pôde ser carregada ou está vazia.")
        user_names = ["(Lista de usuários vazia)"]
        user_map = {}

    is_admin = st.session_state.get('unit_name') == 'Global'
    if is_admin:
        all_units = matrix_manager.get_all_units()
        # Adiciona opção para "sem unidade" ou digitação manual
        options = ["-- Digitar nome da UO --", "-- Pessoa sem UO (utilities) --"] + all_units
        chosen_option = st.selectbox("Selecione a Unidade Operacional (UO) de destino", options=options, key="admin_uo_selector")
        
        if chosen_option == "-- Digitar nome da UO --":
            st.text_input("Digite o nome da UO", key="admin_uo_text_input")
        elif chosen_option == "-- Pessoa sem UO (utilities) --":
            st.info("💡 O responsável selecionado não está associado a uma unidade específica. A ação será registrada como 'Utilities' ou 'Geral'.")
    
    st.markdown("---")
    for _, action in blocking_actions.iterrows():
        st.toggle(action['descricao_acao'], key=f"toggle_{action['id']}", on_change=force_fragment_rerun)
    st.divider()

    with st.form("abrangencia_form_data"):
        st.markdown("**Preencha os dados para as ações ativadas acima:**")
        col_resp, col_co_resp, col_prazo = st.columns([2, 2, 1])
        col_resp.caption("Responsável Principal"); col_co_resp.caption("Co-responsável (Opcional)"); col_prazo.caption("Prazo Final")

        for _, action in blocking_actions.iterrows():
            action_id = action['id']
            is_enabled = st.session_state.get(f"toggle_{action_id}", False)
            
            col_resp, col_co_resp, col_prazo = st.columns([2, 2, 1])
            with col_resp:
                st.selectbox("Responsável", options=user_names, index=None, placeholder="Selecione um nome...",
                             key=f"resp_{action_id}", disabled=not is_enabled or not user_names, label_visibility="collapsed")
            with col_co_resp:
                st.selectbox("Co-responsável", options=["(Nenhum)"] + user_names, index=0,
                             key=f"co_resp_{action_id}", disabled=not is_enabled or not user_names, label_visibility="collapsed")
            with col_prazo:
                st.date_input("Prazo", min_value=date.today(), key=f"prazo_{action_id}", disabled=not is_enabled, label_visibility="collapsed")
        
        submitted = st.form_submit_button("Registrar Plano de Ação", type="primary")

    if submitted:
        unit_to_save = None
        if is_admin:
            if st.session_state.admin_uo_selector == "-- Digitar nome da UO --":
                unit_to_save = st.session_state.admin_uo_text_input
            elif st.session_state.admin_uo_selector == "-- Pessoa sem UO (utilities) --":
                unit_to_save = "Utilities"  # <<< Nome padrão para pessoas sem UO
            else:
                unit_to_save = st.session_state.admin_uo_selector
            
            if not unit_to_save or not unit_to_save.strip():
                st.error("Administrador: Por favor, selecione ou digite o nome da Unidade Operacional."); return
        else:
            unit_to_save = st.session_state.unit_name

        actions_to_save = []
        for _, action in blocking_actions.iterrows():
            action_id = action['id']
            if st.session_state.get(f"toggle_{action_id}", False):
                responsavel_nome = st.session_state[f"resp_{action_id}"]
                co_responsavel_nome = st.session_state[f"co_resp_{action_id}"]
                
                if not responsavel_nome:
                    st.error(f"Ação selecionada '{action['descricao_acao']}' está sem Responsável Principal."); return
                
                responsavel_email = user_map.get(responsavel_nome)
                if not responsavel_email:
                    st.error(f"Erro de Dados: O e-mail para o responsável '{responsavel_nome}' não foi encontrado na lista de usuários ('utilities'). Verifique a planilha e tente novamente.")
                    return
                
                co_responsavel_email = user_map.get(co_responsavel_nome) if co_responsavel_nome and co_responsavel_nome != "(Nenhum)" else ""
                
                actions_to_save.append({
                    "id_acao_bloqueio": action_id, "descricao": action['descricao_acao'], "unidade_operacional": unit_to_save,
                    "responsavel_email": responsavel_email, "co_responsavel_email": co_responsavel_email,
                    "prazo_inicial": st.session_state[f"prazo_{action_id}"]
                })
        
        if not actions_to_save:
            st.warning("Nenhuma ação foi selecionada. Ative uma ou mais ações para salvar."); return

        saved_count = 0
        with st.spinner(f"Salvando {len(actions_to_save)} ação(ões) para a UO: {unit_to_save}..."):
            for action_data in actions_to_save:
                new_id = incident_manager.add_abrangencia_action(
                    id_acao_bloqueio=action_data['id_acao_bloqueio'], unidade_operacional=action_data['unidade_operacional'],
                    responsavel_email=action_data['responsavel_email'], co_responsavel_email=action_data['co_responsavel_email'],
                    prazo_inicial=action_data['prazo_inicial'], status="Pendente"
                )
                if new_id:
                    saved_count += 1
                    log_action("ADD_ACTION_PLAN_ITEM", {"plan_id": new_id, "desc": action_data['descricao'], "target_unit": unit_to_save})
        
        st.success(f"{saved_count} ação(ões) salvas com sucesso!")
        import time; time.sleep(2); st.rerun()

def render_incident_card(incident, col, incident_manager, is_pending):
    with col.container(border=True):
        foto_url = incident.get('foto_url')
        if pd.notna(foto_url) and isinstance(foto_url, str) and foto_url.strip():
            display_url = convert_drive_url_to_displayable(foto_url)
            if display_url: 
                cached_url = get_cached_image_url(display_url)
                st.image(cached_url, use_container_width=True)
            else: 
                st.caption("Imagem não disponível ou URL inválida")
        else:
            st.markdown(f"#### Alerta: {incident.get('numero_alerta')}")
            st.caption("Sem imagem anexada")
        st.subheader(incident.get('evento_resumo'))
        st.write(incident.get('o_que_aconteceu'))
        anexos_url = incident.get('anexos_url')
        if pd.notna(anexos_url) and isinstance(anexos_url, str) and anexos_url.strip():
            st.markdown(f"**[Ver Análise Completa 📄]({anexos_url})**")
        st.write("") 
        if is_pending:
            if st.button("Analisar Abrangência", key=f"analisar_{incident['id']}", type="primary", width='stretch'):
                abrangencia_dialog(incident, incident_manager)
        else: st.success("✔ Análise Registrada", icon="✅")

def display_incident_list(incident_manager: IncidentManager):
    st.title("Dashboard de Incidentes")
    
    # <<< USA CACHE PERSISTENTE >>>
    all_incidents_df = DataCache.get_or_load(
        key="all_incidents",
        loader_func=incident_manager.get_all_incidents,
        ttl_seconds=300  # 5 minutos
    )
    
    if all_incidents_df.empty:
        st.info("Nenhum incidente cadastrado no sistema ainda.")
        return
    
    user_unit = st.session_state.get('unit_name', 'Global')
    
    if user_unit != 'Global':
        # Cache específico por unidade
        covered_ids = DataCache.get_or_load(
            key=f"covered_incidents_{user_unit}",
            loader_func=incident_manager.get_covered_incident_ids_for_unit,
            ttl_seconds=300,
            unit_name=user_unit
        )
        
        # Separa incidentes pendentes e analisados
        all_incidents_df['id_str'] = all_incidents_df['id'].astype(str)
        pending_df = all_incidents_df[~all_incidents_df['id_str'].isin(covered_ids)]
        analyzed_df = all_incidents_df[all_incidents_df['id_str'].isin(covered_ids)]
    else:
        # Admin vê todos como pendentes para análise global
        pending_df = all_incidents_df
        analyzed_df = pd.DataFrame()
    
    # Ordena por data (mais recente primeiro)
    if 'data_evento' in pending_df.columns:
        pending_df['data_dt'] = pd.to_datetime(pending_df['data_evento'], format='%d/%m/%Y', errors='coerce')
        pending_df = pending_df.sort_values('data_dt', ascending=False)
    
    if not analyzed_df.empty and 'data_evento' in analyzed_df.columns:
        analyzed_df['data_dt'] = pd.to_datetime(analyzed_df['data_evento'], format='%d/%m/%Y', errors='coerce')
        analyzed_df = analyzed_df.sort_values('data_dt', ascending=False)
    
    # Exibe métricas
    col1, col2 = st.columns(2)
    col1.metric("📋 Incidentes Pendentes de Análise", len(pending_df))
    col2.metric("✅ Incidentes Já Analisados", len(analyzed_df))
    
    st.divider()
    
    # Renderiza incidentes pendentes
    if not pending_df.empty:
        st.subheader("🔴 Pendentes de Análise de Abrangência")
        cols = st.columns(3)
        for idx, (_, incident) in enumerate(pending_df.iterrows()):
            col = cols[idx % 3]
            render_incident_card(incident, col, incident_manager, is_pending=True)
    else:
        st.success("🎉 Parabéns! Todos os incidentes já foram analisados pela sua unidade.")
    
    # Renderiza incidentes já analisados
    if not analyzed_df.empty:
        st.divider()
        with st.expander(f"✅ Ver {len(analyzed_df)} Incidentes Já Analisados", expanded=False):
            cols = st.columns(3)
            for idx, (_, incident) in enumerate(analyzed_df.iterrows()):
                col = cols[idx % 3]
                render_incident_card(incident, col, incident_manager, is_pending=False)

def show_dashboard_page():
    check_permission(level='viewer')
    incident_manager = get_incident_manager()
    display_incident_list(incident_manager)
