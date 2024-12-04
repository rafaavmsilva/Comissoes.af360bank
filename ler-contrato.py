import pandas as pd

def ler_contrato(arquivo_excel):
    """
    Ler arquivo Excel e retornar dados de contrato.
    
    :param arquivo_excel: Caminho do arquivo Excel
    :return: DataFrame com dados de contrato
    """
    try:
        # Ler arquivo Excel
        df = pd.read_excel(arquivo_excel)
        
        # Selecionar colunas necessárias
        colunas = [
            'CCB',
            'Data de Digitação',
            'Tabela',
            'Valor Bruto',
            'Valor Líquido',
            'Usuário',
            'E-mail',
            'Status',
            'Data do Desembolso',
            'CPF/CNPJ',
            'Nome',
            'Parcelas'
        ]
        
        # Filtrar colunas
        df = df[colunas]
        
        return df
    
    except FileNotFoundError:
        print("Arquivo não encontrado.")
        return None
    
    except Exception as e:
        print(f"Erro: {e}")
        return None

def main():
    # Caminho do arquivo Excel
    arquivo_excel = "contratos.xlsx"
    
    # Ler dados de contrato
    df = ler_contrato(arquivo_excel)
    
    # Imprimir dados
    if df is not None:
        print(df)

if __name__ == "__main__":
    main()