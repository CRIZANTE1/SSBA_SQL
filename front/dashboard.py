# front/dashboard.py

import streamlit as st
import pandas as pd
from datetime import date, datetime
from auth.auth_utils import check_permission
from operations.incident_manager import get_incident_manager, IncidentManager
from operations.audit_logger import log_action
from gdrive.matrix_manager import get_matrix_manager

def convert_drive_url_to_displayable(url: str) -> str | None:
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
    Renderiza um diálogo modal com um formulário dinâmico, permitindo a atribuição
    de responsáveis e prazos individuais para cada ação selecionada.
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

    st.subheader("Selecione as ações aplicáveis e defina os responsáveis")
    st.info("Ative uma ação no seletor à esquerda para habilitar os campos e incluí-la no plano.")

    with st.form("abrangencia_dialog_form_individual"):
        # Lógica para Admin Global selecionar a UO (permanece a mesma)
        is_admin = st.session_state.get('unit_name') == 'Global'
        target_unit_name = None
        if is_admin:
            matrix_manager = get_matrix_manager()
            all_units = matrix_manager.get_all_units()
            options = ["-- Digitar nome da UO --"] + all_units
            chosen_option = st.selectbox("Selecione a Unidade Operacional (UO) de destino", options=options)
            if chosen_option == "-- Digitar nome da UO --":
                target_unit_name = st.text_input("Digite o nome da UO", key="new_uo_input")
            else:
                target_unit_name = chosen_option
        
        st.markdown("---")

        # Loop para renderizar o formulário dinâmico
        for _, action in blocking_actions.iterrows():
            action_id = action['id']
            
            col_toggle, col_resp, col_co_resp, col_prazo = st.columns([2, 1.5, 1.5, 1])

            with col_toggle:
                is_pertinent = st.toggle(action['descricao_acao'], key=f"toggle_{action_id}")
            
            with col_resp:
                st.text_input(
                    "Responsável", 
                    value=st.session_state.get('user_info', {}).get('email', ''),
                    key=f"resp_{action_id}",
                    disabled=not is_pertinent,
                    label_visibility="collapsed"
                )
            with col_co_resp:
                st.text_input(
                    "Co-responsável",
                    placeholder="Co-responsável (Opcional)",
                    key=f"co_resp_{action_id}",
                    disabled=not is_pertinent,
                    label_visibility="collapsed"
                )
            with col_prazo:
                st.date_input(
                    "Prazo",
                    min_value=date.today(),
                    key=f"prazo_{action_id}",
                    disabled=not is_pertinent,
                    label_visibility="collapsed"
                )
            st.divider()

        submitted = st.form_submit_button("Registrar Plano de Ação", type="primary")

        if submitted:
            # Lógica de processamento pós-submissão
            unit_to_save = target_unit_name if is_admin else st.session_state.unit_name
            if is_admin and (not unit_to_save or not unit_to_save.strip()):
                st.error("Administrador: Por favor, selecione ou digite o nome da Unidade Operacional.")
                return

            actions_to_save = []
            validation_passed = True
            # Loop para coletar dados das ações selecionadas
            for _, action in blocking_actions.iterrows():
                action_id = action['id']
                if st.session_state[f"toggle_{action_id}"]:
                    responsavel = st.session_state[f"resp_{action_id}"]
                    co_responsavel = st.session_state[f"co_resp_{action_id}"]
                    prazo = st.session_state[f"prazo_{action_id}"]
                    
                    if not responsavel or not prazo:
                        st.error(f"Ação selecionada '{action['descricao_acao']}' está sem Responsável ou Prazo preenchido.")
                        validation_passed = False
                        break
                    
                    actions_to_save.append({
                        "id_acao_bloqueio": action_id,
                        "descricao": action['descricao_acao'],
                        "unidade_operacional": unit_to_save,
                        "responsavel_email": responsavel,
                        "co_responsavel_email": co_responsavel,
                        "prazo_inicial": prazo
                    })

            if not validation_passed:
                return

            if not actions_to_save:
                st.warning("Nenhuma ação foi selecionada. Ative o seletor de uma ou mais ações para salvar.")
                return

            saved_count = 0
            with st.spinner(f"Salvando {len(actions_to_save)} ação(ões) para a UO: {unit_to_save}..."):
                for action_data in actions_to_save:
                    new_id = incident_manager.add_abrangencia_action(
                        id_acao_bloqueio=action_data['id_acao_bloqueio'],
                        unidade_operacional=action_data['unidade_operacional'],
                        responsavel_email=action_data['responsavel_email'],
                        co_responsavel_email=action_data['co_responsavel_email'],
                        prazo_inicial=action_data['prazo_inicial'],
                        status="Pendente"
                    )
                    if new_id:
                        saved_count += 1
                        log_action("ADD_ACTION_PLAN_ITEM", {"plan_id": new_id, "desc": action_data['descricao'], "target_unit": unit_to_save})
            
            st.success(f"{saved_count} ação(ões) salvas com sucesso!")
            st.balloons()
            import time
            time.sleep(2)
            st.rerun()

def render_incident_card(incident, col, incident_manager, is_pending):
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
    st.title("Dashboard de Incidentes")
    user_unit = st.session_state.get('unit_name', 'Global')
    matrix_manager = get_matrix_manager()
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
    check_permission(level='viewer')
    incident_manager = get_incident_manager()
    display_incident_list(incident_manager)
