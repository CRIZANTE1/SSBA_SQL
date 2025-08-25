import streamlit as st
import pandas as pd
from gdrive.matrix_manager import MatrixManager as GlobalMatrixManager
from operations.employee import EmployeeManager
from auth.auth_utils import check_permission

@st.cache_data(ttl=300)
def load_aggregated_data():
    """
    Carrega e agrega dados de TODAS as unidades.
    """
    progress_bar = st.progress(0, text="Carregando dados consolidados de todas as unidades...")
    
    matrix_manager_global = GlobalMatrixManager()
    all_units = matrix_manager_global.get_all_units()

    aggregated_companies = []
    aggregated_employees = []
    
    total_units = len(all_units)
    for i, unit in enumerate(all_units):
        unit_name = unit.get('nome_unidade')
        spreadsheet_id = unit.get('spreadsheet_id')
        folder_id = unit.get('folder_id')
        
        progress_bar.progress((i + 1) / total_units, text=f"Lendo unidade: {unit_name}...")
        
        if not spreadsheet_id or not unit_name:
            continue

        try:
            temp_manager = EmployeeManager(spreadsheet_id, folder_id)
            
            companies_df = temp_manager.companies_df
            if not companies_df.empty:
                companies_df['unidade'] = unit_name
                aggregated_companies.append(companies_df)

            employees_df = temp_manager.employees_df
            if not employees_df.empty:
                employees_df['unidade'] = unit_name
                aggregated_employees.append(employees_df)
        except Exception as e:
            st.warning(f"Não foi possível carregar dados da unidade '{unit_name}': {e}")

    progress_bar.empty()
    final_companies = pd.concat(aggregated_companies, ignore_index=True) if aggregated_companies else pd.DataFrame()
    final_employees = pd.concat(aggregated_employees, ignore_index=True) if aggregated_employees else pd.DataFrame()

    return final_companies, final_employees

def show_admin_page():
    if not check_permission(level='admin'):
        st.stop()

    st.title("🚀 Painel de Administração")

    is_global_view = st.session_state.get('unit_name') == 'Global'
    
    if is_global_view:
        tab_list = ["Visão Global", "Logs de Auditoria"]
        tab_global, tab_logs = st.tabs(tab_list)

        with tab_global:
            st.header("Visão Global (Todas as Unidades)")
            st.info("Este modo é para consulta consolidada. Para gerenciar detalhes, selecione uma unidade na barra lateral.")
            all_companies, all_employees = load_aggregated_data()
            
            st.subheader("Todas as Empresas Cadastradas")
            if not all_companies.empty:
                st.dataframe(all_companies[['unidade', 'nome', 'cnpj', 'status']], use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma empresa encontrada em todas as unidades.")
                
            st.subheader("Todos os Funcionários Cadastrados")
            if not all_employees.empty:
                st.dataframe(all_employees[['unidade', 'nome', 'cargo', 'status']], use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum funcionário encontrado em todas as unidades.")

        with tab_logs:
            st.header("📜 Logs de Auditoria do Sistema")
            st.info("Ações de login, logout e exclusão de registros em todo o sistema.")
            matrix_manager_global = GlobalMatrixManager()
            logs_df = matrix_manager_global.get_audit_logs()
            
            if not logs_df.empty:
                logs_df_sorted = logs_df.sort_values(by='timestamp', ascending=False)
                st.dataframe(logs_df_sorted, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum registro de log encontrado.")
        
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

    # --- CORREÇÃO APLICADA AQUI: APENAS UM CONJUNTO DE ABAS É CRIADO ---
    tab_list_unidade = ["Gerenciar Empresas", "Gerenciar Funcionários", "Gerenciar Matriz Manualmente", "Assistente de Matriz (IA)"]
    tab_empresa, tab_funcionario, tab_matriz, tab_recomendacoes = st.tabs(tab_list_unidade)

    with tab_empresa:
        with st.expander("➕ Cadastrar Nova Empresa"):
            with st.form("form_add_company", clear_on_submit=True):
                company_name = st.text_input("Nome da Empresa", placeholder="Digite o nome completo da empresa")
                company_cnpj = st.text_input("CNPJ", placeholder="Digite o CNPJ")
                submitted = st.form_submit_button("Cadastrar Empresa")
                if submitted and company_name and company_cnpj:
                    with st.spinner("Cadastrando..."):
                        company_id, message = employee_manager.add_company(company_name, company_cnpj)
                        if company_id:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)

        st.subheader("Empresas Cadastradas na Unidade")
        show_archived = st.toggle("Mostrar empresas arquivadas", key="toggle_companies")
        
        df_to_show = employee_manager.companies_df if show_archived else employee_manager.companies_df[employee_manager.companies_df['status'].str.lower() == 'ativo']
        
        if df_to_show.empty:
            st.info("Nenhuma empresa para exibir.")
        else:
            for _, row in df_to_show.sort_values('nome').iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    col1.markdown(f"**{row['nome']}**")
                    col2.caption(f"CNPJ: {row['cnpj']} | Status: {row['status']}")
                    with col3:
                        if str(row['status']).lower() == 'ativo':
                            if st.button("Arquivar", key=f"archive_comp_{row['id']}", use_container_width=True):
                                employee_manager.archive_company(row['id'])
                                st.rerun()
                        else:
                            if st.button("Reativar", key=f"unarchive_comp_{row['id']}", type="primary", use_container_width=True):
                                employee_manager.unarchive_company(row['id'])
                                st.rerun()

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
