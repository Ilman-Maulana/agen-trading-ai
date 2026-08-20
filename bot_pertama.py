import os
import yfinance as yf
import pandas as pd
import requests
import schedule
import time
from datetime import datetime
from google import genai 

# --- TAMBAHAN UNTUK CLOUD (Server Web Palsu) ---
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Agen Trading AI sedang bekerja 24/7 di awan!"

# ==========================================
# 1. KONFIGURASI KREDENSIAL (AMAN DI CLOUD)
# ==========================================
TOKEN_TELEGRAM = os.environ.get("TOKEN_TELEGRAM")
CHAT_ID = os.environ.get("CHAT_ID")
API_KEY_GEMINI = os.environ.get("API_KEY_GEMINI")

if API_KEY_GEMINI:
    client = genai.Client(api_key=API_KEY_GEMINI)
else:
    print("⚠️ PERINGATAN: API_KEY_GEMINI tidak ditemukan!")

def kirim_telegram(pesan):
    if not TOKEN_TELEGRAM or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": pesan})
    except:
        pass

def analisis_sentimen_berita(ticker_symbol):
    if not API_KEY_GEMINI: return "NETRAL ⚪"
    try:
        ticker = yf.Ticker(ticker_symbol)
        berita = ticker.news
        if not berita: return "NETRAL ⚪"

        kumpulan_judul = ""
        for b in berita[:5]:
            judul = b.get('title') or (b.get('content') and b['content'].get('title')) or ""
            if judul: kumpulan_judul += f"- {judul}\n"
        
        prompt = f"Baca judul berita Bitcoin ini:\n{kumpulan_judul}\nApakah sentimen pasar POSITIF, NEGATIF, atau NETRAL? Jawab HANYA dengan 1 kata tersebut."
        respon = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        sentimen = respon.text.strip().upper()
        
        if "POSITIF" in sentimen: return "POSITIF 🟢"
        elif "NEGATIF" in sentimen: return "NEGATIF 🔴"
        else: return "NETRAL ⚪"
    except:
        return "NETRAL ⚪"

# ==========================================
# 2. LOGIKA TRADING AI (HOLY TRINITY + SENTIMEN)
# ==========================================
def cek_pasar():
    waktu_sekarang = datetime.now().strftime("%H:%M:%S")
    print(f"[{waktu_sekarang}] 🤖 Menarik data BTC-USD...")
    
    try:
        df = yf.download('BTC-USD', period='1mo', interval='1d', progress=False)
        if df.empty: return 
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        macd = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD_Hist'] = macd - macd.ewm(span=9, adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))

        df['Sinyal'] = 0
        kondisi_beli = (df['EMA_20'] > df['EMA_50']) & (df['MACD_Hist'] > 0) & (df['RSI'] < 70)
        kondisi_jual = (df['EMA_20'] <= df['EMA_50']) | (df['RSI'] > 75)
        df.loc[kondisi_beli, 'Sinyal'] = 1
        df.loc[kondisi_jual, 'Sinyal'] = -1
        
        if len(df) < 2: return

        status_terakhir = df['Sinyal'].diff().iloc[-1]
        harga_terakhir = float(df['Close'].iloc[-1])
        tp_harga = harga_terakhir * 1.06
        cl_harga = harga_terakhir * 0.98

        if status_terakhir == 2:
            sent = analisis_sentimen_berita('BTC-USD')
            if "NEGATIF" in sent:
                pesan = f"🛡️ [PEMBELIAN DIBATALKAN] BTC-USD\n\nGemini mendeteksi berita NEGATIF 🔴. Eksekusi dibatalkan!"
            else:
                pesan = f"🚀 [SINYAL BELI TERKONFIRMASI] BTC-USD\n\nHarga Virtual: ${harga_terakhir:,.2f}\nSentimen: {sent}\n🎯 TP: ${tp_harga:,.2f} | 🛡️ CL: ${cl_harga:,.2f}"
        elif status_terakhir == -2:
            pesan = f"⚠️ [SINYAL JUAL DARURAT] BTC-USD\n\nHarga Jual Virtual: ${harga_terakhir:,.2f}\nPosisi ditutup!"
        else:
            sent = analisis_sentimen_berita('BTC-USD')
            pesan = f"⏳ [LAPORAN REAL-TIME AI-PRO] BTC-USD\n\nHarga Live: ${harga_terakhir:,.2f}\nStatus Sinyal: HOLD 💤\nSentimen: {sent}"

        kirim_telegram(pesan)
    except Exception as e:
        print(f"Error: {e}")

# ==========================================
# 3. MESIN PENGGERAK UTAMA
# ==========================================
def jalankan_bot():
    cek_pasar()
    schedule.every(1).minutes.do(cek_pasar)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    print("⚙️ MODE OTOMATIS AKTIF: Memulai Bot & Web Server...")
    
    # Menjalankan bot di latar belakang
    t = Thread(target=jalankan_bot)
    t.start()
    
    # Menjalankan web server palsu agar Render tidak mematikan mesinnya
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
