import streamlit as st
import pandas as pd
from datetime import date
from auth.auth_utils import check_permission
from operations.incident_manager import get_incident_manager, IncidentManager
from operations.audit_logger import log_action

def truncate_text(text, max_length=120):
    """Trunca o texto para um comprimento máximo e adiciona '...' se necessário."""
    if not isinstance(text, str) or len(text) <= max_length:
        return text
    # Tenta cortar na última palavra para não quebrar no meio de uma
    return text[:max_length].rsplit(' ', 1)[0] + "..."

def display_incident_list(incident_manager: IncidentManager):
    """
    Exibe a lista de todos os incidentes em formato de cards.
    """
    st.subheader("Alertas de Incidentes Globais para Abrangência")
    incidents_df = incident_manager.get_all_incidents()

    if incidents_df.empty:
        st.info("Nenhum alerta de incidente cadastrado no sistema.")
        return

    # Garante que a coluna de data esteja no formato correto e ordena
    try:
        incidents_df['data_evento_dt'] = pd.to_datetime(incidents_df['data_evento'], dayfirst=True)
        sorted_incidents = incidents_df.sort_values(by="data_evento_dt", ascending=False)
    except Exception:
        st.warning("Não foi possível ordenar os incidentes por data devido a formatos inconsistentes.")
        sorted_incidents = incidents_df

    cols = st.columns(3)
    for i, (_, incident) in enumerate(sorted_incidents.iterrows()):
        col = cols[i % 3]
        with col:
            with st.container(border=True):
                # Imagem do incidente, se disponível
                if pd.notna(incident.get('foto_url')):
                    st.image(incident['foto_url'], use_container_width=True, caption=f"Alerta: {incident.get('numero_alerta')}")
                else:
                    st.subheader(f"Alerta: {incident.get('numero_alerta')}")
                
                st.subheader(incident.get('evento_resumo', 'Título Indisponível'))
                
                # Descrição curta com link para mais detalhes
                descricao_curta = truncate_text(incident.get('o_que_aconteceu', ''))
                st.write(descricao_curta)

                # Expansor com todos os detalhes
                with st.expander("➕ Ver Detalhes"):
                    st.markdown("##### O que aconteceu?")
                    st.write(incident.get('o_que_aconteceu', 'Não informado.'))
                    st.markdown("##### Por que aconteceu?")
                    st.write(incident.get('por_que_aconteceu', 'Não informado.'))
                    data_evento_str = incident['data_evento_dt'].strftime('%d/%m/%Y') if 'data_evento_dt' in incident else incident.get('data_evento', 'N/A')
                    st.markdown(f"**Data do Evento:** {data_evento_str}")

                st.divider()
                
                # Botão para iniciar o fluxo de análise
                if st.button("Analisar Abrangência", key=f"analisar_{incident['id']}", type="primary", use_container_width=True):
                    st.session_state.selected_incident_id = incident['id']
                    st.rerun()

def display_incident_detail(incident_id: str, incident_manager: IncidentManager):
    """
    Exibe os detalhes de um incidente selecionado e o formulário para o plano de ação de abrangência.
    """
    incident = incident_manager.get_incident_by_id(incident_id)

    if incident is None:
        st.error("Incidente não encontrado. Retornando à lista.")
        if 'selected_incident_id' in st.session_state:
            del st.session_state.selected_incident_id
        st.rerun()

    # --- Cabeçalho e Detalhes do Incidente ---
    if st.button("← Voltar para a lista de alertas"):
        del st.session_state.selected_incident_id
        st.rerun()

    st.title(incident.get('evento_resumo'))
    data_evento_str = pd.to_datetime(incident.get('data_evento'), dayfirst=True).strftime('%d/%m/%Y')
    st.caption(f"Nº Alerta: {incident.get('numero_alerta', 'N/A')} | Data do Evento: {data_evento_str}")
    st.divider()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Descrição do Evento")
        st.markdown(f"**O que aconteceu?**\n\n{incident.get('o_que_aconteceu')}")
        st.markdown(f"**Por que aconteceu?**\n\n{incident.get('por_que_aconteceu')}")
    with col2:
        if pd.notna(incident.get('foto_url')):
            st.image(incident.get('foto_url'), caption="Foto do incidente")
        if pd.notna(incident.get('anexos_url')):
            st.link_button("Acessar Documento de Análise", url=incident.get('anexos_url'), use_container_width=True)

    st.divider()

    # --- Formulário de Abrangência ---
    st.header("Análise e Plano de Ação de Abrangência")
    blocking_actions = incident_manager.get_blocking_actions_by_incident(incident_id)

    if blocking_actions.empty:
        st.success("Não há ações de bloqueio cadastradas para este incidente.")
        return

    st.info(f"Avalie cada Ação de Bloqueio abaixo e marque aquelas que são aplicáveis para a sua unidade: **{st.session_state.unit_name}**.")

    with st.form("abrangencia_form"):
        pertinent_actions = {}
        for _, action in blocking_actions.iterrows():
            action_id = action['id']
            description = action['descricao_acao']
            is_pertinent = st.toggle(f"**Ação:** {description}", key=f"toggle_{action_id}")
            if is_pertinent:
                pertinent_actions[action_id] = description
        
        st.divider()
        st.markdown("**Preencha os detalhes para as ações marcadas como aplicáveis:**")

        responsavel_email = st.text_input("E-mail do Responsável", value=get_user_email())
        prazo_inicial = st.date_input("Prazo para Implementação", min_value=date.today())

        submitted = st.form_submit_button("Registrar Plano de Ação", type="primary")

        if submitted:
            if not pertinent_actions:
                st.warning("Nenhuma ação foi marcada como aplicável. Nada foi salvo.")
            elif not responsavel_email or not prazo_inicial:
                st.error("O e-mail do responsável e o prazo são obrigatórios.")
            else:
                saved_count = 0
                error_count = 0
                with st.spinner("Salvando plano de ação..."):
                    for action_id, desc in pertinent_actions.items():
                        new_id = incident_manager.add_abrangencia_action(
                            id_acao_bloqueio=action_id,
                            unidade_operacional=st.session_state.unit_name,
                            responsavel_email=responsavel_email,
                            prazo_inicial=prazo_inicial,
                            status="Pendente"
                        )
                        if new_id:
                            saved_count += 1
                            log_action("ADD_ACTION_PLAN_ITEM", {"plan_id": new_id, "action_desc": desc})
                        else:
                            error_count += 1
                
                if error_count == 0:
                    st.success(f"{saved_count} ação(ões) de abrangência foram salvas com sucesso no plano de ação!")
                    del st.session_state.selected_incident_id # Retorna à lista principal
                    st.rerun()
                else:
                    st.error(f"Ocorreu um erro. {saved_count} ações salvas, {error_count} falharam.")

# --- PONTO DE ENTRADA DA PÁGINA ---
def show_dashboard_page():
    check_permission(level='viewer')

    incident_manager = get_incident_manager()

    # Lógica de navegação: mostra a lista de incidentes ou os detalhes de um específico.
    if 'selected_incident_id' in st.session_state:
        display_incident_detail(st.session_state.selected_incident_id, incident_manager)
    else:
        st.title("Dashboard de Incidentes")
        display_incident_list(incident_manager)
