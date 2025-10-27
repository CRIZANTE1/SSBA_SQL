import streamlit as st
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
from io import BytesIO

try:
    import PyPDF2
    import pdfplumber
    import fitz  # PyMuPDF
    from pdf2image import convert_from_bytes
    from PIL import Image
    PDF_LIBRARIES_AVAILABLE = True
except ImportError as e:
    PDF_LIBRARIES_AVAILABLE = False
    st.warning(f"Bibliotecas de PDF não disponíveis: {e}")

logger = logging.getLogger('pdf_processor')

class PDFProcessor:
    """
    Classe especializada para processamento de PDFs de incidentes SSMA.
    Oferece múltiplas estratégias de extração de dados.
    """
    
    def __init__(self):
        if not PDF_LIBRARIES_AVAILABLE:
            raise ImportError("Bibliotecas de PDF necessárias não estão instaladas")
    
    def extract_incident_data(self, pdf_file, use_ai: bool = False) -> Dict:
        """
        Extrai dados de incidente do PDF usando diferentes estratégias.
        
        Args:
            pdf_file: Arquivo PDF carregado pelo Streamlit
            use_ai: Se True, usa IA (apenas para admins). Se False, usa processamento tradicional.
        
        Returns:
            Dict com os dados extraídos do incidente
        """
        if use_ai:
            return self._extract_with_ai(pdf_file)
        else:
            return self._extract_with_traditional_methods(pdf_file)
    
    def _extract_with_ai(self, pdf_file) -> Dict:
        """
        Extrai dados usando IA (método original).
        Disponível apenas para administradores.
        """
        try:
            from AI.api_Operation import PDFQA
            
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
                files=[pdf_file],
                question=prompt,
                task_type='extraction'
            )
            
            if analysis_result and isinstance(analysis_result, dict):
                return analysis_result
            else:
                raise ValueError("IA não retornou dados válidos")
                
        except Exception as e:
            logger.error(f"Erro na extração com IA: {e}")
            st.error(f"Erro na análise com IA: {e}")
            # Fallback para método tradicional
            return self._extract_with_traditional_methods(pdf_file)
    
    def _extract_with_traditional_methods(self, pdf_file) -> Dict:
        """
        Extrai dados usando bibliotecas especializadas de PDF.
        Método principal para usuários normais.
        """
        try:
            # Lê o PDF usando pdfplumber (melhor para tabelas e texto estruturado)
            with pdfplumber.open(BytesIO(pdf_file.getvalue())) as pdf:
                full_text = ""
                tables = []
                
                for page in pdf.pages:
                    # Extrai texto da página
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"
                    
                    # Extrai tabelas da página
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
            
            # Processa o texto extraído
            incident_data = self._parse_incident_text(full_text, tables)
            
            return incident_data
            
        except Exception as e:
            logger.error(f"Erro na extração tradicional: {e}")
            st.error(f"Erro ao processar PDF: {e}")
            return self._get_default_incident_data()
    
    def _parse_incident_text(self, text: str, tables: List) -> Dict:
        """
        Analisa o texto extraído do PDF para encontrar informações específicas.
        """
        # Normaliza o texto
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text)
        
        # Extrai informações usando regex
        incident_data = {
            'evento_resumo': self._extract_event_summary(text),
            'data_evento': self._extract_event_date(text),
            'o_que_aconteceu': self._extract_what_happened(text),
            'por_que_aconteceu': self._extract_why_happened(text),
            'recomendacoes': self._extract_recommendations(text, tables)
        }
        
        return incident_data
    
    def _extract_event_summary(self, text: str) -> str:
        """Extrai resumo do evento"""
        # Procura por padrões comuns de títulos de incidente
        patterns = [
            r'INCIDENTE[:\s]+([^\.]+)',
            r'ALERTA[:\s]+([^\.]+)',
            r'EVENTO[:\s]+([^\.]+)',
            r'OCORRÊNCIA[:\s]+([^\.]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: pega as primeiras palavras do texto
        words = text.split()[:10]
        return ' '.join(words) if words else "Incidente não identificado"
    
    def _extract_event_date(self, text: str) -> str:
        """Extrai data do evento"""
        # Padrões de data brasileira
        date_patterns = [
            r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})',
            r'(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})',
            r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    if len(match.groups()) == 3:
                        day, month, year = match.groups()
                        # Converte para formato ISO
                        if len(year) == 4:
                            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                except:
                    continue
        
        # Fallback: data atual
        return datetime.now().strftime("%Y-%m-%d")
    
    def _extract_what_happened(self, text: str) -> str:
        """Extrai seção 'O que aconteceu'"""
        patterns = [
            r'O QUE ACONTECEU[:\s]*([^P]+?)(?=POR QUE|RECOMENDAÇÕES|FIM|$)',
            r'DESCRIÇÃO DO EVENTO[:\s]*([^P]+?)(?=POR QUE|RECOMENDAÇÕES|FIM|$)',
            r'FATO[:\s]*([^P]+?)(?=POR QUE|RECOMENDAÇÕES|FIM|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return "Descrição não encontrada no documento"
    
    def _extract_why_happened(self, text: str) -> str:
        """Extrai seção 'Por que aconteceu'"""
        patterns = [
            r'POR QUE ACONTECEU[:\s]*([^R]+?)(?=RECOMENDAÇÕES|O QUE FAZER|FIM|$)',
            r'CAUSA[:\s]*([^R]+?)(?=RECOMENDAÇÕES|O QUE FAZER|FIM|$)',
            r'ANÁLISE[:\s]*([^R]+?)(?=RECOMENDAÇÕES|O QUE FAZER|FIM|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return "Análise de causa não encontrada no documento"
    
    def _extract_recommendations(self, text: str, tables: List) -> List[str]:
        """Extrai recomendações do texto e tabelas"""
        recommendations = []
        
        # Procura por seções de recomendações no texto
        patterns = [
            r'O QUE FAZER PARA EVITAR[:\s]*([^$]+)',
            r'RECOMENDAÇÕES[:\s]*([^$]+)',
            r'MEDIDAS PREVENTIVAS[:\s]*([^$]+)',
            r'AÇÕES CORRETIVAS[:\s]*([^$]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                rec_text = match.group(1).strip()
                # Divide em itens por quebras de linha ou números
                items = re.split(r'\n|\d+[\.\)]\s*', rec_text)
                for item in items:
                    item = item.strip()
                    if item and len(item) > 10:  # Filtra itens muito curtos
                        recommendations.append(item)
        
        # Procura por recomendações em tabelas
        for table in tables:
            for row in table:
                for cell in row:
                    if cell and isinstance(cell, str):
                        cell_text = cell.strip()
                        if any(keyword in cell_text.lower() for keyword in 
                               ['recomendação', 'medida', 'ação', 'prevenção', 'correção']):
                            if len(cell_text) > 10:
                                recommendations.append(cell_text)
        
        # Remove duplicatas e limita a 10 recomendações
        unique_recommendations = list(dict.fromkeys(recommendations))[:10]
        
        return unique_recommendations if unique_recommendations else ["Recomendações não encontradas no documento"]
    
    def _get_default_incident_data(self) -> Dict:
        """Retorna dados padrão em caso de erro"""
        return {
            'evento_resumo': "Incidente não identificado",
            'data_evento': datetime.now().strftime("%Y-%m-%d"),
            'o_que_aconteceu': "Descrição não disponível",
            'por_que_aconteceu': "Análise não disponível",
            'recomendacoes': ["Recomendações não disponíveis"]
        }
    
    def generate_pdf_preview(self, pdf_file, max_pages: int = 3) -> List[Image.Image]:
        """
        Gera preview visual do PDF para exibição.
        
        Args:
            pdf_file: Arquivo PDF
            max_pages: Número máximo de páginas para preview
        
        Returns:
            Lista de imagens PIL das páginas
        """
        try:
            images = convert_from_bytes(
                pdf_file.getvalue(),
                first_page=1,
                last_page=max_pages,
                dpi=150
            )
            return images
        except Exception as e:
            logger.error(f"Erro ao gerar preview: {e}")
            return []
    
    def validate_pdf_structure(self, pdf_file) -> Tuple[bool, str]:
        """
        Valida se o PDF tem a estrutura esperada para incidentes SSMA.
        
        Returns:
            Tuple (is_valid, message)
        """
        try:
            with pdfplumber.open(BytesIO(pdf_file.getvalue())) as pdf:
                if len(pdf.pages) == 0:
                    return False, "PDF não contém páginas"
                
                # Extrai texto da primeira página
                first_page_text = pdf.pages[0].extract_text() or ""
                first_page_text = first_page_text.lower()
                
                # Verifica se contém palavras-chave de incidente
                incident_keywords = ['incidente', 'alerta', 'ocorrência', 'evento', 'ssma']
                has_keywords = any(keyword in first_page_text for keyword in incident_keywords)
                
                if not has_keywords:
                    return False, "PDF não parece ser um documento de incidente SSMA"
                
                return True, "PDF válido para processamento"
                
        except Exception as e:
            return False, f"Erro ao validar PDF: {e}"
