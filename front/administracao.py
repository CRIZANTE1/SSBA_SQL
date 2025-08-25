import streamlit as st
import pandas as pd
from datetime import date
from gdrive.matrix_manager import MatrixManager as GlobalMatrixManager
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from auth.auth_utils import check_permission
from ui.metrics import display_minimalist_metrics
from gdrive.google_api_manager import GoogleApiManager
from operations.audit_logger import log_action

@st.cache_data(ttl=300)
def load_aggregated_data():
    """
    Carrega e agrega dados de TODAS as unidades, incluindo Documentos da Empresa,
    e retorna uma tupla de 5 DataFrames.
    """
    progress_bar = st.progress(0, text="Carregando dados consolidados de todas as unidades...")
    matrix_manager_global = GlobalMatrixManager()
    all_units = matrix_manager_global.get_all_units()
    aggregated_data = {"companies": [], "employees": [], "asos": [], "trainings": [], "company_docs": []}
    
    total_units = len(all_units)
    for i, unit in enumerate(all_units):
        unit_name, spreadsheet_id, folder_id = unit.get('nome_unidade'), unit.get('spreadsheet_id'), unit.get('folder_id')
        progress_bar.progress((i + 1) / total_units, text=f"Lendo unidade: {unit_name}...")
        if not spreadsheet_id or not unit_name: continue
        try:
            temp_employee_manager = EmployeeManager(spreadsheet_id, folder_id)
            temp_docs_manager = CompanyDocsManager(spreadsheet_id)
            data_to_collect = {
                "companies": temp_employee_manager.companies_df, "employees": temp_employee_manager.employees_df,
                "asos": temp_employee_manager.aso_df, "trainings": temp_employee_manager.training_df,
                "company_docs": temp_docs_manager.docs_df
            }
            for key, df in data_to_collect.items():
                if not df.empty:
                    df['unidade'] = unit_name
                    aggregated_data[key].append(df)
        except Exception as e:
            st.warning(f"Não foi possível carregar dados da unidade '{unit_name}': {e}")

    progress_bar.empty()
    final_dfs = {key: (pd.concat(value, ignore_index=True) if value else pd.DataFrame()) for key, value in aggregated_data.items()}
    return final_dfs["companies"], final_dfs["employees"], final_dfs["asos"], final_dfs["trainings"], final_dfs["company_docs"]


def display_global_summary_dashboard(companies_df, employees_df, asos_df, trainings_df, company_docs_df):
    """
    Calcula e exibe um dashboard de resumo executivo com gráficos e detalhamento de pendências.
    """
    st.header("Dashboard de Resumo Executivo Global")

    if companies_df.empty:
        st.info("Nenhuma empresa encontrada em todas as unidades.")
        return

    # --- Filtra para entidades ATIVAS ---
    active_companies = companies_df[companies_df['status'].str.lower() == 'ativo']
    active_employees = employees_df[employees_df['status'].str.lower() == 'ativo']
    
    if active_companies.empty:
        st.info("Nenhuma empresa ativa encontrada.")
        return

    # --- Métricas Gerais ---
    total_units = companies_df['unidade'].nunique()
    total_active_companies = len(active_companies)
    total_active_employees = len(active_employees)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Unidades Operacionais", f"{total_units}")
    col2.metric("Total de Empresas Ativas", total_active_companies)
    col3.metric("Total de Funcionários Ativos", total_active_employees)
    st.divider()

    # --- Cálculo de Pendências (Apenas o mais recente por tipo/norma) ---
    today = date.today()
    
    expired_asos = pd.DataFrame()
    if not asos_df.empty:
        asos_actives = asos_df[asos_df['funcionario_id'].isin(active_employees['id'])].copy()
        latest_asos = asos_actives.sort_values('data_aso', ascending=False).groupby(['funcionario_id', 'tipo_aso']).head(1)
        expired_asos = latest_asos[latest_asos['vencimento'].dt.date < today]

    expired_trainings = pd.DataFrame()
    if not trainings_df.empty:
        trainings_actives = trainings_df[trainings_df['funcionario_id'].isin(active_employees['id'])].copy()
        latest_trainings = trainings_actives.sort_values('data', ascending=False).groupby(['funcionario_id', 'norma']).head(1)
        expired_trainings = latest_trainings[latest_trainings['vencimento'].dt.date < today]

    expired_company_docs = pd.DataFrame()
    if not company_docs_df.empty:
        docs_actives = company_docs_df[company_docs_df['empresa_id'].isin(active_companies['id'])].copy()
        latest_docs = docs_actives.sort_values('data_emissao', ascending=False).groupby(['empresa_id', 'tipo_documento']).head(1)
        expired_company_docs = latest_docs[latest_docs['vencimento'].dt.date < today]

    total_pendencies = len(expired_asos) + len(expired_trainings) + len(expired_company_docs)
    if total_pendencies == 0:
        st.success("🎉 Parabéns! Nenhuma pendência de vencimento encontrada em todas as unidades ativas.")
        return

    # --- Métricas por Categoria ---
    st.subheader("Total de Pendências por Categoria (Entidades Ativas)")
    col1, col2, col3 = st.columns(3)
    col1.metric("🩺 ASOs Vencidos", len(expired_asos))
    col2.metric("🎓 Treinamentos Vencidos", len(expired_trainings))
    col3.metric("📄 Docs. Empresa Vencidos", len(expired_company_docs))
    st.divider()

    # --- Gráfico de Pendências por Unidade ---
    st.subheader("Gráfico de Pendências por Unidade Operacional")
    series_list = []
    if not expired_asos.empty: series_list.append(expired_asos.groupby('unidade').size().rename("ASOs Vencidos"))
    if not expired_trainings.empty: series_list.append(expired_trainings.groupby('unidade').size().rename("Treinamentos Vencidos"))
    if not expired_company_docs.empty: series_list.append(expired_company_docs.groupby('unidade').size().rename("Docs. Empresa Vencidos"))
    
    if series_list:
        df_consolidated = pd.concat(series_list, axis=1).fillna(0).astype(int)
        st.bar_chart(df_consolidated)
        with st.expander("Ver tabela de dados de pendências por unidade"):
            df_consolidated['Total'] = df_consolidated.sum(axis=1)
            st.dataframe(df_consolidated.sort_values(by='Total', ascending=False), use_container_width=True)

        # --- Detalhamento da Unidade Mais Crítica ---
        most_critical_unit = df_consolidated.sum(axis=1).idxmax()
        st.subheader(f"🔍 Detalhes da Unidade Mais Crítica: {most_critical_unit}")

        # Mapeamentos globais
        employee_to_company_id = employees_df.set_index('id')['empresa_id']
        company_id_to_name = companies_df.set_index('id')['nome']
        pendencies_by_company = {}

        # Agrega todas as pendências da unidade crítica
        all_expired_docs = []
        if not expired_asos.empty: all_expired_docs.append(expired_asos[expired_asos['unidade'] == most_critical_unit])
        if not expired_trainings.empty: all_expired_docs.append(expired_trainings[expired_trainings['unidade'] == most_critical_unit])
        if not expired_company_docs.empty: all_expired_docs.append(expired_company_docs[expired_company_docs['unidade'] == most_critical_unit])
        
        if all_expired_docs:
            critical_unit_pendencies = pd.concat(all_expired_docs, ignore_index=True)
            
            # Mapeia o nome da empresa para cada pendência
            is_employee_doc = pd.notna(critical_unit_pendencies['funcionario_id'])
            critical_unit_pendencies.loc[is_employee_doc, 'empresa_id'] = critical_unit_pendencies.loc[is_employee_doc, 'funcionario_id'].map(employee_to_company_id)
            critical_unit_pendencies['nome_empresa'] = critical_unit_pendencies['empresa_id'].map(company_id_to_name)
            
            # Contagem de pendências por empresa
            pendencies_by_company_df = critical_unit_pendencies.groupby('nome_empresa').size().reset_index(name='Nº de Pendências')
            pendencies_by_company_df = pendencies_by_company_df.sort_values(by='Nº de Pendências', ascending=False).set_index('nome_empresa')

            st.markdown("##### Pendências por Empresa")
            st.bar_chart(pendencies_by_company_df)

            # --- Detalhamento dos Treinamentos Vencidos ---
            st.markdown("##### Detalhes dos Treinamentos Vencidos")
            expired_trainings_unit = expired_trainings[expired_trainings['unidade'] == most_critical_unit]
            if not expired_trainings_unit.empty:
                # Mapeia o nome do funcionário para cada treinamento
                employee_id_to_name = employees_df.set_index('id')['nome']
                display_df = expired_trainings_unit.copy()
                display_df['nome_funcionario'] = display_df['funcionario_id'].map(employee_id_to_name)
                display_df['nome_empresa'] = display_df['funcionario_id'].map(employee_to_company_id).map(company_id_to_name)
                
                st.dataframe(
                    display_df[['nome_empresa', 'nome_funcionario', 'norma', 'vencimento']],
                    column_config={
                        "nome_empresa": "Empresa",
                        "nome_funcionario": "Funcionário",
                        "norma": "Treinamento Vencido",
                        "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY")
                    },
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Nenhum treinamento vencido nesta unidade.")
        
def show_admin_page():
    if not check_permission(level='admin'):
        st.stop()

    st.title("🚀 Painel de Administração")

    is_global_view = st.session_state.get('unit_name') == 'Global'
    
    if is_global_view:
        tab_list = ["Dashboard Global", "Logs de Auditoria", "Provisionar Unidade"]
        tab_dashboard, tab_logs, tab_provision = st.tabs(tab_list)

        with tab_dashboard:
            companies, employees, asos, trainings, company_docs = load_aggregated_data()
            display_global_summary_dashboard(companies, employees, asos, trainings, company_docs)

        with tab_logs:
            st.header("📜 Logs de Auditoria do Sistema")
            matrix_manager_global = GlobalMatrixManager()
            logs_df = matrix_manager_global.get_audit_logs()
            if not logs_df.empty:
                st.dataframe(logs_df.sort_values(by='timestamp', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum registro de log encontrado.")
        
        with tab_provision:
            st.header("Provisionar Nova Unidade Operacional")
            with st.form("provision_form"):
                new_unit_name = st.text_input("Nome da Nova Unidade")
                if st.form_submit_button("🚀 Iniciar Provisionamento"):
                    if not new_unit_name:
                        st.error("O nome da unidade não pode ser vazio.")
                    else:
                        matrix_manager_global = GlobalMatrixManager()
                        if matrix_manager_global.get_unit_info(new_unit_name):
                            st.error(f"Erro: Uma unidade com o nome '{new_unit_name}' já existe.")
                        else:
                            with st.spinner(f"Criando infraestrutura para '{new_unit_name}'..."):
                                try:
                                    from gdrive.config import CENTRAL_DRIVE_FOLDER_ID
                                    api_manager = GoogleApiManager()
                                    st.write("1/4 - Criando pasta no Google Drive...")
                                    new_folder_id = api_manager.create_folder(f"SEGMA-SIS - {new_unit_name}", CENTRAL_DRIVE_FOLDER_ID)
                                    if not new_folder_id: raise Exception("Falha ao criar pasta no Drive.")
                                    st.write("2/4 - Criando Planilha Google...")
                                    new_sheet_id = api_manager.create_spreadsheet(f"SEGMA-SIS - Dados - {new_unit_name}", new_folder_id)
                                    if not new_sheet_id: raise Exception("Falha ao criar Planilha Google.")
                                    st.write("3/4 - Configurando abas da nova planilha...")
                                    if not api_manager.setup_sheets_from_config(new_sheet_id, "sheets_config.yaml"):
                                        raise Exception("Falha ao configurar as abas da planilha.")
                                    st.write("4/4 - Registrando nova unidade na Planilha Matriz...")
                                    if not matrix_manager_global.add_unit([new_unit_name, new_sheet_id, new_folder_id]):
                                        raise Exception("Falha ao registrar a nova unidade na Planilha Matriz.")
                                    log_action("PROVISION_UNIT", {"unit_name": new_unit_name, "sheet_id": new_sheet_id})
                                    st.success(f"Unidade '{new_unit_name}' provisionada com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Ocorreu um erro durante o provisionamento: {e}")
        st.stop()

    # --- CÓDIGO PARA VISÃO DE UNIDADE ESPECÍFICA ---
    unit_name = st.session_state.get('unit_name', 'Nenhuma')
    st.header(f"Gerenciamento da Unidade: '{unit_name}'")

    if not st.session_state.get('managers_initialized'):
        st.warning("Aguardando a inicialização dos dados da unidade...")
        st.stop()

    employee_manager = st.session_state.employee_manager
    matrix_manager_unidade = st.session_state.matrix_manager_unidade
    nr_analyzer = st.session_state.nr_analyzer

    st.subheader("Visão Geral de Pendências da Unidade")
    display_minimalist_metrics(employee_manager)
    st.divider()

    tab_list_unidade = ["Gerenciar Empresas", "Gerenciar Funcionários", "Gerenciar Matriz", "Assistente de Matriz (IA)"]
    tab_empresa, tab_funcionario, tab_matriz, tab_recomendacoes = st.tabs(tab_list_unidade)

    with tab_empresa:
            with st.expander("➕ Cadastrar Nova Empresa"):
                with st.form("form_add_company", clear_on_submit=True):
                    company_name = st.text_input("Nome da Empresa")
                    company_cnpj = st.text_input("CNPJ")
                    if st.form_submit_button("Cadastrar Empresa"):
                        if company_name and company_cnpj:
                            _, message = employee_manager.add_company(company_name, company_cnpj)
                            st.success(message)
                            st.rerun()
                        else:
                            st.warning("Preencha todos os campos.")

            st.subheader("Empresas Cadastradas na Unidade")
            show_archived = st.toggle("Mostrar empresas arquivadas")
            df_to_show = employee_manager.companies_df if show_archived else employee_manager.companies_df[employee_manager.companies_df['status'].str.lower() == 'ativo']
            
            if not df_to_show.empty:
                for _, row in df_to_show.sort_values('nome').iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3,2,1])
                        c1.markdown(f"**{row['nome']}**")
                        c2.caption(f"CNPJ: {row['cnpj']} | Status: {row['status']}")
                        with c3:
                            if str(row['status']).lower() == 'ativo':
                                if st.button("Arquivar", key=f"archive_{row['id']}"):
                                    employee_manager.archive_company(row['id'])
                                    st.rerun()
                            else:
                                if st.button("Reativar", key=f"unarchive_{row['id']}", type="primary"):
                                    employee_manager.unarchive_company(row['id'])
                                    st.rerun()
            else:
                st.info("Nenhuma empresa para exibir.")

    with tab_funcionario:
        with st.expander("➕ Cadastrar Novo Funcionário"):
            active_companies = employee_manager.companies_df[employee_manager.companies_df['status'].str.lower() == 'ativo']
            if active_companies.empty:
                st.warning("Cadastre ou reative uma empresa primeiro.")
            else:
                company_id = st.selectbox("Selecione a Empresa", options=active_companies['id'], format_func=employee_manager.get_company_name)
                with st.form("form_add_employee", clear_on_submit=True):
                    name = st.text_input("Nome do Funcionário")
                    role = st.text_input("Cargo")
                    adm_date = st.date_input("Data de Admissão")
                    if st.form_submit_button("Cadastrar"):
                        if all([name, role, adm_date, company_id]):
                            _, msg = employee_manager.add_employee(name, role, adm_date, company_id)
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error("Todos os campos são obrigatórios.")
        
        st.subheader("Funcionários Cadastrados na Unidade")
        company_filter = st.selectbox("Filtrar por Empresa", options=['Todas'] + employee_manager.companies_df['id'].tolist(), format_func=lambda x: 'Todas' if x == 'Todas' else employee_manager.get_company_name(x))
        
        employees_to_show = employee_manager.employees_df
        if company_filter != 'Todas':
            employees_to_show = employees_to_show[employees_to_show['empresa_id'] == str(company_filter)]

        if employees_to_show.empty:
            st.info("Nenhum funcionário encontrado para a empresa selecionada.")
        else:
            for _, row in employees_to_show.sort_values('nome').iterrows():
                 with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    col1.markdown(f"**{row['nome']}**")
                    col2.caption(f"Cargo: {row['cargo']} | Status: {row['status']}")
                    with col3:
                        if str(row['status']).lower() == 'ativo':
                            if st.button("Arquivar", key=f"archive_emp_{row['id']}", use_container_width=True):
                                employee_manager.archive_employee(row['id'])
                                st.rerun()
                        else:
                            if st.button("Reativar", key=f"unarchive_emp_{row['id']}", type="primary", use_container_width=True):
                                employee_manager.unarchive_employee(row['id'])
                                st.rerun()

    with tab_matriz:
        st.header("Matriz de Treinamento por Função")
        
        with st.expander("🤖 Importar Matriz com IA (via PDF)"):
            uploaded_file = st.file_uploader("Selecione um PDF com a matriz", type="pdf", key="matrix_uploader")
            if uploaded_file and st.button("Analisar Matriz com IA"):
                with st.spinner("Analisando..."):
                    data, msg = matrix_manager_unidade.analyze_matrix_pdf(uploaded_file)
                if data:
                    st.success(msg)
                    st.session_state.extracted_matrix_data = data
                else:
                    st.error(msg)

        if 'extracted_matrix_data' in st.session_state:
            st.info("Revise os dados extraídos e salve se estiverem corretos.")
            st.json(st.session_state.extracted_matrix_data)
            if st.button("Confirmar e Salvar Matriz", type="primary"):
                with st.spinner("Salvando..."):
                    funcs, maps = matrix_manager_unidade.save_extracted_matrix(st.session_state.extracted_matrix_data)
                st.success(f"Matriz salva! {funcs} novas funções e {maps} mapeamentos adicionados.")
                del st.session_state.extracted_matrix_data
                st.rerun()

        st.subheader("Gerenciamento Manual")
        col1, col2 = st.columns(2)
        with col1:
            with st.form("form_add_function"):
                st.markdown("#### Adicionar Função")
                func_name = st.text_input("Nome da Nova Função")
                if st.form_submit_button("Adicionar"):
                    if func_name:
                        _, msg = matrix_manager_unidade.add_function(func_name, "")
                        st.success(msg)
                        st.rerun()
        with col2:
            with st.form("form_map_training"):
                st.markdown("#### Mapear Treinamento para Função")
                if not matrix_manager_unidade.functions_df.empty:
                    func_id = st.selectbox("Selecione a Função", options=matrix_manager_unidade.functions_df['id'], format_func=lambda id: matrix_manager_unidade.functions_df[matrix_manager_unidade.functions_df['id'] == id]['nome_funcao'].iloc[0])
                    norm = st.selectbox("Selecione o Treinamento", options=sorted(list(employee_manager.nr_config.keys())))
                    if st.form_submit_button("Mapear"):
                        _, msg = matrix_manager_unidade.add_training_to_function(func_id, norm)
                        st.success(msg)
                        st.rerun()
                else:
                    st.warning("Cadastre uma função primeiro.")

        st.subheader("Visão Consolidada da Matriz")
        functions_df = matrix_manager_unidade.functions_df
        matrix_df = matrix_manager_unidade.matrix_df
        if not functions_df.empty:
            if not matrix_df.empty:
                mappings = matrix_df.groupby('id_funcao')['norma_obrigatoria'].apply(list).reset_index()
                consolidated = pd.merge(functions_df, mappings, left_on='id', right_on='id_funcao', how='left')
            else:
                consolidated = functions_df.copy()
                consolidated['norma_obrigatoria'] = [[] for _ in range(len(consolidated))]
            
            consolidated['norma_obrigatoria'] = consolidated['norma_obrigatoria'].apply(lambda x: sorted(x) if isinstance(x, list) and x else ["Nenhum treinamento mapeado"])
            display_dict = pd.Series(consolidated.norma_obrigatoria.values, index=consolidated.nome_funcao).to_dict()
            st.json(display_dict)
        else:
            st.info("Nenhuma função cadastrada para exibir a matriz.")

    with tab_recomendacoes:
        st.header("🤖 Assistente de Matriz com IA")
        if not matrix_manager_unidade.functions_df.empty:
            func_id_rec = st.selectbox("Selecione a Função para obter recomendações", options=matrix_manager_unidade.functions_df['id'], format_func=lambda id: matrix_manager_unidade.functions_df[matrix_manager_unidade.functions_df['id'] == id]['nome_funcao'].iloc[0])
            if st.button("Gerar Recomendações da IA"):
                func_name_rec = matrix_manager_unidade.functions_df[matrix_manager_unidade.functions_df['id'] == func_id_rec]['nome_funcao'].iloc[0]
                with st.spinner("IA pensando..."):
                    recs, msg = matrix_manager_unidade.get_training_recommendations_for_function(func_name_rec, nr_analyzer)
                if recs is not None:
                    st.session_state.recommendations = recs
                    st.session_state.selected_function_for_rec = func_id_rec
                else:
                    st.error(msg)
        else:
            st.warning("Cadastre uma função na aba anterior primeiro.")

        if 'recommendations' in st.session_state:
            st.subheader("Recomendações Geradas")
            recs = st.session_state.recommendations
            if not recs:
                st.success("A IA não identificou treinamentos obrigatórios para esta função.")
            else:
                rec_df = pd.DataFrame(recs)
                rec_df['aceitar'] = True
                edited_df = st.data_editor(rec_df, column_config={"aceitar": st.column_config.CheckboxColumn("Aceitar?")})
                if st.button("Salvar Mapeamentos Selecionados"):
                    norms_to_add = edited_df[edited_df['aceitar']]['treinamento_recomendado'].tolist()
                    if norms_to_add:
                        func_id_to_save = st.session_state.selected_function_for_rec
                        with st.spinner("Salvando..."):
                            success, msg = matrix_manager_unidade.update_function_mappings(func_id_to_save, norms_to_add)
                        if success:
                            st.success(msg)
                            del st.session_state.recommendations
                            del st.session_state.selected_function_for_rec
                            st.rerun()
                        else:
                            st.error(msg)
