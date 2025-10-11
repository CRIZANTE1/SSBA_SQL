import streamlit as st
import pandas as pd
from datetime import datetime
from database.matrix_manager import get_matrix_manager
from operations.incident_manager import get_incident_manager
from auth.auth_utils import check_permission
from operations.audit_logger import log_action
from AI.api_Operation import PDFQA
from front.admin_dashboard import display_admin_summary_dashboard
from database.supabase_storage import SupabaseStorage
from io import BytesIO
from supabase import create_client

# --- LÓGICA DE NEGÓCIO PARA CADASTRO DE INCIDENTE ---

def analyze_incident_document(attachment_file, photo_file, alert_number):
    """
    Orquestra APENAS a análise com IA. Os uploads serão feitos após a confirmação.
    """
    st.session_state.processing = True
    st.session_state.error = None
    st.session_state.analysis_complete = False

    try:
        with st.spinner("Analisando documento com IA..."):
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

            # 2. Armazena os dados DA IA e os ARQUIVOS para upload posterior
            st.session_state.incident_data_for_confirmation = {
                **analysis_result,
                "numero_alerta": alert_number,
                # Armazena os arquivos em memória para upload depois
                "photo_file_bytes": photo_file.getvalue(),
                "photo_file_name": photo_file.name,
                "photo_file_type": photo_file.type,
                "attachment_file_bytes": attachment_file.getvalue(),
                "attachment_file_name": attachment_file.name,
                "attachment_file_type": attachment_file.type
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
        
        submitted = st.form_submit_button("Analisar com IA", type="primary")

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
                # Mostra a foto em memória
                st.image(data['photo_file_bytes'], caption="Foto do Incidente", use_container_width=True)
            
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
                    with st.spinner("Fazendo upload dos arquivos e salvando no banco de dados..."):
                        # AGORA faz o upload dos arquivos
                        from io import BytesIO
                        storage = SupabaseStorage()
                        
                        # Reconstrói os objetos de arquivo a partir dos bytes armazenados
                        photo_file_obj = BytesIO(data['photo_file_bytes'])
                        photo_file_obj.name = data['photo_file_name']
                        photo_file_obj.type = data['photo_file_type']
                        
                        attachment_file_obj = BytesIO(data['attachment_file_bytes'])
                        attachment_file_obj.name = data['attachment_file_name']
                        attachment_file_obj.type = data['attachment_file_type']
                        
                        # Upload da foto
                        photo_url = storage.upload_public_image(photo_file_obj)
                        
                        # Upload do anexo
                        anexos_url = storage.upload_restricted_attachment(attachment_file_obj)
                        
                        if not photo_url or not anexos_url:
                            st.error("Falha no upload de um ou mais arquivos para o Supabase Storage.")
                            return
                        
                        # Salva no banco de dados
                        incident_manager = get_incident_manager()
                        
                        new_incident_id = incident_manager.add_incident(
                            numero_alerta=data['numero_alerta'],
                            evento_resumo=edited_evento_resumo,
                            data_evento=edited_data_evento,
                            o_que_aconteceu=edited_o_que_aconteceu,
                            por_que_aconteceu=edited_por_que_aconteceu,
                            foto_url=photo_url,
                            anexos_url=anexos_url
                        )

                        if new_incident_id:
                            recomendacoes_list = edited_recomendacoes["Descrição da Ação"].tolist()
                            success_actions = incident_manager.add_blocking_actions_batch(new_incident_id, recomendacoes_list)
                            
                            if success_actions:
                                st.success(f"✅ Alerta '{edited_evento_resumo}' salvo com sucesso!")
                                log_action("REGISTER_INCIDENT", {"incident_id": new_incident_id, "alert_number": data['numero_alerta']})
                                # Limpa o estado
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

def display_storage_test_tab():
    """Testa as configurações de Storage e API keys"""
    st.header("🔍 Teste de Configuração de Storage")
    
    st.info("Use esta aba para diagnosticar problemas de autenticação com o Supabase Storage.")
    
    # <<< ADICIONE ESTA SEÇÃO DE DIAGNÓSTICO DETALHADO >>>
    st.subheader("🔬 Diagnóstico Detalhado das Chaves")
    
    try:
        supabase_url = st.secrets.supabase.get("url")
        anon_key = st.secrets.supabase.get("key")
        service_key = st.secrets.supabase.get("service_role_key")
        
        # Decodifica os tokens JWT para verificar
        import base64
        import json
        
        def decode_jwt_payload(token):
            """Decodifica a parte payload de um JWT sem verificar a assinatura"""
            try:
                # JWT format: header.payload.signature
                parts = token.split('.')
                if len(parts) != 3:
                    return {"error": "Token inválido - não tem 3 partes"}
                
                # Decodifica o payload (segunda parte)
                payload = parts[1]
                # Adiciona padding se necessário
                payload += '=' * (4 - len(payload) % 4)
                decoded = base64.urlsafe_b64decode(payload)
                return json.loads(decoded)
            except Exception as e:
                return {"error": str(e)}
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🔑 Anon Key**")
            if anon_key:
                anon_payload = decode_jwt_payload(anon_key)
                st.json(anon_payload)
                expected_role = anon_payload.get("role")
                if expected_role == "anon":
                    st.success(f"✅ Role correta: {expected_role}")
                else:
                    st.error(f"❌ Role incorreta. Esperado: 'anon', Encontrado: '{expected_role}'")
            else:
                st.error("❌ Anon key não encontrada")
        
        with col2:
            st.markdown("**🔐 Service Role Key**")
            if service_key:
                service_payload = decode_jwt_payload(service_key)
                st.json(service_payload)
                expected_role = service_payload.get("role")
                if expected_role == "service_role":
                    st.success(f"✅ Role correta: {expected_role}")
                else:
                    st.error(f"❌ Role incorreta. Esperado: 'service_role', Encontrado: '{expected_role}'")
                    st.warning("⚠️ A chave configurada NÃO é uma service_role key! Você copiou a chave errada do Supabase.")
            else:
                st.error("❌ Service role key não encontrada")
        
        st.divider()
        
        # <<< RESTANTE DO CÓDIGO ORIGINAL >>>
        st.subheader("Configurações Encontradas")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("URL do Supabase", "✅ Configurada" if supabase_url else "❌ Ausente")
            if supabase_url:
                st.caption(supabase_url)
        
        with col2:
            st.metric("Anon Key", "✅ Encontrada" if anon_key else "❌ Ausente")
            st.metric("Service Role Key", "✅ Encontrada" if service_key else "❌ Ausente")
        
        if not all([supabase_url, anon_key, service_key]):
            st.error("⚠️ Algumas configurações estão faltando! Verifique o arquivo `.streamlit/secrets.toml`")
            st.code("""
[supabase]
url = "https://qhkfkffkaqihlhcfildx.supabase.co"
key = "sua_anon_key_aqui"
service_role_key = "sua_service_role_key_aqui"
            """)
            return
        
        st.divider()
        st.subheader("Testes de Conectividade")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔑 Testar Anon Key", use_container_width=True):
                with st.spinner("Testando..."):
                    try:
                        client = create_client(supabase_url, anon_key)
                        buckets = client.storage.list_buckets()
                        st.success(f"✅ Anon Key funciona!\n\n{len(buckets)} buckets encontrados")
                        with st.expander("Ver buckets"):
                            st.json(buckets)
                    except Exception as e:
                        st.error(f"❌ Anon Key falhou:\n\n{e}")
        
        with col2:
            if st.button("🔐 Testar Service Role Key", use_container_width=True, type="primary"):
                with st.spinner("Testando..."):
                    try:
                        client = create_client(supabase_url, service_key)
                        buckets = client.storage.list_buckets()
                        st.success(f"✅ Service Role Key funciona!\n\n{len(buckets)} buckets encontrados")
                        with st.expander("Ver buckets"):
                            st.json(buckets)
                    except Exception as e:
                        st.error(f"❌ Service Role Key falhou:\n\n{e}")
        
        with col3:
            if st.button("📤 Testar Upload", use_container_width=True):
                with st.spinner("Testando upload..."):
                    try:
                        client = create_client(supabase_url, service_key)
                        
                        # Cria um arquivo de teste
                        test_content = f"Teste de upload - {datetime.now().isoformat()}"
                        test_file = BytesIO(test_content.encode())
                        
                        result = client.storage.from_("public-images").upload(
                            path="test_upload.txt",
                            file=test_file.getvalue(),
                            file_options={"upsert": "true"}
                        )
                        
                        st.success("✅ Upload funcionou!")
                        
                        # Gera URL do arquivo
                        file_url = client.storage.from_("public-images").get_public_url("test_upload.txt")
                        st.markdown(f"**Arquivo criado:** [test_upload.txt]({file_url})")
                        
                        with st.expander("Ver resposta completa"):
                            st.json(result)
                    except Exception as e:
                        st.error(f"❌ Upload falhou:\n\n{e}")
        
        if st.button("🖼️ Testar Upload de Imagem Real", use_container_width=True):
            with st.spinner("Testando upload de imagem..."):
                try:
                    client = create_client(supabase_url, service_key)
                    
                    # Cria uma imagem PNG válida de 1x1 pixel
                    import struct
                    png_data = (
                        b'\x89PNG\r\n\x1a\n'  # PNG signature
                        b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                        b'\x08\x02\x00\x00\x00\x90wS\xde'
                        b'\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
                        b'\x00\x00\x00\x00IEND\xaeB`\x82'
                    )
                    
                    result = client.storage.from_("public-images").upload(
                        path="test_image.png",
                        file=png_data,
                        file_options={"content-type": "image/png", "upsert": "true"}
                    )
                    
                    st.success("✅ Upload de imagem funcionou!")
                    file_url = client.storage.from_("public-images").get_public_url("test_image.png")
                    st.markdown(f"**URL:** {file_url}")
                    st.image(file_url, width=100)
                    
                except Exception as e:
                    st.error(f"❌ Upload falhou:\n\n{e}")
        
        st.divider()
        st.subheader("Teste do SupabaseStorage (classe do app)")
        
        if st.button("🧪 Testar SupabaseStorage", use_container_width=True):
            with st.spinner("Testando a classe SupabaseStorage..."):
                try:
                    from database.supabase_storage import SupabaseStorage
                    storage = SupabaseStorage()
                    
                    if not storage.client:
                        st.error("❌ Cliente não foi inicializado")
                        return
                    
                    # Testa listagem de buckets
                    buckets = storage.client.storage.list_buckets()
                    st.success(f"✅ SupabaseStorage funcionando!\n\n{len(buckets)} buckets acessíveis")
                    
                    # Testa upload
                    test_file = BytesIO(b"teste da classe")
                    test_file.name = "test_class.txt"
                    test_file.type = "text/plain"
                    
                    url = storage.upload_public_image(test_file)
                    
                    if url:
                        st.success(f"✅ Upload via classe funcionou!")
                        st.markdown(f"**URL:** {url}")
                    else:
                        st.error("❌ Upload via classe falhou (retornou None)")
                    
                except Exception as e:
                    st.error(f"❌ Erro ao testar SupabaseStorage:\n\n{e}")
                    import traceback
                    with st.expander("Ver traceback completo"):
                        st.code(traceback.format_exc())
    
    except Exception as e:
        st.error(f"Erro ao carregar configurações: {e}")

# --- PÁGINA PRINCIPAL ---

def show_admin_page():
    check_permission(level='admin')
    st.title("🚀 Painel de Administração")
    if st.session_state.get('unit_name') != 'Global':
        st.error("Acesso restrito ao Administrador Global."); st.stop()
    
    # <<< ADICIONE A NOVA ABA AQUI >>>
    tab_dashboard, tab_incident, tab_users, tab_requests, tab_logs, tab_storage_test = st.tabs([
        "📊 Dashboard Global", 
        "➕ Cadastrar Alerta", 
        "👥 Gerenciar Usuários", 
        "📥 Solicitações", 
        "📜 Logs",
        "🔧 Teste Storage"  # <<< NOVA ABA
    ])

    with tab_dashboard:
        display_admin_summary_dashboard()

    with tab_incident: 
        display_incident_registration_tab()

    with tab_users:
        st.header("Gerenciar Usuários do Sistema")
        matrix_manager = get_matrix_manager()
        if st.button("➕ Adicionar Novo Usuário"): user_dialog()
        all_users_df = matrix_manager.get_all_users_df()
        if not all_users_df.empty:
            st.write("Clique em uma linha para editar ou remover um usuário.")
            selected_user = st.dataframe(all_users_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if selected_user.selection.rows:
                user_to_manage = all_users_df.iloc[selected_user.selection.rows[0]].to_dict()
                st.subheader(f"Ações para: {user_to_manage['nome']}")
                col1, col2 = st.columns(2)
                if col1.button("✏️ Editar Usuário", use_container_width=True): user_dialog(user_to_manage)
                if col2.button("🗑️ Remover Usuário", type="primary", use_container_width=True):
                    if matrix_manager.remove_user(user_to_manage['email']):
                        st.success(f"Usuário '{user_to_manage['email']}' removido."); st.rerun()
                    else: st.error("Falha ao remover usuário.")
        else: st.info("Nenhum usuário cadastrado.")

    with tab_logs:
        st.header("📜 Logs de Auditoria do Sistema")
        matrix_manager = get_matrix_manager()
        logs_df = matrix_manager.get_audit_logs()
        if not logs_df.empty:
            st.dataframe(logs_df.sort_values(by='timestamp', ascending=False), use_container_width=True, hide_index=True)
        else: st.info("Nenhum registro de log encontrado.")

    with tab_requests:
        st.header("Solicitações de Acesso Pendentes")
        matrix_manager = get_matrix_manager()
        pending_requests_df = matrix_manager.get_pending_access_requests()
        if pending_requests_df.empty:
            st.info("Nenhuma solicitação de acesso pendente.")
        else:
            st.write("Aprove ou rejeite os novos usuários.")
            for index, row in pending_requests_df.iterrows():
                with st.container(border=True):
                    col1, col2, col3, col_approve, col_reject = st.columns([2.5, 2, 1.5, 1, 1])
                    col1.text_input("E-mail", value=row['email'], disabled=True, key=f"email_{index}")
                    col2.text_input("Unidade", value=row['unidade_solicitada'], disabled=True, key=f"unit_{index}")
                    role_to_assign = col3.selectbox("Definir Papel", options=["viewer", "editor", "admin"], index=0, key=f"role_{index}")
                    if col_approve.button("Aprovar", key=f"approve_{index}", type="primary", use_container_width=True):
                        with st.spinner(f"Aprovando {row['email']}..."):
                            if matrix_manager.approve_access_request(row['email'], role_to_assign):
                                st.success(f"Usuário {row['email']} aprovado!"); st.rerun()
                            else: st.error(f"Falha ao aprovar {row['email']}.")
                    if col_reject.button("Rejeitar", key=f"reject_{index}", use_container_width=True):
                        with st.spinner(f"Rejeitando {row['email']}..."):
                            if matrix_manager.reject_access_request(row['email']):
                                st.warning(f"Solicitação de {row['email']} rejeitada."); st.rerun()
                            else: st.error(f"Falha ao rejeitar {row['email']}.")
    
    # <<< NOVA ABA DE TESTE >>>
    with tab_storage_test:
        display_storage_test_tab()
