import yfinance as yf
import pandas as pd
import requests
import schedule
import time
from datetime import datetime

# Import mesin terbaru dari Google
from google import genai 

# ==========================================
# 1. KONFIGURASI KREDENSIAL
# ==========================================
TOKEN_TELEGRAM = "8920022906:AAFVrbJMK31KV7a3dorTbMMia6ZUr1JJY20" 
CHAT_ID = "5802563077"
API_KEY_GEMINI = "" 

# Konfigurasi Otak Gemini (Sintaks Terbaru 2024/2025)
client = genai.Client(api_key=API_KEY_GEMINI)

def kirim_telegram(pesan):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": pesan}
    requests.post(url, json=payload)

def analisis_sentimen_berita(ticker_symbol):
    """Agen Gemini bertugas membaca berita dan menyimpulkan sentimen"""
    print("🧠 Gemini sedang membaca berita global terbaru...")
    try:
        # Menarik berita keuangan terbaru
        ticker = yf.Ticker(ticker_symbol)
        berita = ticker.news
        
        if not berita:
            return "NETRAL ⚪ (Tidak ada berita tersedia)"

        kumpulan_judul = ""
        for b in berita[:5]:
            # PENGAMANAN BARU: Mencari judul di berbagai struktur data Yahoo Finance
            judul = b.get('title') or (b.get('content') and b['content'].get('title')) or ""
            if judul:
                kumpulan_judul += f"- {judul}\n"
        
        if not kumpulan_judul.strip():
            return "NETRAL ⚪ (Gagal mengekstrak teks berita)"
            
        # Prompt ketat untuk Gemini
        prompt = f"""Kamu adalah analis Hedge Fund senior. Baca judul berita Bitcoin terbaru ini:
        {kumpulan_judul}
        
        Tugas: Apakah sentimen pasar secara keseluruhan POSITIF, NEGATIF, atau NETRAL? 
        Jawab HANYA dengan 1 kata tersebut. Tidak boleh ada tambahan kata lain."""
        
        # EKSEKUSI MENGGUNAKAN MODEL TERBARU (DIUBAH KE GEMINI-2.5-FLASH)
        respon = client.models.generate_content(
            model='gemini-2.5-flash',  # <-- Ubah bagian ini
            contents=prompt
        )
        
        sentimen = respon.text.strip().upper()
        
        if "POSITIF" in sentimen: return "POSITIF 🟢"
        elif "NEGATIF" in sentimen: return "NEGATIF 🔴"
        else: return "NETRAL ⚪"
        
    except Exception as e:
        print(f"⚠️ Gagal menghubungi Gemini: {e}")
        return "NETRAL ⚪"

# ==========================================
# 2. LOGIKA TRADING AI (HOLY TRINITY + SENTIMEN)
# ==========================================
def cek_pasar():
    waktu_sekarang = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{waktu_sekarang}] 🤖 Menarik data real-time BTC-USD...")
    
    # PERUBAHAN: period diperpendek agar lebih ringan di server cloud
    df = yf.download('BTC-USD', period='1mo', interval='1d', progress=False)
    
    # PENGAMANAN BARU: Jika download gagal, jangan lanjut ke perhitungan
    if df.empty:
        print("⚠️ Gagal menarik data dari Yahoo Finance. Mencoba lagi nanti...")
        return 

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # (Sisa perhitungan indikator di bawah tetap sama...)
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    macd = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD_Hist'] = macd - macd.ewm(span=9, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))

    # Syarat Matematika
    df['Sinyal'] = 0
    kondisi_beli = (df['EMA_20'] > df['EMA_50']) & (df['MACD_Hist'] > 0) & (df['RSI'] < 70)
    kondisi_jual = (df['EMA_20'] <= df['EMA_50']) | (df['RSI'] > 75)

    df.loc[kondisi_beli, 'Sinyal'] = 1
    df.loc[kondisi_jual, 'Sinyal'] = -1
    status_terakhir = df['Sinyal'].diff().iloc[-1]
    harga_terakhir = float(df['Close'].iloc[-1])

    # --- PENGAMBILAN KEPUTUSAN GANDA (MATH + SENTIMENT) ---
    tp_harga = harga_terakhir * 1.06
    cl_harga = harga_terakhir * 0.98

    if status_terakhir == 2: # MATEMATIKA MENYURUH BELI
        sentimen_gemini = analisis_sentimen_berita('BTC-USD')
        
        if "NEGATIF" in sentimen_gemini:
            pesan = (f"🛡️ [PEMBELIAN DIBATALKAN] BTC-USD\n\n"
                     f"Matematika menyuruh Beli, TAPI Gemini Pro mendeteksi berita NEGATIF 🔴.\n"
                     f"Agen membatalkan eksekusi demi melindungi modal Anda!")
        else:
            pesan = (f"🚀 [SINYAL BELI TERKONFIRMASI] BTC-USD\n\n"
                     f"Harga Beli Virtual: ${harga_terakhir:,.2f}\n"
                     f"Sentimen Berita: {sentimen_gemini}\n"
                     f"🎯 TP 6%: ${tp_harga:,.2f} | 🛡️ CL 2%: ${cl_harga:,.2f}")
             
    elif status_terakhir == -2: # MATEMATIKA MENYURUH JUAL
        pesan = (f"⚠️ [SINYAL JUAL DARURAT] BTC-USD\n\n"
                 f"Harga Jual Virtual: ${harga_terakhir:,.2f}\n"
                 f"Aksi: Posisi ditutup! Kembali ke Cash.")
    else:
        sentimen_gemini = analisis_sentimen_berita('BTC-USD')
        pesan = (f"⏳ [LAPORAN REAL-TIME AI-PRO] BTC-USD\n\n"
                 f"Harga Live: ${harga_terakhir:,.2f}\n"
                 f"Status Sinyal: HOLD 💤\n"
                 f"Analisis Sentimen Berita: {sentimen_gemini}\n"
                 f"Sistem Simulasi Rp 2 Juta Aman.")

    kirim_telegram(pesan)
    print(f"=> Laporan berhasil dikirim ke Telegram! (Sentimen: {sentimen_gemini})")

print("⚙️ MODE OTOMATIS GANDA AKTIF (Holy Trinity + Gemini Pro Sentimen).")
schedule.every(1).minutes.do(cek_pasar)

cek_pasar()

while True:
    schedule.run_pending()
    time.sleep(1)