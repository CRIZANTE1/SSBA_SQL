import streamlit as st
import pandas as pd
from datetime import date
from auth.auth_utils import check_permission
from operations.incident_manager import get_incident_manager, IncidentManager
from operations.audit_logger import log_action

def convert_drive_url_to_displayable(url: str) -> str | None:
    """
    Converte uma URL de visualização do Google Drive para um formato
    que pode ser exibido diretamente por st.image ou tags <img>.
    """
    if not isinstance(url, str) or 'drive.google.com' not in url:
        return url # Retorna a URL original se não for do Drive ou for inválida
    
    try:
        # Extrai o ID do arquivo da URL
        file_id = url.split('/d/')[1].split('/')[0]
        return f'https://drive.google.com/uc?export=view&id={file_id}'
    except IndexError:
        # Retorna a URL original se o formato for inesperado
        return url

@st.dialog("Análise de Abrangência do Incidente")
def abrangencia_dialog(incident, incident_manager: IncidentManager):
    """
    Renderiza um diálogo modal para o usuário analisar o incidente e selecionar
    as ações de abrangência aplicáveis, definindo responsáveis.
    """
    st.subheader(incident.get('evento_resumo'))
    st.caption(f"Alerta: {incident.get('numero_alerta')} | Data: {pd.to_datetime(incident.get('data_evento'), dayfirst=True).strftime('%d/%m/%Y')}")
    st.divider()

    # Detalhes do incidente (permanece igual)
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

    st.subheader("Selecione as ações aplicáveis à sua UO")
    
    with st.form("abrangencia_dialog_form"):
        pertinent_actions = {}
        for _, action in blocking_actions.iterrows():
            action_id = action['id']
            description = action['descricao_acao']
            is_pertinent = st.toggle(description, key=f"toggle_dialog_{action_id}")
            if is_pertinent:
                pertinent_actions[action_id] = description
        
        st.divider()
        st.markdown("**Defina os responsáveis e o prazo para as ações selecionadas:**")
        
        # <<< MUDANÇA IMPORTANTE: Novos campos de e-mail >>>
        col1, col2 = st.columns(2)
        with col1:
            # O responsável principal, com o e-mail do usuário logado como sugestão
            responsavel_email = st.text_input(
                "E-mail do Responsável Principal", 
                value=st.session_state.get('user_info', {}).get('email', ''),
                help="Este é o responsável direto pela execução da ação."
            )
        with col2:
            # O co-responsável, que receberá as notificações junto com o principal
            co_responsavel_email = st.text_input(
                "E-mail do Co-responsável (Opcional)",
                placeholder="email.coresponsavel@exemplo.com",
                help="Receberá os lembretes de prazo junto com o responsável principal."
            )

        prazo_inicial = st.date_input("Prazo para Implementação", min_value=date.today())

        submitted = st.form_submit_button("Registrar Plano de Ação", type="primary")

        if submitted:
            if not pertinent_actions:
                st.warning("Nenhuma ação foi selecionada. Para concluir a análise, selecione ao menos uma ação aplicável.")
                return
            if not responsavel_email or not prazo_inicial:
                st.error("O e-mail do responsável principal e o prazo são obrigatórios.")
                return

            saved_count = 0
            with st.spinner("Salvando..."):
                for action_id, desc in pertinent_actions.items():
                    new_id = incident_manager.add_abrangencia_action(
                        id_acao_bloqueio=action_id,
                        unidade_operacional=st.session_state.unit_name,
                        responsavel_email=responsavel_email,
                        co_responsavel_email=co_responsavel_email, # Novo argumento
                        prazo_inicial=prazo_inicial,
                        status="Pendente"
                    )
                    if new_id:
                        saved_count += 1
                        log_action("ADD_ACTION_PLAN_ITEM", {"plan_id": new_id, "desc": desc})
            
            st.success(f"{saved_count} ação(ões) salvas com sucesso! Este alerta será removido da sua lista de pendências.")
            #st.balloons()
            import time
            time.sleep(2)
            st.rerun()


def display_incident_list(incident_manager: IncidentManager):
    """
    Exibe a lista de incidentes que AINDA NÃO foram abrangidos pela unidade do usuário.
    """
    st.title("Dashboard de Incidentes")
    st.subheader("Alertas Pendentes de Abrangência")
    
    all_incidents_df = incident_manager.get_all_incidents()
    user_unit = st.session_state.get('unit_name', 'Global')

    if all_incidents_df.empty:
        st.info("Nenhum alerta de incidente cadastrado no sistema.")
        return

    # Filtra alertas já abrangidos
    if user_unit == 'Global':
        incidents_to_show_df = all_incidents_df
        st.info("Visão de Administrador: mostrando todos os alertas globais.")
    else:
        covered_incident_ids = incident_manager.get_covered_incident_ids_for_unit(user_unit)
        incidents_to_show_df = all_incidents_df[~all_incidents_df['id'].isin(covered_incident_ids)]

    if incidents_to_show_df.empty:
        st.success(f"🎉 Todos os alertas de incidentes já foram analisados pela unidade **{user_unit}**.")
        return

    # Ordena e exibe
    try:
        incidents_to_show_df['data_evento_dt'] = pd.to_datetime(incidents_to_show_df['data_evento'], dayfirst=True)
        sorted_incidents = incidents_to_show_df.sort_values(by="data_evento_dt", ascending=False)
    except Exception:
        sorted_incidents = incidents_to_show_df

    st.write(f"Exibindo **{len(sorted_incidents)}** alerta(s) pendente(s) para a unidade **{user_unit}**.")

    cols = st.columns(3)
    for i, (_, incident) in enumerate(sorted_incidents.iterrows()):
        col = cols[i % 3]
        with col.container(border=True):
            display_url = convert_drive_url_to_displayable(incident.get('foto_url'))
            st.image(display_url, use_container_width=True)
            st.subheader(incident.get('evento_resumo'))
            st.write(incident.get('o_que_aconteceu'))
            
            if st.button("Analisar Abrangência", key=f"analisar_{incident['id']}", type="primary", use_container_width=True):
                # Chama o diálogo em vez de mudar de página
                abrangencia_dialog(incident, incident_manager)


def show_dashboard_page():
    """Ponto de entrada principal para a página do dashboard."""
    check_permission(level='viewer')
    incident_manager = get_incident_manager()
    display_incident_list(incident_manager)
