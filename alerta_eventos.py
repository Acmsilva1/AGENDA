import os
from datetime import datetime, timedelta

# Importa as bibliotecas necessárias
import gspread
import pandas as pd
from telegram import Bot
import asyncio

# --- CONFIGURAÇÃO E AUTENTICAÇÃO DO SISTEMA ---

# 🛑 VARIÁVEIS DE AMBIENTE (SECRETS DO GITHUB)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ID da Planilha no seu Google Drive (Use o mesmo do app.py)
PLANILHA_ID = "1S54b0QtWYaCAgrDNpdQM7ZG5f_KbYXpDztK5TSOn2vU"
ABA_NOME = "AGENDA"

# --- FUNÇÕES CORE ---

def conectar_sheets():
    """Conecta ao Google Sheets usando Secrets armazenadas no ambiente."""
    try:
        # Acesso ao JSON de credenciais
        GSPREAD_CREDENTIALS_JSON = os.getenv("GSPREAD_CREDENTIALS_JSON")
        
        if not GSPREAD_CREDENTIALS_JSON:
            print("🚨 ERRO: Credenciais do Google Sheets não encontradas. Verifique a Secret 'GSPREAD_CREDENTIALS_JSON'.")
            return None

        import json
        creds_dict = json.loads(GSPREAD_CREDENTIALS_JSON)
        gc = gspread.service_account_from_dict(creds_dict)
        
        spreadsheet = gc.open_by_key(PLANILHA_ID)
        sheet = spreadsheet.worksheet(ABA_NOME)
        print("✅ Conexão com Google Sheets estabelecida.")
        return sheet
    
    except Exception as e:
        print(f"🚨 Erro fatal ao conectar ao Sheets: {e}")
        return None

def carregar_eventos(sheet):
    """Lê todos os registros e retorna como DataFrame."""
    if sheet is None:
         return pd.DataFrame()
    try:
        dados = sheet.get_all_records()
        df = pd.DataFrame(dados)
        
        # 📌 Ajuste de colunas para minúsculas se necessário, mas aqui apenas 
        # garantimos que 'data_evento' seja datetime.
        df['data_evento'] = pd.to_datetime(df['data_evento'], errors='coerce')
        return df
    except Exception as e:
        print(f"Erro ao carregar eventos: {e}")
        return pd.DataFrame()

async def enviar_alerta(mensagem):
    """Envia a mensagem para o Telegram de forma assíncrona."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("🚨 ERRO: Token ou Chat ID do Telegram não configurados.")
        return

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID, 
            text=mensagem, 
            parse_mode='Markdown'
        )
        print("🎉 Alerta enviado com sucesso para o Telegram!")
    except Exception as e:
        print(f"🚨 Erro ao enviar mensagem para o Telegram: {e}")

# --- LÓGICA DO AGENTE DE ALERTA (O CORAÇÃO DO SISTEMA) ---

def main_alerta():
    """Função principal que executa a lógica de alerta e notificação."""
    print("Iniciando Agente de Alerta...")

    sheet = conectar_sheets()
    if sheet is None:
        return

    df_eventos = carregar_eventos(sheet)
    if df_eventos.empty:
        print("Nenhum evento encontrado.")
        return

    # 1. DEFINIÇÃO DE FILTROS DE GOVERNANÇA (BOLO QUEIMANDO)
    
    # Eventos de ALTA Prioridade Pendentes
    # Usando 'prioridade' e 'status' (minúsculas conforme os cabeçalhos)
    df_alta_pendente = df_eventos[
        (df_eventos['prioridade'] == 'Alta') & 
        (df_eventos['status'] == 'Pendente')
    ]
    
    # Eventos AGENDADOS PARA AMANHÃ
    amanha = datetime.now().date() + timedelta(days=1)
    df_amanha = df_eventos[
        (df_eventos['data_evento'].dt.date == amanha) &
        (df_eventos['status'] == 'Pendente') # Apenas pendentes
    ]
    
    
    # --- CONSTRUÇÃO DA MENSAGEM ---
    
    mensagens = []
    
    # ALERTA 1: ALTA PRIORIDADE PENDENTE
    if not df_alta_pendente.empty:
        msg_alta = "🚨 *PRIORIDADE ALTA PENDENTE* 🚨\n"
        for index, row in df_alta_pendente.head(3).iterrows():
            # Usando 'titulo' e 'data_evento'
            msg_alta += f"  - {row['titulo']} (Data: {row['data_evento'].strftime('%d/%m/%Y')})\n"
        
        if len(df_alta_pendente) > 3:
             msg_alta += f"  ... e mais {len(df_alta_pendente) - 3} itens de Alta Prioridade.\n"
             
        mensagens.append(msg_alta)


    # ALERTA 2: EVENTOS DE AMANHÃ
    if not df_amanha.empty:
        msg_amanha = "🗓️ *AGENDA DE AMANHÃ* 🗓️\n"
        for index, row in df_amanha.iterrows():
            # Usando 'titulo', 'hora_evento' e 'local'
            msg_amanha += f"  - {row['titulo']} ({row['hora_evento']}) - Local: {row['local']}\n"
        mensagens.append(msg_amanha)

    # ALERTA FINAL: SE HOUVE MENSAGEM, ENVIA
    if mensagens:
        mensagem_final = "🤖 *Relatório de Governança da Agenda*\n\n" + "\n---\n".join(mensagens)
        
        # Executa a função assíncrona de envio
        asyncio.run(enviar_alerta(mensagem_final))
    else:
        print("Nenhum alerta de alta prioridade ou evento para amanhã. Tudo sob controle.")


if __name__ == "__main__":
    main_alerta()
