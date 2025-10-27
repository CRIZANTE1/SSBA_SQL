import streamlit as st
import pandas as pd
from datetime import datetime
from operations.pdf_processor import PDFProcessor
from database.supabase_storage import SupabaseStorage
from operations.incident_manager import get_incident_manager
from operations.audit_logger import log_action
from auth.auth_utils import get_user_email, get_user_display_name
from io import BytesIO

def show_pdf_processor_page():
    """
    Página para processamento de PDFs de incidentes para usuários normais.
    Usa apenas processamento tradicional (sem IA).
    """
    st.header("📄 Processador de PDFs de Incidentes")
    st.markdown("Faça upload de documentos PDF de incidentes para extrair informações automaticamente.")
    
    # Verifica se as bibliotecas estão disponíveis
    try:
        pdf_processor = PDFProcessor()
    except ImportError as e:
        st.error(f"❌ Bibliotecas de PDF não estão disponíveis: {e}")
        st.info("Por favor, instale as dependências necessárias executando: `pip install -r requirements.txt`")
        return
    
    # Formulário de upload
    with st.form("pdf_processor_form"):
        st.markdown("**1. Informações do Incidente**")
        alert_number = st.text_input("Número do Alerta", help="Ex: ALERTA-2025-01", placeholder="ALERTA-2025-01")
        
        st.markdown("**2. Arquivos**")
        col1, col2 = st.columns(2)
        
        with col1:
            pdf_file = st.file_uploader(
                "Documento PDF do Incidente", 
                type="pdf",
                help="Documento de análise do incidente em formato PDF"
            )
        
        with col2:
            photo_file = st.file_uploader(
                "Foto do Incidente (Opcional)", 
                type=["jpg", "png", "jpeg"],
                help="Foto relacionada ao incidente"
            )
        
        # Preview do PDF se disponível
        if pdf_file:
            try:
                preview_images = pdf_processor.generate_pdf_preview(pdf_file, max_pages=2)
                if preview_images:
                    st.markdown("**📄 Preview do PDF:**")
                    cols = st.columns(len(preview_images))
                    for i, img in enumerate(preview_images):
                        with cols[i]:
                            st.image(img, caption=f"Página {i+1}", use_container_width=True)
            except Exception as e:
                st.warning(f"Não foi possível gerar preview: {e}")
        
        submitted = st.form_submit_button("📄 Processar Documento", type="primary")
        
        if submitted:
            if not alert_number or not pdf_file:
                st.warning("⚠️ Por favor, preencha o número do alerta e anexe o arquivo PDF.")
            else:
                process_incident_pdf(pdf_file, photo_file, alert_number, pdf_processor)

def process_incident_pdf(pdf_file, photo_file, alert_number, pdf_processor):
    """
    Processa o PDF do incidente e extrai as informações.
    """
    try:
        with st.spinner("🔄 Processando documento PDF..."):
            # Valida o PDF
            is_valid, validation_message = pdf_processor.validate_pdf_structure(pdf_file)
            
            if not is_valid:
                st.warning(f"⚠️ {validation_message}")
                st.info("Tentando processar mesmo assim...")
            
            # Extrai dados usando processamento tradicional
            incident_data = pdf_processor.extract_incident_data(pdf_file, use_ai=False)
            
            if not incident_data:
                st.error("❌ Falha ao extrair dados do PDF.")
                return
            
            # Armazena os dados para confirmação
            st.session_state.pdf_processor_data = {
                **incident_data,
                "numero_alerta": alert_number,
                "pdf_file_bytes": pdf_file.getvalue(),
                "pdf_file_name": pdf_file.name,
                "pdf_file_type": pdf_file.type,
                "photo_file_bytes": photo_file.getvalue() if photo_file else None,
                "photo_file_name": photo_file.name if photo_file else None,
                "photo_file_type": photo_file.type if photo_file else None,
            }
            
            st.session_state.pdf_processing_complete = True
            st.success("✅ Documento processado com sucesso!")
            
            # Log da ação
            log_action("PDF_PROCESSING_SUCCESS", {
                "alert_number": alert_number,
                "user": get_user_email(),
                "method": "Tradicional"
            })
    
    except Exception as e:
        st.error(f"❌ Erro ao processar PDF: {e}")
        log_action("PDF_PROCESSING_FAILURE", {
            "alert_number": alert_number,
            "user": get_user_email(),
            "error": str(e)
        })

def show_confirmation_form():
    """
    Mostra formulário de confirmação com os dados extraídos.
    """
    if not st.session_state.get('pdf_processing_complete'):
        return
    
    st.divider()
    st.subheader("2. Revise e Confirme os Dados Extraídos")
    
    data = st.session_state.pdf_processor_data
    
    with st.form("confirm_pdf_data_form"):
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if data.get('photo_file_bytes'):
                st.image(data['photo_file_bytes'], caption="Foto do Incidente", use_container_width=True)
            else:
                st.info("Nenhuma foto anexada")
        
        with col2:
            st.markdown("**Dados Extraídos:**")
            edited_evento_resumo = st.text_input("Resumo do Evento", value=data.get('evento_resumo', ''))
            
            try:
                default_date = datetime.strptime(data.get('data_evento'), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                default_date = None
            edited_data_evento = st.date_input("Data do Evento", value=default_date)
        
        edited_o_que_aconteceu = st.text_area(
            "O que aconteceu?", 
            value=data.get('o_que_aconteceu', ''), 
            height=150
        )
        
        edited_por_que_aconteceu = st.text_area(
            "Por que aconteceu?", 
            value=data.get('por_que_aconteceu', ''), 
            height=150
        )
        
        # Recomendações
        st.markdown("**Recomendações:**")
        recomendacoes_text = data.get('recomendacoes', [])
        if isinstance(recomendacoes_text, list):
            recomendacoes_text = '\n'.join([f"• {rec}" for rec in recomendacoes_text])
        else:
            recomendacoes_text = str(recomendacoes_text)
        
        edited_recomendacoes = st.text_area(
            "Recomendações", 
            value=recomendacoes_text, 
            height=200,
            help="Uma recomendação por linha, começando com •"
        )
        
        # Converte de volta para lista
        edited_recomendacoes_list = [line.strip().lstrip('• ').strip() 
                                   for line in edited_recomendacoes.split('\n') 
                                   if line.strip()]
        
        confirm_button = st.form_submit_button("💾 Salvar Incidente", type="primary")
        
        if confirm_button:
            if not all([edited_evento_resumo, edited_data_evento, edited_o_que_aconteceu]):
                st.error("❌ Todos os campos obrigatórios devem ser preenchidos.")
            else:
                save_incident_data(
                    edited_evento_resumo,
                    edited_data_evento,
                    edited_o_que_aconteceu,
                    edited_por_que_aconteceu,
                    edited_recomendacoes_list,
                    data
                )

def save_incident_data(evento_resumo, data_evento, o_que_aconteceu, por_que_aconteceu, recomendacoes, original_data):
    """
    Salva os dados do incidente no banco de dados.
    """
    try:
        with st.spinner("💾 Salvando incidente..."):
            # Upload dos arquivos
            storage = SupabaseStorage()
            
            # Upload do PDF
            pdf_file_obj = BytesIO(original_data['pdf_file_bytes'])
            pdf_file_obj.name = original_data['pdf_file_name']
            # pdf_file_obj.type não é necessário para BytesIO
            pdf_url = storage.upload_restricted_attachment(pdf_file_obj)
            
            # Upload da foto se disponível
            photo_url = None
            if original_data.get('photo_file_bytes'):
                photo_file_obj = BytesIO(original_data['photo_file_bytes'])
                photo_file_obj.name = original_data['photo_file_name']
                # photo_file_obj.type não é necessário para BytesIO
                photo_url = storage.upload_public_image(photo_file_obj)
            
            if not pdf_url:
                st.error("❌ Falha no upload do PDF.")
                return
            
            # Salva no banco de dados
            incident_manager = get_incident_manager()
            
            # Usa o método add_incident existente
            incident_id = incident_manager.add_incident(
                numero_alerta=original_data['numero_alerta'],
                evento_resumo=evento_resumo,
                data_evento=data_evento,
                o_que_aconteceu=o_que_aconteceu,
                por_que_aconteceu=por_que_aconteceu,
                foto_url=photo_url or "",
                anexos_url=pdf_url
            )
            
            if incident_id:
                st.success("✅ Incidente salvo com sucesso!")
                st.balloons()
                
                # Limpa os dados da sessão
                st.session_state.pdf_processing_complete = False
                st.session_state.pdf_processor_data = None
                
                # Log da ação
                log_action("INCIDENT_SAVED", {
                    "alert_number": original_data['numero_alerta'],
                    "user": get_user_email(),
                    "method": "Tradicional"
                })
                
                st.rerun()
            else:
                st.error("❌ Falha ao salvar no banco de dados.")
    
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")
        log_action("INCIDENT_SAVE_FAILURE", {
            "alert_number": original_data['numero_alerta'],
            "user": get_user_email(),
            "error": str(e)
        })

def show_pdf_processor_help():
    """
    Mostra informações de ajuda sobre o processador de PDFs.
    """
    with st.expander("ℹ️ Como usar o Processador de PDFs"):
        st.markdown("""
        **O Processador de PDFs extrai automaticamente informações de documentos de incidentes SSMA:**
        
        📄 **Formatos suportados:** PDF
        🔍 **Dados extraídos:**
        - Resumo do evento
        - Data do incidente
        - Descrição do que aconteceu
        - Análise de causa
        - Recomendações
        
        **Como usar:**
        1. Preencha o número do alerta
        2. Faça upload do PDF do incidente
        3. (Opcional) Anexe uma foto
        4. Clique em "Processar Documento"
        5. Revise e confirme os dados extraídos
        6. Salve o incidente
        
        **Dicas:**
        - O sistema funciona melhor com PDFs bem estruturados
        - Sempre revise os dados extraídos antes de salvar
        - Você pode editar qualquer campo antes de confirmar
        """)

# Função principal da página
def display_pdf_processor_page():
    """
    Exibe a página completa do processador de PDFs.
    """
    show_pdf_processor_help()
    show_pdf_processor_page()
    show_confirmation_form()
