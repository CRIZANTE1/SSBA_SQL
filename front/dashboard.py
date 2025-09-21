import streamlit as st
import pandas as pd
from datetime import date
from auth.auth_utils import check_permission
from operations.incident_manager import get_incident_manager, IncidentManager
from operations.audit_logger import log_action
from gdrive.matrix_manager import get_matrix_manager

def convert_drive_url_to_displayable(url: str) -> str | None:
    """
    Converte uma URL de visualização do Google Drive para um formato de thumbnail
    que é mais confiável para exibição direta em st.image.
    """
    if not isinstance(url, str) or 'drive.google.com' not in url:
        return None
    
    try:
        if '/d/' in url:
            file_id = url.split('/d/')[1].split('/')[0]
        elif 'id=' in url:
            file_id = url.split('id=')[1].split('&')[0]
        else:
            return None

        return f'https://drive.google.com/thumbnail?id={file_id}'
    
    except IndexError:
        return None
        
@st.dialog("Análise de Abrangência do Incidente")
def abrangencia_dialog(incident, incident_manager: IncidentManager):
    """
    Renderiza um diálogo modal para o usuário analisar o incidente e selecionar
    as ações de abrangência aplicáveis, definindo responsáveis.
    """
    st.subheader(incident.get('evento_resumo'))
    st.caption(f"Alerta: {incident.get('numero_alerta')} | Data: {pd.to_datetime(incident.get('data_evento'), dayfirst=True).strftime('%d/%m/%Y')}")
    st.divider()

    st.markdown(f"**O que aconteceu?**")
    st.write(incident.get('o_que_aconteceu'))
    st.markdown(f"**Por que aconteceu?**")
    st.write(incident.get('por_que_aconteceu'))
    st.divider()

    blocking_actions = incident_manager.get_blocking_actions_by_incident(incident['id'])
    
    if blocking_actions.empty:
        st.success("Não há ações de bloqueio sugeridas para este incidente.")
        if st.button("Fechar"):
            st.rerun()
        return

    st.subheader("Selecione as ações aplicáveis")
    
    with st.form("abrangencia_dialog_form"):
        is_admin = st.session_state.get('unit_name') == 'Global'
        target_unit_name = None

        if is_admin:
            st.info("Como Administrador, você pode registrar esta abrangência para qualquer UO.")
            matrix_manager = get_matrix_manager()
            all_units = matrix_manager.get_all_units()
            options = ["-- Digitar nome da UO --"] + all_units
            
            chosen_option = st.selectbox(
                "Selecione a Unidade Operacional (UO)", 
                options=options
            )

            if chosen_option == "-- Digitar nome da UO --":
                target_unit_name = st.text_input("Digite o nome da UO (ex: BAERI)", key="new_uo_input")
            else:
                target_unit_name = chosen_option
        else:
            st.markdown(f"**Unidade Operacional:** `{st.session_state.unit_name}`")

        pertinent_actions = {}
        for _, action in blocking_actions.iterrows():
            action_id = action['id']
            description = action['descricao_acao']
            is_pertinent = st.toggle(description, key=f"toggle_dialog_{action_id}")
            if is_pertinent:
                pertinent_actions[action_id] = description
        
        st.divider()
        st.markdown("**Defina os responsáveis e o prazo para as ações selecionadas:**")
        
        col1, col2 = st.columns(2)
        with col1:
            responsavel_email = st.text_input(
                "E-mail do Responsável Principal", 
                value=st.session_state.get('user_info', {}).get('email', ''),
                help="Este é o responsável direto pela execução da ação."
            )
        with col2:
            co_responsavel_email = st.text_input(
                "E-mail do Co-responsável (Opcional)",
                placeholder="email.coresponsavel@exemplo.com",
                help="Receberá os lembretes de prazo junto com o responsável principal."
            )

        prazo_inicial = st.date_input("Prazo para Implementação", min_value=date.today())

        submitted = st.form_submit_button("Registrar Plano de Ação", type="primary")

        if submitted:
            if is_admin:
                unit_to_save = target_unit_name
                if not unit_to_save or not unit_to_save.strip():
                    st.error("Administrador: Por favor, selecione ou digite o nome da Unidade Operacional.")
                    return
            else:
                unit_to_save = st.session_state.unit_name

            if not pertinent_actions:
                st.warning("Nenhuma ação foi selecionada.")
                return
            if not responsavel_email or not prazo_inicial:
                st.error("O e-mail do responsável principal e o prazo são obrigatórios.")
                return

            saved_count = 0
            with st.spinner(f"Salvando ações para a UO: {unit_to_save}..."):
                for action_id, desc in pertinent_actions.items():
                    new_id = incident_manager.add_abrangencia_action(
                        id_acao_bloqueio=action_id,
                        unidade_operacional=unit_to_save.strip(),
                        responsavel_email=responsavel_email,
                        co_responsavel_email=co_responsavel_email,
                        prazo_inicial=prazo_inicial,
                        status="Pendente"
                    )
                    if new_id:
                        saved_count += 1
                        log_action("ADD_ACTION_PLAN_ITEM", {"plan_id": new_id, "desc": desc, "target_unit": unit_to_save})
            
            st.success(f"{saved_count} ação(ões) salvas com sucesso para a UO '{unit_to_save}'!")
            import time
            time.sleep(2)
            st.rerun()


def render_incident_card(incident, col, incident_manager, is_pending):
    """Função auxiliar para renderizar um card de incidente."""
    with col.container(border=True):
        foto_url = incident.get('foto_url')
        if pd.notna(foto_url) and isinstance(foto_url, str) and foto_url.strip():
            display_url = convert_drive_url_to_displayable(foto_url)
            if display_url:
                st.image(display_url, width='stretch')
            else:
                st.caption("Imagem não disponível ou URL inválida")
        else:
            st.markdown(f"#### Alerta: {incident.get('numero_alerta')}")
            st.caption("Sem imagem anexada")

        st.subheader(incident.get('evento_resumo'))
        st.write(incident.get('o_que_aconteceu'))
        
        if is_pending:
            if st.button("Analisar Abrangência", key=f"analisar_{incident['id']}", type="primary", width='stretch'):
                abrangencia_dialog(incident, incident_manager)
        else:
            st.success("✔ Análise Registrada", icon="✅")


def display_incident_list(incident_manager: IncidentManager):
    """
    Exibe a lista de todos os incidentes, separando-os em pendentes e analisados
    para as unidades operacionais, e mostrando apenas pendências globais para o Admin.
    """
    st.title("Dashboard de Incidentes")
    
    user_unit = st.session_state.get('unit_name', 'Global')
    matrix_manager = get_matrix_manager()

    # --- LÓGICA DE EXIBIÇÃO ---
    
    # Se for Admin Global, usa a nova lógica de verificação
    if user_unit == 'Global':
        st.subheader("Alertas com Abrangência Pendente no Sistema")
        all_active_units = matrix_manager.get_all_units()
        
        if not all_active_units:
            st.warning("Não há unidades operacionais cadastradas no sistema. A visão de pendências globais não pode ser calculada.")
            st.info("Cadastre usuários e associe-os a unidades no painel de Administração.")
            return

        incidents_to_show_df = incident_manager.get_globally_pending_incidents(all_active_units)

        if incidents_to_show_df.empty:
            st.success("🎉 Todos os alertas foram analisados por todas as unidades operacionais ativas!")
        else:
            st.info(f"Exibindo **{len(incidents_to_show_df)}** alerta(s) que ainda possuem pendências em ao menos uma UO.")
            cols = st.columns(3)
            for i, (_, incident) in enumerate(incidents_to_show_df.iterrows()):
                col = cols[i % 3]
                render_incident_card(incident, col, incident_manager, is_pending=True)

    # Se for uma UO específica, a lógica anterior de 'pendente vs analisado' se mantém
    else:
        all_incidents_df = incident_manager.get_all_incidents()
        if all_incidents_df.empty:
            st.info("Nenhum alerta de incidente cadastrado no sistema.")
            return

        try:
            all_incidents_df['data_evento_dt'] = pd.to_datetime(all_incidents_df['data_evento'], dayfirst=True)
            sorted_incidents = all_incidents_df.sort_values(by="data_evento_dt", ascending=False)
        except Exception:
            sorted_incidents = all_incidents_df

        covered_incident_ids = incident_manager.get_covered_incident_ids_for_unit(user_unit)
        
        pending_incidents_df = sorted_incidents[~sorted_incidents['id'].isin(covered_incident_ids)]
        covered_incidents_df = sorted_incidents[sorted_incidents['id'].isin(covered_incident_ids)]

        st.subheader("🚨 Alertas Pendentes de Análise")
        if pending_incidents_df.empty:
            st.success(f"🎉 Ótimo trabalho! Não há alertas pendentes para a unidade **{user_unit}**.")
        else:
            st.write(f"Você tem **{len(pending_incidents_df)}** alerta(s) para analisar.")
            cols_pending = st.columns(3)
            for i, (_, incident) in enumerate(pending_incidents_df.iterrows()):
                col = cols_pending[i % 3]
                render_incident_card(incident, col, incident_manager, is_pending=True)

        st.divider()

        st.subheader("✅ Alertas já Analisados")
        if covered_incidents_df.empty:
            st.info("Nenhum alerta foi analisado por esta unidade ainda.")
        else:
            cols_covered = st.columns(3)
            for i, (_, incident) in enumerate(covered_incidents_df.iterrows()):
                col = cols_covered[i % 3]
                render_incident_card(incident, col, incident_manager, is_pending=False)

def show_dashboard_page():
    """Ponto de entrada principal para a página do dashboard."""
    check_permission(level='viewer')
    incident_manager = get_incident_manager()
    display_incident_list(incident_manager)
