
import streamlit as st
import pandas as pd
from datetime import datetime
from gdrive.matrix_manager import get_matrix_manager
from operations.incident_manager import get_incident_manager
from auth.auth_utils import check_permission
from gdrive.google_api_manager import GoogleApiManager
from operations.audit_logger import log_action
from AI.api_Operation import PDFQA

# --- LÓGICA DE NEGÓCIO PARA CADASTRO DE INCIDENTE ---

def analyze_incident_document(attachment_file, photo_file, alert_number):
    """
    Orquestra a análise com IA e faz o upload dos arquivos para as pastas corretas:
    - Foto vai para a pasta de imagens públicas.
    - Anexo vai para a pasta de documentos restritos.
    """
    st.session_state.processing = True
    st.session_state.error = None
    st.session_state.analysis_complete = False

    try:
        with st.spinner("Analisando documento com IA e fazendo upload dos arquivos..."):
            # 1. Análise com IA
            api_op = PDFQA()
            prompt = """
            Você é um especialista em análise de incidentes de segurança. Extraia as seguintes informações do documento e retorne um JSON.
            - evento_resumo: Um título curto e informativo para o evento (ex: "Princípio de incêndio no laboratório").
            - data_evento: A data de emissão do alerta, no formato YYYY-MM-DD.
            - o_que_aconteceu: O parágrafo completo da seção "O que aconteceu?".
            - por_que_aconteceu: O parágrafo completo da seção "Por que aconteceu?".
            - recomendacoes: Uma lista de strings, onde cada string é um item da seção "O que fazer para evitar?".
            Responda APENAS com o bloco de código JSON.
            """
            analysis_result, _ = api_op.answer_question(
                files=[attachment_file],
                question=prompt,
                task_type='extraction'
            )
            if not isinstance(analysis_result, dict) or not analysis_result.get('recomendacoes'):
                raise ValueError("A análise da IA falhou ou não retornou o formato JSON esperado com recomendações.")

            # 2. Upload para pastas separadas no Google Drive
            from gdrive.config import PUBLIC_IMAGES_FOLDER_ID, RESTRICTED_ATTACHMENTS_FOLDER_ID
            api_manager = GoogleApiManager()

            safe_alert_number = "".join(c for c in alert_number if c.isalnum() or c in ('-','_')).rstrip()

            # Upload da foto para a pasta PÚBLICA
            photo_url = api_manager.upload_file(
                PUBLIC_IMAGES_FOLDER_ID, 
                photo_file, 
                f"foto_{safe_alert_number}.jpg"
            )
            
            # Upload do anexo para a pasta RESTRITA
            anexos_url = api_manager.upload_file(
                RESTRICTED_ATTACHMENTS_FOLDER_ID, 
                attachment_file, 
                f"anexo_{safe_alert_number}_{attachment_file.name}"
            )

            if not photo_url or not anexos_url:
                raise ConnectionError("Falha no upload de um ou mais arquivos para o Google Drive.")

            # 3. Armazena tudo no estado da sessão
            st.session_state.incident_data_for_confirmation = {
                **analysis_result,
                "numero_alerta": alert_number,
                "foto_url": photo_url,
                "anexos_url": anexos_url,
                "photo_bytes": photo_file.getvalue()
            }
            st.session_state.analysis_complete = True
            log_action("AI_ANALYSIS_SUCCESS", {"alert_number": alert_number})

    except Exception as e:
        st.session_state.error = f"Ocorreu um erro durante o processamento: {e}"
        log_action("AI_ANALYSIS_FAILURE", {"alert_number": alert_number, "error": str(e)})
    finally:
        st.session_state.processing = False
        
# --- COMPONENTES DA UI ---

def display_incident_registration_tab():
    """
    Renderiza a interface da aba para cadastrar um novo alerta de incidente.
    """
    st.header("Cadastrar Novo Alerta de Incidente")

    # Passo 1: Formulário de Upload
    with st.form("new_incident_form"):
        st.markdown("**1. Forneça os arquivos e informações iniciais**")
        alert_number = st.text_input("Número do Alerta", help="Ex: ALERTA-2025-01")
        attachment_file = st.file_uploader("Documento de Análise (PDF)", type="pdf")
        photo_file = st.file_uploader("Foto do Incidente (JPG/PNG)", type=["jpg", "png"])
        
        submitted = st.form_submit_button("Analisar e Fazer Upload", type="primary")

        if submitted:
            if not all([alert_number, attachment_file, photo_file]):
                st.warning("Por favor, preencha todos os campos e anexe os arquivos.")
            else:
                analyze_incident_document(attachment_file, photo_file, alert_number)
    
    if st.session_state.get('error'):
        st.error(st.session_state.error)

    # Passo 2: Formulário de Confirmação
    if st.session_state.get('analysis_complete'):
        st.divider()
        st.subheader("2. Revise os dados extraídos pela IA e confirme")
        data = st.session_state.incident_data_for_confirmation

        with st.form("confirm_incident_form"):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(data['photo_bytes'], caption="Foto do Incidente", width='stretch')
            
            with col2:
                edited_evento_resumo = st.text_input("Resumo do Evento", value=data.get('evento_resumo', ''))
                try:
                    default_date = datetime.strptime(data.get('data_evento'), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    default_date = None
                edited_data_evento = st.date_input("Data do Evento", value=default_date)

            edited_o_que_aconteceu = st.text_area("O que aconteceu?", value=data.get('o_que_aconteceu', ''), height=150)
            edited_por_que_aconteceu = st.text_area("Por que aconteceu?", value=data.get('por_que_aconteceu', ''), height=150)
            
            st.markdown("##### Recomendações / Ações de Bloqueio Sugeridas")
            recomendacoes_df = pd.DataFrame(data.get('recomendacoes', []), columns=["Descrição da Ação"])
            edited_recomendacoes = st.data_editor(recomendacoes_df, num_rows="dynamic", use_container_width=True)

            confirm_button = st.form_submit_button("Confirmar e Salvar Alerta Completo")

            if confirm_button:
                if not all([edited_evento_resumo, edited_data_evento, edited_o_que_aconteceu]) or edited_recomendacoes.empty:
                    st.error("Todos os campos de texto e a lista de recomendações devem ser preenchidos.")
                else:
                    with st.spinner("Salvando na Planilha Matriz..."):
                        incident_manager = get_incident_manager()
                        
                        new_incident_id = incident_manager.add_incident(
                            numero_alerta=data['numero_alerta'],
                            evento_resumo=edited_evento_resumo,
                            data_evento=edited_data_evento,
                            o_que_aconteceu=edited_o_que_aconteceu,
                            por_que_aconteceu=edited_por_que_aconteceu,
                            foto_url=data['foto_url'],
                            anexos_url=data['anexos_url']
                        )

                        if new_incident_id:
                            recomendacoes_list = edited_recomendacoes["Descrição da Ação"].tolist()
                            success_actions = incident_manager.add_blocking_actions_batch(new_incident_id, recomendacoes_list)
                            
                            if success_actions:
                                st.success(f"Alerta '{edited_evento_resumo}' salvo com sucesso!")
                                log_action("REGISTER_INCIDENT", {"incident_id": new_incident_id, "alert_number": data['numero_alerta']})
                                for key in ['analysis_complete', 'incident_data_for_confirmation', 'error', 'processing']:
                                    if key in st.session_state:
                                        del st.session_state[key]
                                st.rerun()
                            else:
                                st.error("O incidente foi salvo, mas falhou ao salvar as recomendações.")
                                log_action("REGISTER_INCIDENT_ACTIONS_FAILURE", {"incident_id": new_incident_id})
                        else:
                            st.error("Falha ao salvar o alerta na planilha.")
                            log_action("REGISTER_INCIDENT_FAILURE", {"alert_number": data['numero_alerta']})

@st.dialog("Gerenciar Usuário")
def user_dialog(user_data=None):
    """Renderiza um diálogo modal para adicionar ou editar um usuário."""
    is_edit_mode = user_data is not None
    title = "Editar Usuário" if is_edit_mode else "Adicionar Novo Usuário"
    st.subheader(title)

    matrix_manager = get_matrix_manager()
    unit_names = ["*"] + matrix_manager.get_all_units()

    with st.form("user_form"):
        email = st.text_input("E-mail", value=user_data['email'] if is_edit_mode else "", disabled=is_edit_mode)
        nome = st.text_input("Nome", value=user_data['nome'] if is_edit_mode else "")
        
        roles = ["admin", "editor", "viewer"]
        current_role_index = roles.index(user_data['role']) if is_edit_mode and user_data.get('role') in roles else 2
        role = st.selectbox("Papel (Role)", roles, index=current_role_index)
        
        current_unit_index = unit_names.index(user_data['unidade_associada']) if is_edit_mode and user_data.get('unidade_associada') in unit_names else 0
        unidade_associada = st.selectbox("Unidade Associada", unit_names, index=current_unit_index, help="Selecione '*' para acesso global (administradores).")

        if st.form_submit_button("Salvar"):
            if not email or not nome:
                st.error("E-mail e Nome são obrigatórios.")
                return

            if is_edit_mode:
                updates = {"nome": nome, "role": role, "unidade_associada": unidade_associada}
                if matrix_manager.update_user(user_data['email'], updates):
                    st.success("Usuário atualizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Falha ao atualizar usuário.")
            else:
                if matrix_manager.get_user_info(email):
                    st.error(f"O e-mail '{email}' já está cadastrado.")
                else:
                    new_user_data = [email, nome, role, unidade_associada]
                    if matrix_manager.add_user(new_user_data):
                        st.success(f"Usuário '{nome}' adicionado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Falha ao adicionar usuário.")

# --- PÁGINA PRINCIPAL ---

def show_admin_page():
    check_permission(level='admin')
    
    st.title("🚀 Painel de Administração")

    if st.session_state.get('unit_name') != 'Global':
        st.error("Acesso restrito ao Administrador Global.")
        st.stop()
    
   
    tab_incident, tab_users, tab_requests, tab_logs = st.tabs([
    "Cadastrar Alerta", "Gerenciar Usuários", "Solicitações de Acesso", "Logs de Auditoria"
])

    with tab_incident:
        display_incident_registration_tab()

    with tab_users:
        st.header("Gerenciar Usuários do Sistema")
        matrix_manager = get_matrix_manager()

        if st.button("➕ Adicionar Novo Usuário"):
            user_dialog()

        all_users_df = matrix_manager.get_all_users_df()
        if not all_users_df.empty:
            st.write("Clique em uma linha para editar ou remover um usuário.")
            
            selected_user = st.dataframe(
                all_users_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            if selected_user.selection.rows:
                selected_index = selected_user.selection.rows[0]
                user_to_manage = all_users_df.iloc[selected_index].to_dict()
                
                st.subheader(f"Ações para: {user_to_manage['nome']}")
                col1, col2 = st.columns(2)
                if col1.button("✏️ Editar Usuário", use_container_width=True):
                    user_dialog(user_to_manage)
                if col2.button("🗑️ Remover Usuário", type="primary", use_container_width=True):
                    if matrix_manager.remove_user(user_to_manage['email']):
                        st.success(f"Usuário '{user_to_manage['email']}' removido.")
                        st.rerun()
                    else:
                        st.error("Falha ao remover usuário.")
        else:
            st.info("Nenhum usuário cadastrado.")

    with tab_logs:
        st.header("📜 Logs de Auditoria do Sistema")
        matrix_manager = get_matrix_manager()
        logs_df = matrix_manager.get_audit_logs()
        if not logs_df.empty:
            st.dataframe(
                logs_df.sort_values(by='timestamp', ascending=False),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Nenhum registro de log encontrado.")

    with tab_requests:
        st.header("Solicitações de Acesso Pendentes")
        matrix_manager = get_matrix_manager()
        pending_requests_df = matrix_manager.get_pending_access_requests()
    
        if pending_requests_df.empty:
            st.info("Nenhuma solicitação de acesso pendente no momento.")
        else:
            st.write("Aprove ou rejeite os novos usuários.")
            
            for index, row in pending_requests_df.iterrows():
                with st.container(border=True):
                    col1, col2, col3, col_approve, col_reject = st.columns([2.5, 2, 1.5, 1, 1])
                    col1.text_input("E-mail", value=row['email'], disabled=True, key=f"email_{index}")
                    col2.text_input("Unidade", value=row['unidade_solicitada'], disabled=True, key=f"unit_{index}")
                    
                    role_to_assign = col3.selectbox(
                        "Definir Papel",
                        options=["viewer", "editor", "admin"],
                        index=0, 
                        key=f"role_{index}"
                    )
                    
                    if col_approve.button("Aprovar", key=f"approve_{index}", type="primary", use_container_width=True):
                        with st.spinner(f"Aprovando {row['email']}..."):
                            if matrix_manager.approve_access_request(row['email'], role_to_assign):
                                st.success(f"Usuário {row['email']} aprovado!")
                                st.rerun()
                            else:
                                st.error(f"Falha ao aprovar {row['email']}.")
                    
                    if col_reject.button("Rejeitar", key=f"reject_{index}", use_container_width=True):
                        with st.spinner(f"Rejeitando {row['email']}..."):
                            if matrix_manager.reject_access_request(row['email']):
                                st.warning(f"Solicitação de {row['email']} rejeitada.")
                                st.rerun()
                            else:
                                st.error(f"Falha ao rejeitar {row['email']}.")
