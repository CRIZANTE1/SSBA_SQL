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
        return None # Retorna None se a URL for inválida
    
    try:
        # Extrai o ID do arquivo de diferentes formatos de URL
        if '/d/' in url:
            file_id = url.split('/d/')[1].split('/')[0]
        elif 'id=' in url:
            file_id = url.split('id=')[1].split('&')[0]
        else:
            return None # Formato de URL não reconhecido

        # Retorna a URL no formato de thumbnail
        return f'https://drive.google.com/thumbnail?id={file_id}'
    
    except IndexError:
        # Se a extração do ID falhar
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

    # Detalhes do incidente
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
        # --- LÓGICA CONDICIONAL PARA O ADMIN GLOBAL ---
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
            # Para usuários normais, a UO é a sua própria, sem opção de escolha.
            st.markdown(f"**Unidade Operacional:** `{st.session_state.unit_name}`")
        # --- FIM DA LÓGICA CONDICIONAL ---

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
            # Define qual nome de unidade será salvo
            if is_admin:
                unit_to_save = target_unit_name
                if not unit_to_save or not unit_to_save.strip():
                    st.error("Administrador: Por favor, selecione ou digite o nome da Unidade Operacional.")
                    return
            else:
                unit_to_save = st.session_state.unit_name

            if not pertinent_actions:
                st.warning("Nenhuma ação foi selecionada. Para concluir a análise, selecione ao menos uma ação aplicável.")
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

    if user_unit == 'Global':
        incidents_to_show_df = all_incidents_df
        st.info("Visão de Administrador: mostrando todos os alertas globais.")
    else:
        covered_incident_ids = incident_manager.get_covered_incident_ids_for_unit(user_unit)
        incidents_to_show_df = all_incidents_df[~all_incidents_df['id'].isin(covered_incident_ids)]

    if incidents_to_show_df.empty:
        st.success(f"🎉 Todos os alertas de incidentes já foram analisados pela unidade **{user_unit}**.")
        return

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
            
            foto_url = incident.get('foto_url')

            if pd.notna(foto_url) and isinstance(foto_url, str) and foto_url.strip():
                display_url = convert_drive_url_to_displayable(foto_url)
                if display_url:
                    st.image(display_url, use_container_width=True)
                else:
                    st.caption("Imagem não disponível ou URL inválida")
            else:
                st.markdown(f"#### Alerta: {incident.get('numero_alerta')}")
                st.caption("Sem imagem anexada")

            st.subheader(incident.get('evento_resumo'))
            st.write(incident.get('o_que_aconteceu'))
            
            if st.button("Analisar Abrangência", key=f"analisar_{incident['id']}", type="primary", use_container_width=True):
                abrangencia_dialog(incident, incident_manager)


def show_dashboard_page():
    """Ponto de entrada principal para a página do dashboard."""
    check_permission(level='viewer')
    incident_manager = get_incident_manager()
    display_incident_list(incident_manager)
