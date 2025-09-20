
import streamlit as st
import pandas as pd
from datetime import date

from auth.auth_utils import check_permission
from operations.incident_manager import IncidentManager
from gdrive.matrix_manager import MatrixManager as GlobalMatrixManager

def truncate_text(text, max_length=100):
    """Trunca o texto para um comprimento máximo e adiciona '...' se for maior."""
    if not isinstance(text, str) or len(text) <= max_length:
        return text
    return text[:max_length].rsplit(' ', 1)[0] + "..."

def display_incident_list(incident_manager: IncidentManager):
    """
    Exibe a lista de todos os incidentes em formato de cards numa grade de 3 colunas.
    """
    st.subheader("Alertas de Incidentes Globais para Abrangência")
    incidents = incident_manager.get_all_incidents()

    if incidents.empty:
        st.info("Nenhum alerta de incidente cadastrado no sistema.")
        return

    # Ordena do mais recente para o mais antigo
    incidents['data_evento'] = pd.to_datetime(incidents['data_evento'])
    sorted_incidents = incidents.sort_values(by="data_evento", ascending=False)

    cols = st.columns(3)
    for index, incident in sorted_incidents.iterrows():
        col = cols[index % 3]
        with col:
            with st.container(border=True):
                if pd.notna(incident.get('foto_url')):
                    st.image(incident['foto_url'], use_container_width=True)
                
                st.subheader(incident.get('evento_resumo', 'Título não disponível'))
                
                # Descrição curta
                descricao_curta = truncate_text(incident.get('o_que_aconteceu', ''), max_length=120)
                st.write(descricao_curta)

                # Expansor com mais detalhes
                with st.expander("➕ Saiba Mais"):
                    st.markdown("##### O que aconteceu?")
                    st.write(incident.get('o_que_aconteceu', 'Não informado.'))

                    st.markdown("##### Por que aconteceu?")
                    st.write(incident.get('por_que_aconteceu', 'Não informado.'))

                    st.markdown("##### Informações Gerais")
                    st.write(f"**Nº Alerta:** {incident.get('numero_alerta', 'N/A')}")
                    st.write(f"**Data do Evento:** {incident['data_evento'].strftime('%d/%m/%Y')}")

                st.markdown("---")
                
                # Botão para iniciar o fluxo principal
                if st.button("Analisar e Iniciar Abrangência", key=f"analisar_{incident['id']}", type="primary"):
                    st.session_state.selected_incident_id = incident['id']
                    st.rerun()

def display_incident_detail(incident_id: str, global_incident_manager: IncidentManager, unit_incident_manager: IncidentManager):
    """
    Exibe os detalhes de um único incidente e o fluxo de abrangência.
    """
    incident = global_incident_manager.get_incident_by_id(incident_id)

    if incident is None:
        st.error("Incidente não encontrado. Retornando à lista.")
        del st.session_state.selected_incident_id
        st.rerun()

    # Botão para voltar
    if st.button("← Voltar para a lista de alertas"):
        del st.session_state.selected_incident_id
        # Limpa o estado do fluxo de abrangência ao voltar
        if 'start_abrangencia' in st.session_state:
            del st.session_state.start_abrangencia
        st.rerun()

    st.header(incident.get('evento_resumo'))
    st.caption(f"Nº Alerta: {incident.get('numero_alerta', 'N/A')} | Data: {pd.to_datetime(incident.get('data_evento')).strftime('%d/%m/%Y')}")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("O que aconteceu?")
        st.markdown(incident.get('o_que_aconteceu'))
        st.subheader("Por que aconteceu?")
        st.markdown(incident.get('por_que_aconteceu'))
    with col2:
        if pd.notna(incident.get('foto_url')):
            st.image(incident.get('foto_url'), caption="Foto do incidente")
        st.link_button("Acessar Documento de Análise Completo", url=incident.get('anexos_url', ''))

    st.divider()

    # --- FLUXO DE ABRANGÊNCIA ---
    st.header("Fluxo de Abrangência")

    if 'start_abrangencia' not in st.session_state:
        st.session_state.start_abrangencia = False

    if not st.session_state.start_abrangencia:
        if st.button("Iniciar Abrangência", type="primary"):
            st.session_state.start_abrangencia = True
            st.rerun()
    
    if st.session_state.start_abrangencia:
        blocking_actions = global_incident_manager.get_blocking_actions_by_incident(incident_id)

        if blocking_actions.empty:
            st.success("Não há ações de bloqueio cadastradas para este incidente.")
            return

        st.info("Avalie cada Ação de Bloqueio abaixo e marque aquelas que são pertinentes para a sua unidade.")

        with st.form("abrangencia_form"):
            pertinent_actions = {}
            for _, action in blocking_actions.iterrows():
                action_id = action['id']
                description = action['descricao_acao']
                is_pertinent = st.toggle(f"**Ação:** {description}", key=f"toggle_{action_id}")
                if is_pertinent:
                    pertinent_actions[action_id] = description
            
            st.divider()
            st.markdown("**Preencha os detalhes para as ações marcadas como pertinentes:**")

            responsavel_email = st.text_input("E-mail do Responsável na Unidade", value=st.session_state.get('user_email', ''))
            prazo_inicial = st.date_input("Prazo para Implementação")

            submitted = st.form_submit_button("Registrar Plano de Ação de Abrangência")

            if submitted:
                if not pertinent_actions:
                    st.warning("Nenhuma ação foi marcada como pertinente. Nada foi salvo.")
                elif not responsavel_email or not prazo_inicial:
                    st.error("O e-mail do responsável e o prazo são obrigatórios.")
                else:
                    saved_count = 0
                    with st.spinner("Salvando plano de ação na planilha da sua unidade..."):
                        for action_id, desc in pertinent_actions.items():
                            new_id = unit_incident_manager.add_abrangencia_action(
                                id_acao_bloqueio=action_id,
                                unidade_operacional=st.session_state.get('unit_name', 'N/A'),
                                responsavel_email=responsavel_email,
                                prazo_inicial=prazo_inicial,
                                status="Pendente"
                            )
                            if new_id:
                                saved_count += 1
                    
                    if saved_count == len(pertinent_actions):
                        st.success(f"{saved_count} ação(ões) de abrangência foram salvas com sucesso no plano de ação da sua unidade!")
                        # Limpa o estado para finalizar o fluxo
                        del st.session_state.start_abrangencia
                        del st.session_state.selected_incident_id
                    else:
                        st.error("Ocorreu um erro ao salvar algumas ou todas as ações. Verifique a planilha.")

# --- PONTO DE ENTRADA DA PÁGINA ---
def show_dashboard_page():
    # Verifica se o usuário tem permissão para ver a página
    if not check_permission(level='viewer'):
        st.stop()

    # Verifica se os managers da unidade foram inicializados (garante que o login foi feito)
    if not st.session_state.get('managers_initialized'):
        st.warning("Selecione uma unidade operacional para visualizar o dashboard.")
        st.stop()
    
    # --- LÓGICA DE NAVEGAÇÃO (DETALHE vs. LISTA) ---
    # Se um incidente foi selecionado para análise, mostra a tela de detalhes
    if 'selected_incident_id' in st.session_state:
        # Inicialização dos managers movida para dentro do if para garantir que só rodem quando necessário
        try:
            global_matrix_manager = GlobalMatrixManager()
            matrix_spreadsheet_id = global_matrix_manager.spreadsheet.id
            global_incident_manager = IncidentManager(matrix_spreadsheet_id)

            unit_spreadsheet_id = st.session_state.get('spreadsheet_id')
            unit_incident_manager = IncidentManager(unit_spreadsheet_id)
        except Exception as e:
            st.error(f"Erro ao inicializar os gerenciadores de dados: {e}")
            st.stop()
        
        display_incident_detail(st.session_state.selected_incident_id, global_incident_manager, unit_incident_manager)
    # Senão, mostra a lista de cards de incidentes
    else:
        try:
            global_matrix_manager = GlobalMatrixManager()
            matrix_spreadsheet_id = global_matrix_manager.spreadsheet.id
            global_incident_manager = IncidentManager(matrix_spreadsheet_id)
        except Exception as e:
            st.error(f"Erro ao inicializar o gerenciador de incidentes globais: {e}")
            st.stop()

        display_incident_list(global_incident_manager)
