from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from sqlalchemy import Column, Integer, String, Float
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
from flask_sqlalchemy import SQLAlchemy
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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Frame, PageTemplate
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
import csv
import json

# Global variable to store uploaded data
uploaded_data = []

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///temp_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
Session(app)
db = SQLAlchemy(app)

class UploadedData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ccb = db.Column(db.String(80))
    data_digitacao = db.Column(db.String(80))
    data_desembolso = db.Column(db.String(80))
    cpf_cnpj = db.Column(db.String(80))
    nome = db.Column(db.String(80))
    tabela = db.Column(db.String(80))
    parcelas = db.Column(db.Integer)
    valor_parcela = db.Column(db.Float)
    valor_bruto = db.Column(db.Float)
    valor_liquido = db.Column(db.Float)
    link_assinatura = db.Column(db.String(255))
    parceiro = db.Column(db.String(80))
    usuario = db.Column(db.String(80))
    email = db.Column(db.String(80))
    status = db.Column(db.String(80))
    data_nascimento_fundacao = db.Column(db.String(80))

# Create the table if it doesn't exist
with app.app_context():
    db.create_all()

# Define the Contrato model
class Contrato(db.Model):
    __tablename__ = 'contrato'  # Explicitly specify the table name if necessary
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), nullable=False)
    valor = db.Column(db.Float, nullable=False)

# Initialize auth client
auth_client = AuthClient(
    auth_server_url=os.getenv('AUTH_SERVER_URL', 'https://af360bank.onrender.com'),
    app_name=os.getenv('APP_NAME', 'sistema-comissoes')
)
auth_client.init_app(app)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect('https://af360bank.onrender.com/login')
        return f(*args, **kwargs)
    return decorated_function

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')
    
# Ensure the logs directory exists
if not app.debug:
    # Create a file handler
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('App startup')

# Configure debug logging
if app.debug:
    app.logger.setLevel(logging.DEBUG)

@app.before_request
def before_request():
    """Ensure session is initialized with required data structures."""
    # Initialize session data if not exists
    if 'dados' not in session:
        session['dados'] = []
    if 'comissoes' not in session:
        session['comissoes'] = {}
    if 'tabela_config' not in session:
        session['tabela_config'] = {}
        set_default_commission_config()
    
    # Always mark session as modified to ensure changes are saved
    session.modified = True

@app.route('/auth')
def auth():
    token = request.args.get('token')
    if not token:
        return redirect('https://af360bank.onrender.com/login')
    
    verification = auth_client.verify_token(token)
    if not verification or not verification.get('valid'):
        return redirect('https://af360bank.onrender.com/login')
    
    # Set session variables
    session['token'] = token
    session['authenticated'] = True
    session.permanent = True
    return redirect(url_for('index'))

def set_default_commission_config():
    """Set default commission configurations for different tables."""
    date_threshold = datetime.strptime('28/01/2025', '%d/%m/%Y')
    current_date = datetime.now()

    # Post 2025 configuration
    new_config = {
        'BRAVE 1 - 50 a 250': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 31,
            'comissao_repassada': 31,
            'valor_minimo': 50,
            'valor_maximo': 250
        },
        'BRAVE 2 - 250,01 - 3800': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 27,
            'comissao_repassada': 27,
            'valor_minimo': 250.01,
            'valor_maximo': 3800
        },
        'BRAVE 3 - 3800,01 - 30.000': {
            'tipo_comissao': 'fixa',
            'comissao_fixa_recebida': 2295,
            'comissao_fixa_repassada': 2295,
            'valor_minimo': 3800.01,
            'valor_maximo': 30000
        },
        'BRAVE DIFERENCIADA - COM REDUÇÃO': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 8,
            'comissao_repassada': 8,
            'valor_minimo': 0,
            'valor_maximo': float('inf')
        },
        'VIA INVEST 1 - 75 A 250': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 26,
            'comissao_repassada': 26,
            'valor_minimo': 75,
            'valor_maximo': 250
        },
        'VIA INVEST 2 - 250,01 A 1.000': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 21,
            'comissao_repassada': 21,
            'valor_minimo': 250.01,
            'valor_maximo': 1000
        },
        'VIA INVEST 3 - 1.000,01 A 30.000': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 15,
            'comissao_repassada': 15,
            'valor_minimo': 1000.01,
            'valor_maximo': 30000
        },
        'VIA INVEST DIF - COM REDUÇAO': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 12,
            'comissao_repassada': 12,
            'valor_minimo': 0,
            'valor_maximo': float('inf')
        },
    }

    # Pre 2025 configuration
    old_config = {
        'BRAVE 1 - 50 a 250': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 28,
            'comissao_repassada': 26,
            'valor_minimo': 50,
            'valor_maximo': 250
        },
        'BRAVE 2 - 250,01 - 3800': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 24,
            'comissao_repassada': 22,
            'valor_minimo': 250.01,
            'valor_maximo': 3800
        },
        'BRAVE 3 - 3800,01 - 30.000': {
            'tipo_comissao': 'fixa',
            'comissao_fixa_recebida': 1200,
            'comissao_fixa_repassada': 1050,
            'valor_minimo': 3800.01,
            'valor_maximo': 30000
        },
        'BRAVE DIFERENCIADA - COM REDUÇÃO': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 8,
            'comissao_repassada': 6,
            'valor_minimo': 0,
            'valor_maximo': float('inf')
        },
        'VIA INVEST 1 - 75 A 250': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 26,
            'comissao_repassada': 24,
            'valor_minimo': 75,
            'valor_maximo': 250
        },
        'VIA INVEST 2 - 250,01 A 1.000': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 21,
            'comissao_repassada': 19,
            'valor_minimo': 250.01,
            'valor_maximo': 1000
        },
        'VIA INVEST 3 - 1.000,01 A 30.000': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 15,
            'comissao_repassada': 13,
            'valor_minimo': 1000.01,
            'valor_maximo': 30000
        },
        'VIA INVEST DIF - COM REDUÇAO': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 10,
            'comissao_repassada': 8,
            'valor_minimo': 0,
            'valor_maximo': float('inf')
        },
    }
    # Common configuration
    common_config = {
        'NÃO COMISSIONADO': {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 0,
            'comissao_repassada': 0,
            'valor_minimo': 0,
            'valor_maximo': float('inf')
        }
    }

    # Select configuration based on date
    base_config = old_config if current_date < date_threshold else new_config
    
    # Merge with common configuration
    base_config.update(common_config)
    
    session['tabela_config'] = base_config
    session.modified = True

def is_valid_file(filename: str) -> bool:
    """Validate if the file is a CSV or Excel file."""
    if not '.' in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ['csv', 'xls', 'xlsx']

def read_file(file):
    """Read CSV or Excel file into a pandas DataFrame."""
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file, encoding='utf-8-sig')
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        else:
            raise ValueError("Formato de arquivo não suportado")
        
        if df.empty:
            return None
            
        # Convert DataFrame to list of dictionaries
        dados = df.replace({pd.NA: None}).to_dict('records')
        
        # Log converted data
        app.logger.info(f"Converted data sample: {dados[:2] if dados else 'No data'}")
        
        return dados
    except Exception as e:
        app.logger.error(f"Erro ao ler arquivo: {str(e)}")
        raise e

def convert_to_float(value: str) -> float:
    """Convert a Brazilian currency string to float."""
    try:
        if value is None or pd.isna(value):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        # Remove any non-numeric characters except comma and dot
        value = ''.join(c for c in str(value) if c.isdigit() or c in '.,')
        if not value:  # Se não houver números após a limpeza
            return 0.0
        # Replace comma with dot for float conversion
        value = value.replace('.', '').replace(',', '.')
        if not value:  # Se ainda não houver números
            return 0.0
        return float(value)
    except Exception as e:
        app.logger.error(f'Erro ao converter valor {value} para float: {str(e)}')
        return 0.0

def format_currency(value: any) -> str:
    """Format a number as Brazilian currency."""
    if value is None or pd.isna(value):
        return ''
    try:
        if isinstance(value, str):
            value = convert_to_float(value)
        return f"R$ {float(value):,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
    except (ValueError, TypeError):
        return ''

def format_client_name(nome: str, documento: str) -> str:
    """Format client name with document number."""
    if not nome:
        return ''
    if documento:
        return f"{nome} ({documento})"
    return nome

def get_table_config(tabela: str, valor: float = None, data_transacao: datetime = None):
    """Get commission configuration for a table based on value range and date."""
    try:
        DATE_THRESHOLD = datetime.strptime('28/01/2025', '%d/%m/%Y')
        
        # Load both configs from session
        new_config = session.get('new_config', {})
        old_config = session.get('old_config', {})
        
        # Get the correct config based on date
        if data_transacao and data_transacao <= DATE_THRESHOLD:
            tabela_config = old_config  # Use pre-2025 config
        else:
            tabela_config = new_config  # Use post-2025 config
            
        # Default config
        default_config = {
            'tipo_comissao': 'percentual',
            'comissao_recebida': 0,
            'comissao_repassada': 0,
            'nome_tabela': tabela
        }
        
        # Get base config from table
        config = None
        if tabela in tabela_config:
            config = tabela_config[tabela].copy()
            config['nome_tabela'] = tabela
        else:
            for nome_tabela, cfg in tabela_config.items():
                if ('DIFERENCIADA' in tabela or 'DIF' in tabela) != ('DIFERENCIADA' in nome_tabela or 'DIF' in nome_tabela):
                    continue
                    
                mesma_empresa = (tabela.startswith('BRAVE') and nome_tabela.startswith('BRAVE')) or \
                              (tabela.startswith('VIA') and nome_tabela.startswith('VIA'))
                
                if mesma_empresa and valor:
                    valor_minimo = float(cfg.get('valor_minimo', 0))
                    valor_maximo = float(cfg.get('valor_maximo', float('inf')))
                    if valor_minimo <= valor <= valor_maximo:
                        config = cfg.copy()
                        config['nome_tabela'] = nome_tabela
                        break
        
        if not config:
            return default_config
            
        return config
        
    except Exception as e:
        app.logger.error(f'Erro ao obter configuração da tabela {tabela}: {str(e)}')
        return default_config

def calcular_comissoes(dados: List[Dict]):
    """Calculate commissions based on provided data and table configurations."""
    comissoes = {}
    erros = []
    DATE_THRESHOLD = datetime.strptime('28/01/2025', '%d/%m/%Y')
    
    try:
        for linha in dados:
            ccb = linha.get("CCB", "")
            erro_linha = {}
            
            # Parse transaction date
            data_str = linha.get('Data do Desembolso') or linha.get('Data Digitacao', '')
            
            # Format CCB as integer string
            ccb = str(int(float(linha.get("CCB", "0")))) if linha.get("CCB") else ""
            erro_linha = {}
            
            # Format client name
            nome = linha.get('Nome', '')
            documento = linha.get('CPF/CNPJ', '')
            linha['Cliente'] = format_client_name(nome, documento)
            
            try:
                if not data_str:
                    data_transacao = datetime.now()
                    erro_linha['data'] = 'Data não encontrada, usando data atual'
                else:
                    data_str = str(data_str).strip()
                    try:
                        if len(data_str) > 10 and '-' in data_str:
                            data_transacao = datetime.strptime(data_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        else:
                            data_transacao = datetime.strptime(data_str, '%d/%m/%Y')
                    except ValueError:
                        data_transacao = datetime.now()
                        erro_linha['data'] = f'Data inválida: {data_str}, usando data atual'
                
                linha['Data'] = data_transacao.strftime('%d/%m/%Y')
                
                # Process valores and get config
                valor_bruto = linha.get('Valor Bruto', 0)
                valor = convert_to_float(valor_bruto) if valor_bruto else 0
                tabela = linha.get('Tabela', '')
                
                # Get config with date
                config = get_table_config(tabela, valor, data_transacao)
                
                try:
                    tipo_comissao = config.get('tipo_comissao', 'percentual')
                    valor_liquido = convert_to_float(linha.get('Valor Líquido', 0))
                    
                    if tipo_comissao == 'fixa':
                        comissao_recebida_valor = float(config.get('comissao_fixa_recebida', 0))
                        comissao_repassada_valor = float(config.get('comissao_fixa_repassada', 0))
                        comissao_recebida_percentual = (comissao_recebida_valor / valor * 100) if valor > 0 else 0
                        comissao_repassada_percentual = (comissao_repassada_valor / valor_liquido * 100) if valor_liquido > 0 else 0
                    else:
                        comissao_recebida = float(config.get('comissao_recebida', 0))
                        comissao_repassada = float(config.get('comissao_repassada', 0))
                        comissao_recebida_valor = valor * (comissao_recebida / 100)
                        comissao_repassada_valor = valor_liquido * (comissao_repassada / 100)
                        comissao_recebida_percentual = comissao_recebida
                        comissao_repassada_percentual = comissao_repassada
                    
                    linha.update({
                        'comissao_recebida_valor': comissao_recebida_valor,
                        'comissao_repassada_valor': comissao_repassada_valor,
                        'comissao_recebida_percentual': comissao_recebida_percentual,
                        'comissao_repassada_percentual': comissao_repassada_percentual,
                        'tipo_comissao': tipo_comissao
                    })
                    
                except Exception as e:
                    erro_linha['calculo'] = f'Erro ao calcular comissões: {str(e)}'
                    linha.update({
                        'comissao_recebida_valor': 0,
                        'comissao_repassada_valor': 0,
                        'comissao_recebida_percentual': 0,
                        'comissao_repassada_percentual': 0
                    })
                
                comissoes[str(ccb)] = linha
                
                if erro_linha:
                    linha['erros'] = erro_linha
                    erros.append({'ccb': ccb, 'erros': erro_linha})
                
            except Exception as e:
                app.logger.error(f'Erro ao processar CCB {ccb}: {str(e)}')
                erro_linha['geral'] = f'Erro geral: {str(e)}'
                erros.append({'ccb': ccb, 'erros': erro_linha})
                continue

    except Exception as e:
        app.logger.error(f'Erro ao calcular comissões: {str(e)}')
        flash('Ocorreu um erro ao calcular as comissões.', 'error')
    
    session['erros_comissoes'] = erros
    return comissoes

@app.route('/', methods=['GET', 'POST'])
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
        
        # Convert dict_values to list and sort
        comissoes_list = list(comissoes.values())
        
        # Safe sorting function
        def get_sort_key(x):
            # Get usuario value, defaulting to empty string if None
            usuario = x.get('Usuario') or x.get('Usuário') or ''
            # Get date value, defaulting to '01/01/2000' if None
            data = x.get('Data') or '01/01/2000'
            return (usuario.lower(), datetime.strptime(data, '%d/%m/%Y'))
        
        # Sort using the safe function
        comissoes_list.sort(key=get_sort_key)
        
        # Get unique tables and users for filters
        tabelas = sorted(list(set(item.get('Tabela', '') for item in dados if item.get('Tabela'))))
        usuarios = sorted(list(set(
            item.get('Usuario', item.get('Usuário', '')) 
            for item in dados 
            if item.get('Usuario') or item.get('Usuário')
        )))
        
        # Calculate totals
        total_bruto = sum(float(item.get('Valor Bruto', 0)) for item in comissoes.values())
        total_liquido = sum(float(item.get('Valor Líquido', 0)) for item in comissoes.values())
        total_comissao_recebida = sum(float(item.get('comissao_recebida_valor', 0)) for item in comissoes.values())
        total_comissao_repassada = sum(float(item.get('comissao_repassada_valor', 0)) for item in comissoes.values())
        
        # Get errors if any
        erros = session.get('erros_comissoes', [])
        if erros:
            flash(f'Foram encontrados {len(erros)} problemas durante o processamento. Verifique os detalhes na tabela.', 'warning')
        
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
    
    return render_template('Tabela.html', tabelas=tabelas_data)

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
@login_required
def limpar_dados():
    try:
        # Clear all data from the database
        db.session.query(UploadedData).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Dados limpos com sucesso!'})
    except Exception as e:
        app.logger.error(f'Error clearing data: {str(e)}')
        return jsonify({'success': False, 'message': 'Erro ao limpar dados.'}), 500
    
# Function to load CSV data into memory
def load_csv_data(file_path):
    global uploaded_data
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        uploaded_data = [row for row in reader]

@app.route('/upload_csv', methods=['POST'])
@login_required
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400
    if file:
        uploaded_data = read_file(file)
        if uploaded_data is None:
            return jsonify({'success': False, 'message': 'No data found in the file'}), 400
        
        # Store the uploaded data in the database
        for row in uploaded_data:
            data_entry = UploadedData(
                ccb=row.get('CCB'),
                data_digitacao=row.get('Data de Digitação'),
                data_desembolso=row.get('Data do Desembolso'),
                cpf_cnpj=row.get('CPF/CNPJ'),
                nome=row.get('Nome'),
                tabela=row.get('Tabela'),
                parcelas=row.get('Parcelas'),
                valor_parcela=row.get('Valor da Parcela'),
                valor_bruto=row.get('Valor Bruto'),
                valor_liquido=row.get('Valor Líquido'),
                link_assinatura=row.get('Link de assinatura'),
                parceiro=row.get('Parceiro'),
                usuario=row.get('Usuário'),
                email=row.get('E-mail'),
                status=row.get('Status'),
                data_nascimento_fundacao=row.get('Data Nascimento/Fundação')
            )
            db.session.add(data_entry)
        db.session.commit()
        
        # Log the stored data for debugging
        stored_data = UploadedData.query.all()
        app.logger.info(f"Stored data: {[data.__dict__ for data in stored_data]}")

        return jsonify({'success': True, 'message': 'File uploaded and data loaded successfully'})
    
@app.route('/deletar_dados_usuario', methods=['POST'])
@login_required
def deletar_dados_usuario():
    try:
        data = request.get_json()
        usuario = data.get('usuario')
        if not usuario:
            return jsonify({'success': False, 'message': 'Usuário não especificado.'}), 400

        # Log the current data for debugging
        current_data = UploadedData.query.all()
        app.logger.info(f"Current data before deletion: {[data.__dict__ for data in current_data]}")

        # Delete user data from the database
        deleted_rows = UploadedData.query.filter_by(usuario=usuario).delete()
        db.session.commit()

        if deleted_rows == 0:
            return jsonify({'success': False, 'message': 'Nenhum dado encontrado para o usuário especificado.'}), 404

        # Log the remaining data for debugging
        remaining_data = UploadedData.query.all()
        app.logger.info(f"Remaining data after deletion: {[data.__dict__ for data in remaining_data]}")

        return jsonify({'success': True, 'message': 'Dados do usuário deletados com sucesso!'})
    except Exception as e:
        app.logger.error(f'Error deleting user data: {str(e)}')
        return jsonify({'success': False, 'message': 'Erro ao deletar dados do usuário.'}), 500

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

@app.route('/print_comissoes_2')
def print_comissoes_2():
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
        
        # Sort by usuario and date
        def get_sort_key(x):
            usuario = x.get('Usuario') or x.get('Usuário') or ''
            data = x.get('Data') or '01/01/2000'
            return (usuario.lower(), datetime.strptime(data, '%d/%m/%Y'))
        
        comissoes_list.sort(key=get_sort_key)
            
        if not comissoes_list:
            flash('Nenhuma comissão encontrada para o usuário selecionado.', 'error')
            return redirect(url_for('comissoes'))
            
        return render_template('print_comissoes_2.html', comissoes=comissoes_list)
            
    except Exception as e:
        app.logger.error(f'Erro detalhado na rota /print_comissoes_2: {str(e)}', exc_info=True)
        flash(f'Ocorreu um erro ao gerar a visualização de impressão: {str(e)}', 'error')
        return redirect(url_for('comissoes'))

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
            
        return render_template('print_comissoes.html', comissoes=comissoes_list)
            
    except Exception as e:
        app.logger.error(f'Erro detalhado na rota /print_comissoes: {str(e)}', exc_info=True)
        flash(f'Ocorreu um erro ao gerar a visualização de impressão: {str(e)}', 'error')
        return redirect(url_for('comissoes'))

def generate_dark_pdf_2(output_path, comissoes):
    """Generate PDF for comissoes without commission details"""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=170,  # Add top margin to prevent overlap with the logo
        bottomMargin=30
    )
    
    # Create a frame for the first page with the logo
    frame_first_page = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 170, id='first_page')
    
    # Create a frame for subsequent pages without the logo
    frame_other_pages = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='other_pages')
    
    # Define the first page template with the logo
    def first_page(canvas, doc):
        canvas.saveState()
        logo_path = r'C:\Users\marke\OneDrive\Área de Trabalho\comissoes af360bank online\Comissoes.af360bank\static\images\logo.png'
        if os.path.exists(logo_path):
            logo = ImageReader(logo_path)
            canvas.drawImage(logo, doc.leftMargin, A4[1] - 150, width=150, height=150)
        canvas.restoreState()
    
    # Define the page templates
    template_first_page = PageTemplate(id='first_page', frames=frame_first_page, onPage=first_page)
    template_other_pages = PageTemplate(id='other_pages', frames=frame_other_pages)
    
    doc.addPageTemplates([template_first_page, template_other_pages])
    
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=30,
        textColor=colors.black
    )
    
    story.append(Paragraph("Relatório de Comissões", title_style))
    story.append(Spacer(1, 20))
    
    # Table data
    table_data = [['CCB', 'Usuário', 'Cliente', 'Valor Bruto', 'Tabela', 'Repasse']]
    
    for index, comissao in enumerate(comissoes):
        row = [
            str(comissao.get('CCB', '')),
            str(comissao.get('Usuario', comissao.get('Usuário', ''))),
            str(comissao.get('Cliente', '')),
            f"R$ {comissao.get('Valor Bruto', 0):,.2f}",
            str(comissao.get('Tabela', '')),
            f"R$ {comissao.get('comissao_repassada_valor', 0):,.2f}"
        ]
        table_data.append(row)
        
        # Add a spacer after every 9 rows
        if (index + 1) % 9 == 0:
            story.append(Table(table_data, repeatRows=1))
            story.append(Spacer(1, 170))  # Add spacer with the same height as the logo
            table_data = [['CCB', 'Usuário', 'Cliente', 'Valor Bruto', 'Tabela', 'Repasse']]  # Reset table data
    
    # Add remaining table data
    if len(table_data) > 1:
        story.append(Table(table_data, repeatRows=1))
    
    story.append(Spacer(1, 30))
    
    # Calculate totals
    total_bruto = sum(comissao.get('Valor Bruto', 0) for comissao in comissoes)
    total_repasse = sum(comissao.get('comissao_repassada_valor', 0) for comissao in comissoes)
    
    # Add summary
    summary_style = ParagraphStyle(
        'Summary',
        parent=styles['Normal'],
        fontSize=14,
        borderWidth=2,
        borderColor=colors.black,
        borderPadding=10,
        backColor=colors.white
    )
    
    story.append(Paragraph(
        f"""
        <b>Resumo:</b><br/>
        Total de operações: {len(comissoes)}<br/>
        Valor total bruto: R$ {total_bruto:,.2f}<br/>
        Total de repasse: R$ {total_repasse:,.2f}
        """,
        summary_style
    ))
    
    doc.build(story)

@app.route('/generate_pdf_2/<template_name>')
def generate_pdf_2(template_name):
    try:
        if template_name == 'comissoes':
            comissoes = session.get('print_comissoes', [])
            
            # Create temporary file for PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
                # Generate PDF
                generate_dark_pdf_2(pdf_file.name, comissoes)
                
                # Read PDF
                with open(pdf_file.name, 'rb') as f:
                    pdf_content = f.read()
                
                # Cleanup
                try:
                    os.unlink(pdf_file.name)
                except Exception as e:
                    app.logger.error(f'Error deleting temporary file {pdf_file.name}: {str(e)}')
                
                # Return PDF
                response = make_response(pdf_content)
                response.headers['Content-Type'] = 'application/pdf'
                response.headers['Content-Disposition'] = 'attachment; filename=Comissoes_sem_comissao.pdf'
                return response

    except Exception as e:
        app.logger.error(f'Error generating PDF: {str(e)}')
        flash('Erro ao gerar PDF. Por favor, tente novamente.', 'error')
        return redirect(url_for('comissoes'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)