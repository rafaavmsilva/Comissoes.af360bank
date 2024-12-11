from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from datetime import datetime, timedelta
from functools import wraps
import os
from auth_client import AuthClient
import pandas as pd
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional
import os
from werkzeug.utils import secure_filename
import logging
from logging.handlers import RotatingFileHandler
from flask_session import Session
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from PIL import Image
import io
import pdfkit
import fitz
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from fpdf import FPDF
import locale
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import inch
from xhtml2pdf import pisa
from io import BytesIO
import imgkit
from PIL import Image, ImageEnhance
import tempfile
import os
import numpy as np
from PIL import Image, ImageEnhance
import cv2

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)  # Set session lifetime to 1 hour

# Initialize auth client
auth = AuthClient(
    auth_server_url='https://af360bank.onrender.com',  # Change this to your AF360 Bank auth server URL in production
)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect('https://af360bank.onrender.com/login')
        return f(*args, **kwargs)
    return decorated_function

@app.route('/auth')
def auth_route():
    token = request.args.get('token')
    if not token or not auth.verify_token(token):
        return redirect('https://af360bank.onrender.com/login')
    
    # Set session variables
    session['authenticated'] = True
    session.permanent = True  # Make the session last longer
    
    return redirect(url_for('index'))

@app.route('/')
@login_required
def index():
    """Handle the main page and file upload."""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)
            
        if file and is_valid_file(file.filename):
            try:
                dados = read_file(file)
                if dados:
                    session['dados'] = dados
                    flash('Arquivo carregado com sucesso!', 'success')
                    return redirect(url_for('dados'))
                else:
                    flash('O arquivo está vazio ou não contém dados válidos', 'error')
            except Exception as e:
                app.logger.error(f'Erro ao processar arquivo: {str(e)}')
                flash('Erro ao processar o arquivo. Verifique o formato e tente novamente.', 'error')
        else:
            flash('Tipo de arquivo não suportado. Use arquivos CSV ou Excel.', 'error')
            
    return render_template('Index.html')

@app.route('/dados')
@login_required
def dados():
    """Display uploaded data."""
    dados = session.get('dados')
    if not dados:
        return render_template('error.html')
    return render_template('dados.html', dados=dados)

@app.route('/comissoes')
@login_required
def comissoes():
    """Calculate and display commissions."""
    try:
        # Check if we have data
        dados = session.get('dados')
        if not dados:
            flash('Nenhum dado encontrado. Por favor, faça o upload do arquivo primeiro.', 'error')
            return redirect(url_for('index'))
        
        # Calculate commissions
        comissoes = calcular_comissoes(dados)
        if not comissoes:
            flash('Não foi possível calcular as comissões. Verifique os dados e tente novamente.', 'error')
            return redirect(url_for('index'))
        
        session['comissoes'] = comissoes
        
        # Get unique tables and users for filters
        tabelas = sorted(list(set(item.get('Tabela', '') for item in dados if item.get('Tabela'))))
        usuarios = sorted(list(set(item.get('Usuario', item.get('Usuário', '')) for item in dados if item.get('Usuario') or item.get('Usuário'))))
        
        # Calculate totals
        total_bruto = sum(float(item.get('Valor Bruto', 0)) for item in comissoes.values())
        total_liquido = sum(float(item.get('Valor Líquido', 0)) for item in comissoes.values())
        total_comissao_recebida = sum(float(item.get('comissao_recebida_valor', 0)) for item in comissoes.values())
        total_comissao_repassada = sum(float(item.get('comissao_repassada_valor', 0)) for item in comissoes.values())
        
        # Get errors if any
        erros = session.get('erros_comissoes', [])
        if erros:
            flash(f'Foram encontrados {len(erros)} problemas durante o processamento. Verifique os detalhes na tabela.', 'warning')
        
        # Convert dict_values to list before passing to template
        comissoes_list = list(comissoes.values())
        
        return render_template('comissoes.html', 
                             comissoes=comissoes_list, 
                             tabelas=tabelas,
                             usuarios=usuarios,
                             erros=erros,
                             totais={
                                 'bruto': total_bruto,
                                 'liquido': total_liquido,
                                 'comissao_recebida': total_comissao_recebida,
                                 'comissao_repassada': total_comissao_repassada
                             })
            
    except Exception as e:
        app.logger.error(f'Erro na rota /comissoes: {str(e)}')
        flash('Ocorreu um erro inesperado. Por favor, tente novamente.', 'error')
        return redirect(url_for('index'))

@app.route('/tabela', methods=['GET'])
@login_required
def tabela():
    """Render the table configuration page."""
    dados = session.get('dados')
    if not dados:
        return render_template('error.html')
        
    # Get unique tables from the data
    tabelas = sorted(list(set(item['Tabela'] for item in dados if item.get('Tabela'))))
    
    # Get existing configuration
    tabela_config = session.get('tabela_config', {})
    
    # Prepare table data for template
    tabelas_data = {}
    for tabela in tabelas:
        config = tabela_config.get(tabela, {})
        tabelas_data[tabela] = {
            'comissao_recebida': config.get('comissao_recebida', 0),
            'comissao_repassada': config.get('comissao_repassada', 0)
        }
    
    return render_template('tabela.html', tabelas=tabelas_data)

@app.route('/salvar_tabela', methods=['POST'])
@login_required
def salvar_tabela():
    """Save table configuration for both percentage-based and fixed commission."""
    try:
        tabela = request.form.get('tabela') or request.form.get('tabela_fixa')
        if not tabela:
            flash('Por favor, selecione uma tabela', 'error')
            return redirect(url_for('tabela'))
            
        # Check if it's fixed or percentage commission
        if request.form.get('comissao_fixa_recebida') is not None:
            # Fixed commission
            try:
                comissao_fixa_recebida = float(request.form.get('comissao_fixa_recebida', 0))
                comissao_fixa_repassada = float(request.form.get('comissao_fixa_repassada', 0))
            except ValueError:
                flash('Valores de comissão fixa inválidos', 'error')
                return redirect(url_for('tabela'))
                
            if comissao_fixa_recebida < 0 or comissao_fixa_repassada < 0:
                flash('Os valores de comissão não podem ser negativos', 'error')
                return redirect(url_for('tabela'))
                
            if comissao_fixa_repassada > comissao_fixa_recebida:
                flash('A comissão repassada não pode ser maior que a recebida', 'error')
                return redirect(url_for('tabela'))
                
            config = session.get('tabela_config', {})
            config[tabela] = {
                'tipo_comissao': 'fixa',
                'comissao_recebida': 0,
                'comissao_repassada': 0,
                'comissao_fixa_recebida': comissao_fixa_recebida,
                'comissao_fixa_repassada': comissao_fixa_repassada
            }
        else:
            # Percentage commission
            try:
                comissao_recebida = float(request.form.get('comissao_recebida', 0))
                comissao_repassada = float(request.form.get('comissao_repassada', 0))
            except ValueError:
                flash('Valores de comissão inválidos', 'error')
                return redirect(url_for('tabela'))
                
            if comissao_recebida < 0 or comissao_repassada < 0:
                flash('Os valores de comissão não podem ser negativos', 'error')
                return redirect(url_for('tabela'))
                
            if comissao_recebida > 100 or comissao_repassada > 100:
                flash('Os valores de comissão não podem ser maiores que 100%', 'error')
                return redirect(url_for('tabela'))
                
            if comissao_repassada > comissao_recebida:
                flash('A comissão repassada não pode ser maior que a recebida', 'error')
                return redirect(url_for('tabela'))
                
            config = session.get('tabela_config', {})
            config[tabela] = {
                'tipo_comissao': 'percentual',
                'comissao_recebida': comissao_recebida,
                'comissao_repassada': comissao_repassada
            }
        
        session['tabela_config'] = config
        session.modified = True
        
        flash(f'Configuração para tabela {tabela} salva com sucesso!', 'success')
        return redirect(url_for('comissoes'))
        
    except Exception as e:
        app.logger.error(f'Erro ao salvar configuração: {str(e)}')
        flash('Erro ao salvar configuração', 'error')
        return redirect(url_for('tabela'))

@app.route('/resultado')
@login_required
def resultado():
    """Display contract details."""
    dados = session.get('dados')
    if not dados:
        flash('Nenhum dado carregado. Por favor, faça o upload de um arquivo CSV primeiro.', 'error')
        return redirect(url_for('index'))

    ccb = request.args.get('ccb') if request.method == 'GET' else request.form.get('ccb')
    if not ccb:
        flash('Por favor, forneça um número de CCB válido', 'error')
        return redirect(url_for('busca'))
    
    # Tenta encontrar nos dados brutos primeiro
    contrato_raw = None
    ccb_str = str(ccb).strip()
    
    # Procura nos dados brutos
    for item in dados:
        if str(item.get('CCB', '')).strip() == ccb_str:
            contrato_raw = item
            break
    
    # Se não encontrou nos dados brutos, tenta nas comissões
    if not contrato_raw:
        comissoes = session.get('comissoes', {})
        contrato_raw = comissoes.get(ccb_str)
    
    if contrato_raw:
        # Restructure the data for the template
        contrato = {
            'Informações Básicas': {
                'Nome': contrato_raw.get('Nome', 'N/A'),
                'CPF': contrato_raw.get('CPF/CNPJ', 'N/A'),
                'Tabela': contrato_raw.get('Tabela', 'N/A'),
                'Parcelas': contrato_raw.get('Parcelas', 'N/A'),
                'Valor Parcela': format_currency(contrato_raw.get('Valor Parcela')),
                'Valor Bruto': format_currency(contrato_raw.get('Valor Bruto')),
                'Valor Líquido': format_currency(contrato_raw.get('Valor Líquido')),
                'Link de assinatura': contrato_raw.get('Link de assinatura', ''),
                'Parceiro': contrato_raw.get('Parceiro', 'N/A'),
                'Usuário': contrato_raw.get('Usuário', 'N/A'),
                'Status': contrato_raw.get('Status', 'N/A')
            }
        }
        
        return render_template('resultado.html', contrato=contrato, ccb=ccb)
    
    flash('CCB não encontrada. Verifique se o número está correto.', 'error')
    return redirect(url_for('busca'))

@app.route('/busca')
@login_required
def busca():
    """Render the search page."""
    dados = session.get('dados')
    if not dados:
        return render_template('error.html')
    return render_template('busca.html')

from datetime import datetime

@app.route('/preview_ccbs')
def preview_ccbs():
    if 'usuario' not in session:
        return redirect(url_for('busca'))
    
    usuario = session['usuario']
    ccbs = session.get('ccbs', [])
    
    return render_template('print_usuario_ccbs.html', usuario=usuario, ccbs=ccbs)

@app.route('/usuario_ccbs')
def usuario_ccbs():
    if 'usuario' not in session:
        return redirect(url_for('busca'))
    
    usuario = session['usuario']
    ccbs = session.get('ccbs', [])
    
    return render_template('usuario_ccbs.html', usuario=usuario, ccbs=ccbs, preview_url=url_for('preview_ccbs'))

def carregar_dados():
    """Load data from session."""
    return session.get('dados', [])

@app.route('/verificar_ccb/<ccb>')
def verificar_ccb(ccb):
    try:
        dados = carregar_dados()
        if not dados:
            return jsonify({'exists': False, 'error': 'Nenhum dado carregado'})
        
        exists = any(str(linha.get('CCB', '')).strip() == str(ccb).strip() for linha in dados)
        return jsonify({'exists': exists})
    except Exception as e:
        app.logger.error(f"Error checking CCB {ccb}: {str(e)}")
        return jsonify({'exists': False, 'error': 'Erro ao verificar CCB'})

@app.route('/limpar_dados', methods=['POST'])
def limpar_dados():
    """Clear all session data."""
    try:
        session.clear()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def generate_dark_pdf(output_path, usuario, ccbs):
    """Generate PDF directly using ReportLab with maximum darkness settings"""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    
    # Create story for elements
    story = []
    
    # Create custom styles
    styles = getSampleStyleSheet()
    
    # Extra dark title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=30,
        textColor=colors.black,
        borderWidth=2,
        borderColor=colors.black,
        borderPadding=10,
        leading=30
    )
    
    # Extra dark header style
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.black,
        leading=20,
        borderWidth=1,
        borderColor=colors.black,
        borderPadding=5
    )
    
    # Extra dark normal text style
    text_style = ParagraphStyle(
        'CustomText',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.black,
        leading=15
    )
    
    # Add title
    story.append(Paragraph(f"Relatório de CCBs - {usuario}", title_style))
    story.append(Spacer(1, 20))
    
    # Prepare table data
    table_data = [['Número', 'Valor', 'Data de Vencimento', 'Taxa', 'Valor Total']]
    
    # Add CCB data
    for ccb in ccbs:
        row = [
            str(ccb.get('numero', '')),
            f"R$ {ccb.get('valor', 0):,.2f}",
            ccb.get('data_vencimento', ''),
            f"{ccb.get('taxa', 0):.2f}%",
            f"R$ {ccb.get('valor_total', 0):,.2f}"
        ]
        table_data.append(row)
    
    # Create table with thick borders and dark text
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        # Extra thick outer border
        ('BOX', (0, 0), (-1, -1), 2.5, colors.black),
        
        # Extra thick inner borders
        ('INNERGRID', (0, 0), (-1, -1), 1.5, colors.black),
        
        # Dark header background
        ('BACKGROUND', (0, 0), (-1, 0), colors.black),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        
        # Extra dark text for data cells
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        
        # Bold all text
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        
        # Cell padding
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        
        # Extra alignment
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(table)
    
    # Add summary section
    story.append(Spacer(1, 30))
    
    # Calculate totals
    total_valor = sum(ccb.get('valor', 0) for ccb in ccbs)
    total_valor_total = sum(ccb.get('valor_total', 0) for ccb in ccbs)
    
    # Add summary with thick borders
    summary_style = ParagraphStyle(
        'Summary',
        parent=text_style,
        fontSize=14,
        borderWidth=2,
        borderColor=colors.black,
        borderPadding=10,
        backColor=colors.white
    )
    
    story.append(Paragraph(
        f"""
        <b>Resumo:</b><br/>
        Número total de CCBs: {len(ccbs)}<br/>
        Valor total inicial: R$ {total_valor:,.2f}<br/>
        Valor total com juros: R$ {total_valor_total:,.2f}
        """,
        summary_style
    ))
    
    # Generate PDF
    doc.build(story)

@app.route('/generate_pdf/<template_name>')
def generate_pdf(template_name):
    try:
        if template_name == 'usuario_ccbs':
            if 'usuario' not in session:
                return redirect(url_for('busca'))
            
            usuario = session['usuario']
            ccbs = session.get('ccbs', [])
            
            # Create temporary file for PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
                # Generate PDF directly
                generate_dark_pdf(pdf_file.name, usuario, ccbs)
                
                # Read the generated PDF
                with open(pdf_file.name, 'rb') as f:
                    pdf_content = f.read()
                
                # Clean up
                try:
                    os.unlink(pdf_file.name)
                except Exception as e:
                    app.logger.error(f'Error deleting temporary file {pdf_file.name}: {str(e)}')
                
                # Create response
                response = make_response(pdf_content)
                response.headers['Content-Type'] = 'application/pdf'
                response.headers['Content-Disposition'] = f'attachment; filename=CCBs_{usuario}.pdf'
                return response

    except Exception as e:
        app.logger.error(f'Error generating PDF: {str(e)}')
        flash('Erro ao gerar PDF. Por favor, tente novamente.', 'error')
        return redirect(url_for('usuario_ccbs'))

@app.route('/print_view/<template_name>')
def print_view(template_name):
    if template_name == 'usuario_ccbs':
        if 'usuario' not in session:
            return redirect(url_for('busca'))
        usuario = session['usuario']
        ccbs = session.get('ccbs', [])
        return render_template('print_usuario_ccbs.html', usuario=usuario, ccbs=ccbs)
    return redirect(url_for('index'))

@app.route('/print_comissoes')
def print_comissoes():
    """Render the print view for comissoes."""
    try:
        # Get selected user from query parameter
        selected_user = request.args.get('usuario', '')
        
        # Get existing comissoes from session
        comissoes = session.get('comissoes')
        if not comissoes:
            flash('Nenhum dado de comissão encontrado.', 'error')
            return redirect(url_for('comissoes'))
        
        # Convert dict_values to list
        if isinstance(comissoes, dict):
            comissoes_list = list(comissoes.values())
        else:
            comissoes_list = comissoes
            
        # Filter by user if specified
        if selected_user and selected_user.strip():
            filtered_list = []
            for item in comissoes_list:
                user = item.get('Usuário') or item.get('Usuario', '')
                if user and user.lower() == selected_user.lower():
                    filtered_list.append(item)
            comissoes_list = filtered_list
            
        if not comissoes_list:
            flash('Nenhuma comissão encontrada para o usuário selecionado.', 'error')
            return redirect(url_for('comissoes'))
            
        # Log the data being passed to template
        app.logger.info(f"Passing {len(comissoes_list)} comissões to template")
        app.logger.info(f"Sample comissão: {comissoes_list[0] if comissoes_list else 'No data'}")
        
        # Ensure all required fields are present
        for item in comissoes_list:
            if not item.get('Cliente'):
                nome = item.get('Nome', item.get('nome', ''))
                documento = item.get('Documento', item.get('documento', item.get('CPF', '')))
                item['Cliente'] = format_client_name(nome, documento)
        
        return render_template('print_comissoes.html', comissoes=comissoes_list)
            
    except Exception as e:
        app.logger.error(f'Erro detalhado na rota /print_comissoes: {str(e)}', exc_info=True)
        flash(f'Ocorreu um erro ao gerar a visualização de impressão: {str(e)}', 'error')
        return redirect(url_for('comissoes'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))