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
# Mantenho o ID de exemplo, mas use o seu ID real
PLANILHA_ID = "1S54b0QtWYaCAgrDNpdQM7ZG5f_KbYXpDztK5TSOn2vU"
ABA_NOME = "AGENDA"

# --- FUNÇÕES CORE (Sem Alterações) ---

def conectar_sheets():
    """Conecta ao Google Sheets usando Secrets armazenadas no ambiente."""
    try:
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
            parse_mode='Markdown' # Usa Markdown para negrito, etc.
        )
        print("🎉 Alerta enviado com sucesso para o Telegram!")
    except Exception as e:
        print(f"🚨 Erro ao enviar mensagem para o Telegram: {e}")

# --- LÓGICA DO AGENTE DE ALERTA ---

def main_alerta():
    """Função principal que executa a lógica de alerta e notificação."""
    print("Iniciando Agente de Alerta...")
    
    sheet = conectar_sheets()
    if sheet is None:
        return

    df_eventos = carregar_eventos(sheet)
    
    # 📌 NOVO ALERTA 1: SEM REGISTRO DE EVENTOS (Planilha vazia)
    if df_eventos.empty:
        print("Nenhum evento encontrado na planilha.")
        # Frase solicitada: "OLÁ! NÃO HÁ EVENTOS REGISTRADOS!"
        mensagem_vazia = "OLÁ! NÃO HÁ EVENTOS REGISTRADOS!"
        asyncio.run(enviar_alerta(mensagem_vazia))
        return

    # 1. DEFINIÇÃO DE FILTROS DE GOVERNANÇA
    
    df_alta_pendente = df_eventos[
        (df_eventos['prioridade'] == 'Alta') & 
        (df_eventos['status'] == 'Pendente')
    ]
    
    amanha = datetime.now().date() + timedelta(days=1)
    df_amanha = df_eventos[
        (df_eventos['data_evento'].dt.date == amanha) &
        (df_eventos['status'] == 'Pendente')
    ]
    
    # --- CONSTRUÇÃO DA MENSAGEM ---
    
    mensagens = []
    
    # ALERTA 1: ALTA PRIORIDADE PENDENTE (Mensagem de Alerta)
    if not df_alta_pendente.empty:
        msg_alta = "🚨 *PRIORIDADE ALTA PENDENTE* 🚨\n"
        for index, row in df_alta_pendente.head(3).iterrows():
            msg_alta += f"  - {row['titulo']} (Data: {row['data_evento'].strftime('%d/%m/%Y')})\n"
        
        if len(df_alta_pendente) > 3:
             msg_alta += f"  ... e mais {len(df_alta_pendente) - 3} itens de Alta Prioridade.\n"
             
        mensagens.append(msg_alta)


    # ALERTA 2: EVENTOS DE AMANHÃ (Mensagem de Alerta)
    if not df_amanha.empty:
        msg_amanha = "🗓️ *AGENDA DE AMANHÃ* 🗓️\n"
        for index, row in df_amanha.iterrows():
            msg_amanha += f"  - {row['titulo']} ({row['hora_evento']}) - Local: {row['local']}\n"
        mensagens.append(msg_amanha)

    # ALERTA FINAL: SE HOUVE MENSAGEM (URGENTE/AGENDA) OU SE NÃO HOUVE (NADA CONSTA)
    if mensagens:
        # Se encontrou alertas, envia a lista completa
        mensagem_final = "🤖 *Relatório de Governança da Agenda*\n\n" + "\n---\n".join(mensagens)
        asyncio.run(enviar_alerta(mensagem_final))
    else:
        # 📌 NOVO ALERTA 2: SEM EVENTOS URGENTES (Planilha com dados, mas filtros vazios)
        print("Nenhum alerta de alta prioridade ou evento para amanhã. Tudo sob controle.")
        # Frase solicitada: "OLÁ! NÃO HÁ EVENTOS URGENTES!"
        mensagem_nada_consta = "OLÁ! NÃO HÁ EVENTOS URGENTES!"
        asyncio.run(enviar_alerta(mensagem_nada_consta))


if __name__ == "__main__":
    main_alerta()
