
import streamlit as st
import pandas as pd
from datetime import datetime

from gdrive.matrix_manager import MatrixManager as GlobalMatrixManager
from operations.incident_manager import IncidentManager as GlobalIncidentManager
from auth.auth_utils import check_permission
from gdrive.google_api_manager import GoogleApiManager
from operations.audit_logger import log_action
from AI.api_Operation import PDFQA

# --- FUNÇÕES DE LÓGICA PARA O NOVO FLUXO DE INCIDENTES ---

def analyze_incident_document(attachment_file, photo_file, alert_number):
    """
    Orquestra a análise do documento de incidente com IA e o upload de arquivos.
    """
    st.session_state.processing = True
    st.session_state.error = None
    st.session_state.analysis_complete = False

    try:
        with st.spinner("Analisando documento com IA e fazendo upload dos arquivos..."):
            # 1. Análise com IA
            api_op = PDFQA()
            prompt = f"""
            Você é um especialista em análise de incidentes de segurança. Extraia as seguintes informações do documento em anexo e retorne um JSON.

            - evento_resumo: Um título curto e informativo para o evento (ex: "Tombamento de caminhão em mina").
            - data_evento: A data em que o evento ocorreu, no formato YYYY-MM-DD.
            - o_que_aconteceu: Um parágrafo detalhado descrevendo o que aconteceu.
            - por_que_aconteceu: Um parágrafo descrevendo as causas fundamentais do incidente.
            - recomendacoes: Uma lista de strings, onde cada string é uma ação de bloqueio ou recomendação específica para evitar a recorrência deste incidente.

            Exemplo de JSON de saída:
            {{
                "evento_resumo": "Tombamento de caminhão em mina",
                "data_evento": "2025-09-20",
                "o_que_aconteceu": "O caminhão modelo X tombou durante a subida da rampa Y.",
                "por_que_aconteceu": "A rampa estava com inclinação acima do recomendado e havia óleo na pista.",
                "recomendacoes": [
                    "Revisar e corrigir a inclinação de todas as rampas de acesso.",
                    "Implementar procedimento de limpeza de pista a cada 2 horas.",
                    "Adicionar sensores de inclinação nos caminhões."
                ]
            }}

            Responda APENAS com o bloco de código JSON.
            """
            analysis_result, _ = api_op.answer_question(
                files=[attachment_file],
                question=prompt,
                task_type='extraction'
            )

            if not analysis_result or not analysis_result.get('recomendacoes'):
                raise ValueError("A análise da IA não retornou dados ou não gerou recomendações.")

            # 2. Upload para o Google Drive
            from gdrive.config import CENTRAL_ALERTS_FOLDER_ID
            api_manager = GoogleApiManager()

            photo_url = api_manager.upload_file(CENTRAL_ALERTS_FOLDER_ID, photo_file, f"foto_{alert_number}.jpg")
            anexos_url = api_manager.upload_file(CENTRAL_ALERTS_FOLDER_ID, attachment_file, f"anexo_{alert_number}.pdf")

            if not photo_url or not anexos_url:
                raise ConnectionError("Falha no upload de um ou mais arquivos para o Google Drive.")

            # 3. Salvar no estado da sessão para confirmação
            st.session_state.incident_data_for_confirmation = {
                **analysis_result,
                "numero_alerta": alert_number,
                "foto_url": photo_url,
                "anexos_url": anexos_url,
                "photo_bytes": photo_file.getvalue()
            }
            st.session_state.analysis_complete = True

    except Exception as e:
        st.session_state.error = f"Ocorreu um erro: {e}"
    finally:
        st.session_state.processing = False

def display_incident_registration_tab():
    """
    Exibe a aba e o fluxo completo para cadastrar um novo alerta de incidente.
    """
    st.header("Cadastrar Novo Alerta de Incidente")

    # Etapa 1: Formulário de Upload
    with st.form("new_incident_form"):
        st.markdown("**1. Forneça os arquivos e informações iniciais**")
        alert_number = st.text_input("Número do Alerta", help="Ex: ALERTA-2025-01")
        attachment_file = st.file_uploader("Documento de Anexo (PDF/DOCX)", type=["pdf", "docx"])
        photo_file = st.file_uploader("Foto do Incidente (JPG/PNG)", type=["jpg", "png"])
        
        submitted = st.form_submit_button("Analisar e Fazer Upload", type="primary")

        if submitted:
            if not all([alert_number, attachment_file, photo_file]):
                st.warning("Por favor, preencha todos os campos e anexe os arquivos.")
            else:
                analyze_incident_document(attachment_file, photo_file, alert_number)
    
    if st.session_state.get('error'):
        st.error(st.session_state.error)

    # Etapa 2: Confirmação do Admin
    if st.session_state.get('analysis_complete'):
        st.markdown("---_**2. Revise os dados extraídos pela IA e confirme**")
        data = st.session_state.incident_data_for_confirmation

        with st.form("confirm_incident_form"):
            st.image(data['photo_bytes'], caption="Foto do Incidente", width=300)

            edited_evento_resumo = st.text_input("Resumo do Evento", value=data.get('evento_resumo', ''))
            edited_data_evento = st.date_input("Data do Evento", value=datetime.strptime(data.get('data_evento'), '%Y-%m-%d').date() if data.get('data_evento') else None)
            edited_o_que_aconteceu = st.text_area("O que aconteceu?", value=data.get('o_que_aconteceu', ''), height=150)
            edited_por_que_aconteceu = st.text_area("Por que aconteceu?", value=data.get('por_que_aconteceu', ''), height=150)
            
            st.markdown("##### Recomendações / Ações de Bloqueio Sugeridas pela IA")
            recomendacoes_df = pd.DataFrame(data.get('recomendacoes', []), columns=["Descrição da Recomendação"])
            edited_recomendacoes = st.data_editor(recomendacoes_df, num_rows="dynamic", use_container_width=True)

            confirm_button = st.form_submit_button("Confirmar e Salvar Alerta Completo")

            if confirm_button:
                if not all([edited_evento_resumo, edited_data_evento, edited_o_que_aconteceu, edited_por_que_aconteceu]) or edited_recomendacoes.empty:
                    st.error("Todos os campos de texto e a lista de recomendações devem ser preenchidos.")
                else:
                    with st.spinner("Salvando na Planilha Matriz..."):
                        # Pega o ID da planilha matriz do gerenciador global
                        matrix_manager_global = GlobalMatrixManager()
                        matrix_spreadsheet_id = matrix_manager_global.spreadsheet.id
                        incident_manager = GlobalIncidentManager(matrix_spreadsheet_id)
                        
                        # 1. Salva o incidente principal
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
                            # 2. Salva as ações de bloqueio (recomendações) em lote
                            recomendacoes_list = edited_recomendacoes["Descrição da Recomendação"].tolist()
                            success_actions = incident_manager.add_blocking_actions_batch(new_incident_id, recomendacoes_list)
                            
                            if success_actions:
                                st.success(f"Alerta '{edited_evento_resumo}' e suas {len(recomendacoes_list)} recomendações foram salvos com sucesso!")
                                log_action("REGISTER_INCIDENT", {"incident_summary": edited_evento_resumo, "alert_number": data['numero_alerta']})
                                # Limpa o estado para permitir novo cadastro
                                del st.session_state.analysis_complete
                                del st.session_state.incident_data_for_confirmation
                                st.rerun()
                            else:
                                st.error("O incidente foi salvo, mas falhou ao salvar as recomendações. Verifique a aba 'acoes_bloqueio'.")
                        else:
                            st.error("Falha ao salvar o alerta na planilha. Verifique os logs.")

# --- FUNÇÕES ANTIGAS (ADAPTADAS) ---

@st.dialog("Gerenciar Usuário")
def user_dialog(user_data=None):
    is_edit_mode = user_data is not None
    title = "Editar Usuário" if is_edit_mode else "Adicionar Novo Usuário"
    st.subheader(title)

    matrix_manager_global = GlobalMatrixManager()
    all_units = matrix_manager_global.get_all_units()
    unit_names = [unit['nome_unidade'] for unit in all_units] + ["*"]

    with st.form("user_form"):
        email = st.text_input("E-mail", value=user_data['email'] if is_edit_mode else "", disabled=is_edit_mode)
        nome = st.text_input("Nome", value=user_data['nome'] if is_edit_mode else "")
        
        roles = ["admin", "editor", "viewer"]
        current_role_index = roles.index(user_data['role']) if is_edit_mode and user_data.get('role') in roles else 0
        role = st.selectbox("Papel (Role)", roles, index=current_role_index)
        
        current_unit_index = unit_names.index(user_data['unidade_associada']) if is_edit_mode and user_data.get('unidade_associada') in unit_names else 0
        unidade_associada = st.selectbox("Unidade Associada", unit_names, index=current_unit_index)

        if st.form_submit_button("Salvar"):
            if not email or not nome:
                st.error("E-mail e Nome são obrigatórios.")
                return

            if is_edit_mode:
                updates = {"nome": nome, "role": role, "unidade_associada": unidade_associada}
                if matrix_manager_global.update_user(user_data['email'], updates):
                    st.success("Usuário atualizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Falha ao atualizar usuário.")
            else:
                if matrix_manager_global.get_user_info(email):
                    st.error(f"O e-mail '{email}' já está cadastrado.")
                else:
                    user_data = [email, nome, role, unidade_associada]
                    if matrix_manager_global.add_user(user_data):
                        st.success(f"Usuário '{nome}' adicionado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Falha ao adicionar usuário.")

@st.dialog("Confirmar Exclusão")
def confirm_delete_dialog(user_email):
    st.warning(f"Você tem certeza que deseja remover permanentemente o usuário **{user_email}**?")
    st.caption("Esta ação não pode ser desfeita.")
    
    col1, col2 = st.columns(2)
    if col1.button("Cancelar", use_container_width=True):
        st.rerun()
    if col2.button("Sim, Remover", type="primary", use_container_width=True):
        matrix_manager_global = GlobalMatrixManager()
        if matrix_manager_global.remove_user(user_email):
            st.success(f"Usuário '{user_email}' removido com sucesso!")
            st.rerun()
        else:
            st.error("Falha ao remover usuário.")

# --- PÁGINA PRINCIPAL DE ADMINISTRAÇÃO ---

def show_admin_page():
    if not check_permission(level='admin'):
        st.stop()

    st.title("🚀 Painel de Administração")

    if st.session_state.get('unit_name') != 'Global':
        st.warning("Acesso restrito ao Administrador Global.")
        st.stop()

    tab_list = [
        "Cadastrar Novo Alerta de Incidente",
        "Logs de Auditoria",
        "Gerenciamento Global"
    ]
    tab_incident, tab_logs, tab_global_manage = st.tabs(tab_list)

    with tab_incident:
        display_incident_registration_tab()

    with tab_logs:
        st.header("📜 Logs de Auditoria do Sistema")
        matrix_manager_global = GlobalMatrixManager()
        logs_df = matrix_manager_global.get_audit_logs()
        if not logs_df.empty:
            st.dataframe(logs_df.sort_values(by='timestamp', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum registro de log encontrado.")
    
    with tab_global_manage:
        st.header("Gerenciamento Global do Sistema")
        matrix_manager_global = GlobalMatrixManager()

        with st.expander("Provisionar Nova Unidade Operacional"):
            with st.form("provision_form"):
                new_unit_name = st.text_input("Nome da Nova Unidade")
                if st.form_submit_button("🚀 Iniciar Provisionamento"):
                    if not new_unit_name:
                        st.error("O nome da unidade não pode ser vazio.")
                    elif matrix_manager_global.get_unit_info(new_unit_name):
                        st.error(f"Erro: Uma unidade com o nome '{new_unit_name}' já existe.")
                    else:
                        with st.spinner(f"Criando infraestrutura para '{new_unit_name}'..."):
                            try:
                                from gdrive.config import CENTRAL_DRIVE_FOLDER_ID
                                api_manager = GoogleApiManager()
                                st.write("1/4 - Criando pasta...")
                                new_folder_id = api_manager.create_folder(f"ABRANGENCIA - {new_unit_name}", CENTRAL_DRIVE_FOLDER_ID)
                                if not new_folder_id: raise Exception("Falha ao criar pasta.")
                                st.write("2/4 - Criando Planilha...")
                                new_sheet_id = api_manager.create_spreadsheet(f"ABRANGENCIA - Dados - {new_unit_name}", new_folder_id)
                                if not new_sheet_id: raise Exception("Falha ao criar Planilha.")
                                st.write("3/4 - Configurando abas...")
                                if not api_manager.setup_sheets_from_config(new_sheet_id, "sheets_config.yaml"):
                                    raise Exception("Falha ao configurar as abas.")
                                st.write("4/4 - Registrando na Matriz...")
                                if not matrix_manager_global.add_unit([new_unit_name, new_sheet_id, new_folder_id]):
                                    raise Exception("Falha ao registrar na Planilha Matriz.")
                                log_action("PROVISION_UNIT", {"unit_name": new_unit_name, "sheet_id": new_sheet_id})
                                st.success(f"Unidade '{new_unit_name}' provisionada com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Ocorreu um erro: {e}")
        
        st.divider()
        st.subheader("Gerenciar Usuários do Sistema")

        if st.button("➕ Adicionar Novo Usuário"):
            user_dialog()

        all_users_df = pd.DataFrame(matrix_manager_global.get_all_users())
        if not all_users_df.empty:
            display_columns = ['email', 'nome', 'role', 'unidade_associada']
            columns_to_show = [col for col in display_columns if col in all_users_df.columns]
            
            st.data_editor(
                all_users_df[columns_to_show],
                key="user_editor",
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Nenhum usuário cadastrado.")
