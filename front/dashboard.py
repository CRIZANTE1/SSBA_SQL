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
    return text[:max_length].rsplit(' ', 1)[0] + "..."

def display_incident_list(incident_manager: IncidentManager):
    """
    Exibe a lista de incidentes que AINDA NÃO foram abrangidos pela unidade do usuário.
    """
    st.subheader("Alertas de Incidentes Pendentes de Abrangência")
    
    all_incidents_df = incident_manager.get_all_incidents()
    user_unit = st.session_state.get('unit_name', 'Global')

    if all_incidents_df.empty:
        st.info("Nenhum alerta de incidente cadastrado no sistema.")
        return

    # <<< MUDANÇA IMPORTANTE: Lógica para filtrar alertas já abrangidos >>>
    # Se o usuário for global (admin), ele vê todos os alertas.
    if user_unit == 'Global':
        incidents_to_show_df = all_incidents_df
        st.info("Visão de Administrador: mostrando todos os alertas globais.")
    else:
        # Pega os IDs dos incidentes que a unidade do usuário já abrangiu.
        covered_incident_ids = incident_manager.get_covered_incident_ids_for_unit(user_unit)
        
        if not covered_incident_ids:
            # Se a unidade ainda não abrangiu nenhum, mostra todos.
            incidents_to_show_df = all_incidents_df
        else:
            # Filtra o DataFrame para excluir os incidentes cujos IDs estão na lista de abrangidos.
            incidents_to_show_df = all_incidents_df[~all_incidents_df['id'].isin(covered_incident_ids)]

    if incidents_to_show_df.empty:
        st.success(f"🎉 Todos os alertas de incidentes já foram analisados pela unidade **{user_unit}**.")
        return

    # Garante que a coluna de data esteja no formato correto e ordena
    try:
        incidents_to_show_df['data_evento_dt'] = pd.to_datetime(incidents_to_show_df['data_evento'], dayfirst=True)
        sorted_incidents = incidents_to_show_df.sort_values(by="data_evento_dt", ascending=False)
    except Exception:
        sorted_incidents = incidents_to_show_df

    st.write(f"Exibindo **{len(sorted_incidents)}** alerta(s) pendente(s) para a unidade **{user_unit}**.")

    cols = st.columns(3)
    for i, (_, incident) in enumerate(sorted_incidents.iterrows()):
        col = cols[i % 3]
        with col:
            with st.container(border=True):
                if pd.notna(incident.get('foto_url')):
                    st.image(incident['foto_url'], use_container_width=True, caption=f"Alerta: {incident.get('numero_alerta')}")
                else:
                    st.subheader(f"Alerta: {incident.get('numero_alerta')}")
                
                st.subheader(incident.get('evento_resumo', 'Título Indisponível'))
                st.write(truncate_text(incident.get('o_que_aconteceu', '')))

                with st.expander("➕ Ver Detalhes"):
                    st.markdown("##### O que aconteceu?")
                    st.write(incident.get('o_que_aconteceu', 'Não informado.'))
                    st.markdown("##### Por que aconteceu?")
                    st.write(incident.get('por_que_aconteceu', 'Não informado.'))
                    data_evento_str = incident['data_evento_dt'].strftime('%d/%m/%Y') if 'data_evento_dt' in incident else incident.get('data_evento', 'N/A')
                    st.markdown(f"**Data do Evento:** {data_evento_str}")

                st.divider()
                
                if st.button("Analisar Abrangência", key=f"analisar_{incident['id']}", type="primary", use_container_width=True):
                    st.session_state.selected_incident_id = incident['id']
                    st.rerun()

def display_incident_detail(incident_id: str, incident_manager: IncidentManager):
    """
    Exibe os detalhes de um incidente selecionado e o formulário para o plano de ação de abrangência.
    (Esta função permanece praticamente a mesma)
    """
    incident = incident_manager.get_incident_by_id(incident_id)

    if incident is None:
        st.error("Incidente não encontrado. Retornando à lista.")
        if 'selected_incident_id' in st.session_state:
            del st.session_state.selected_incident_id
        st.rerun()

    if st.button("← Voltar para a lista de alertas pendentes"):
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

        responsavel_email = st.text_input("E-mail do Responsável", value=st.session_state.get('user_info', {}).get('email', ''))
        prazo_inicial = st.date_input("Prazo para Implementação", min_value=date.today())

        submitted = st.form_submit_button("Registrar Plano de Ação", type="primary")

        if submitted:
            # <<< MUDANÇA IMPORTANTE: Mesmo que nenhuma ação seja pertinente, registramos a análise. >>>
            # Se o usuário não marcou nenhuma ação, podemos adicionar um registro especial ou simplesmente considerar a análise concluída.
            # A abordagem mais simples é: se ele submeteu o formulário (mesmo que vazio), ele analisou.
            # A lógica de `get_covered_incident_ids_for_unit` já cobre isso: se pelo menos UMA ação for salva, o incidente some da lista.
            if not pertinent_actions:
                st.warning("Nenhuma ação foi marcada como aplicável. Para registrar que este alerta foi analisado, ao menos uma ação deve ser selecionada. Se nenhuma for aplicável, contate o administrador.")
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
                
                if error_count == 0 and saved_count > 0:
                    st.success(f"{saved_count} ação(ões) de abrangência foram salvas! Este alerta não aparecerá mais na sua lista de pendências.")
                    del st.session_state.selected_incident_id 
                    st.rerun()
                elif error_count > 0:
                     st.error(f"Ocorreu um erro. {saved_count} ações salvas, {error_count} falharam.")

def show_dashboard_page():
    check_permission(level='viewer')

    incident_manager = get_incident_manager()

    if 'selected_incident_id' in st.session_state:
        display_incident_detail(st.session_state.selected_incident_id, incident_manager)
    else:
        st.title("Dashboard de Incidentes")
        display_incident_list(incident_manager)
