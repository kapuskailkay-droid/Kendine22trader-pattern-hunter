import io
import time
import ccxt
import matplotlib
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
import requests

matplotlib.use('Agg')

# --- SABİT BOT VE TELEGRAM AYARLARI (GÖMÜLÜ) ---
BOT_TOKEN = "7820599329:AAEAa13edhS9PLoG1t8R34PLO9xpKlaT_Lc"
CHAT_ID = "-1004434260285"
TOPIC_ID = 3802
COIN_ADEDI = 50

hafiza = set()

def telegram_gonder(foto_buf, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": CHAT_ID,
        "message_thread_id": TOPIC_ID,
        "caption": caption,
        "parse_mode": "HTML"
    }
    files = {"photo": ("chart.png", foto_buf, "image/png")}
    try:
        requests.post(url, data=data, files=files, timeout=15)
    except Exception as e:
        print(f"Telegram Hatası: {e}")

def grafik_ciz(df_mum, sembol, tf_etiket, formasyon_adi, kirilan_seviye, tp1, tp2, sl):
    df_grafik = df_mum.copy()
    df_grafik['Zaman'] = pd.to_datetime(df_grafik['Zaman'], unit='ms')
    df_grafik.set_index('Zaman', inplace=True)
    df_grafik.rename(columns={'Acilis':'Open','Yuksek':'High','Dusuk':'Low','Kapanis':'Close','Hacim':'Volume'}, inplace=True)
    df_plot = df_grafik.tail(42)
    
    mc = mpf.make_marketcolors(up='#00FF88', down='#FF3366', inherit=True, volume='in')
    s = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc, gridcolor='#20242C', facecolor='#0E1117', edgecolor='#30363D', figcolor='#0E1117')
    hlines_dict = dict(hlines=[kirilan_seviye, tp1, tp2, sl], colors=['#00D4FF', '#00FF88', '#38EF7D', '#FF3366'], linestyle=['-', '--', '-.', ':'], linewidths=[2.2, 1.6, 1.4, 1.6])
    
    buf = io.BytesIO()
    fig, axes = mpf.plot(df_plot, type='candle', volume=True, style=s, hlines=hlines_dict, returnfig=True, figsize=(10, 6), savefig=dict(dpi=140, bbox_inches='tight'))
    ax_main = axes[0]
    ax_main.set_title(f"KENDİNE22TRADER | {sembol} ({tf_etiket}) - {formasyon_adi}", fontsize=12, fontweight='bold', color='#F4E07B', pad=12)
    
    son_x = len(df_plot) - 1
    ax_main.text(son_x, kirilan_seviye, f"  ⚡ Retest: {kirilan_seviye}$", color='#00D4FF', fontsize=8.5, fontweight='bold', bbox=dict(boxstyle='round,pad=0.25', facecolor='#0D223A', edgecolor='#00D4FF', alpha=0.9), verticalalignment='center')
    ax_main.text(son_x, tp1, f"  🎯 TP1: {tp1}$", color='#00FF88', fontsize=8, fontweight='bold', bbox=dict(boxstyle='round,pad=0.2', facecolor='#092E1B', edgecolor='#00FF88', alpha=0.9), verticalalignment='center')
    ax_main.text(son_x, sl, f"  🛑 STOP: {sl}$", color='#FF3366', fontsize=8, fontweight='bold', bbox=dict(boxstyle='round,pad=0.2', facecolor='#350F18', edgecolor='#FF3366', alpha=0.9), verticalalignment='center')
    
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='#0E1117')
    buf.seek(0)
    plt.close(fig)
    return buf

def retest_bul(df, hacim_orani):
    highs, lows, closes, opens = df['Yuksek'].values, df['Dusuk'].values, df['Kapanis'].values, df['Acilis'].values
    c_son, o_son = closes[-1], opens[-1]
    
    dip_idx, tepe_idx = [], []
    for i in range(3, len(df)-4):
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            dip_idx.append(i)
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            tepe_idx.append(i)
            
    # W Dip
    if len(dip_idx) >= 2:
        d1, d2 = dip_idx[-2], dip_idx[-1]
        if abs(lows[d1]-lows[d2])/lows[d1] <= 0.022 and (d2-d1)>=5 and (len(df)-1-d2)<=12:
            boyun = round(float(max([highs[k] for k in range(d1, d2+1)])), 6)
            if any(closes[-5:-1] > boyun * 1.002) and any(lows[-3:] <= boyun * 1.006) and (c_son > boyun) and (c_son > o_son) and hacim_orani >= 1.1:
                return "📐 W FORMASYONU (RETEST ONAYLANDI 🚀)", "🟢 LONG", boyun

    # M Tepe
    if len(tepe_idx) >= 2:
        t1, t2 = tepe_idx[-2], tepe_idx[-1]
        if abs(highs[t1]-highs[t2])/highs[t1] <= 0.022 and (t2-t1)>=5 and (len(df)-1-t2)<=12:
            taban = round(float(min([lows[k] for k in range(t1, t2+1)])), 6)
            if any(closes[-5:-1] < taban * 0.998) and any(highs[-3:] >= taban * 0.994) and (c_son < taban) and (c_son < o_son) and hacim_orani >= 1.1:
                return "📐 M FORMASYONU (RETEST ONAYLANDI 🩸)", "🔴 SHORT", taban

    # TOBO
    if len(dip_idx) >= 3:
        sol, bas, sag = dip_idx[-3], dip_idx[-2], dip_idx[-1]
        if lows[bas] < lows[sol] and lows[bas] < lows[sag] and abs(lows[sol]-lows[sag])/lows[sol] <= 0.035:
            boyun = round(float(max(max(highs[sol:bas]), max(highs[bas:sag+1]))), 6)
            if any(closes[-5:-1] > boyun * 1.002) and any(lows[-3:] <= boyun * 1.006) and (c_son > boyun) and (c_son > o_son) and hacim_orani >= 1.1:
                return "👤 TOBO (RETEST ONAYLANDI 🚀)", "🟢 LONG", boyun

    # OBO
    if len(tepe_idx) >= 3:
        sol, bas, sag = tepe_idx[-3], tepe_idx[-2], tepe_idx[-1]
        if highs[bas] > highs[sol] and highs[bas] > highs[sag] and abs(highs[sol]-highs[sag])/highs[sol] <= 0.035:
            taban = round(float(min(min(lows[sol:bas]), min(lows[bas:sag+1]))), 6)
            if any(closes[-5:-1] < taban * 0.998) and any(highs[-3:] >= taban * 0.994) and (c_son < taban) and (c_son < o_son) and hacim_orani >= 1.1:
                return "👤 OBO (RETEST ONAYLANDI 🩸)", "🔴 SHORT", taban

    # Bull Flag
    if len(df) >= 20:
        direk = ((closes[-6] - closes[-18]) / closes[-18]) * 100
        flama_tavan = round(float(max(highs[-6:-2])), 6)
        if direk >= 4.0 and any(closes[-4:-1] > flama_tavan) and any(lows[-2:] <= flama_tavan * 1.004) and (c_son > flama_tavan) and (c_son > o_son):
            return "🚩 BOĞA BAYRAĞI (RETEST ONAYLANDI 🚀)", "🟢 LONG", flama_tavan

    # Bear Flag
    if len(df) >= 20:
        direk = ((closes[-6] - closes[-18]) / closes[-18]) * 100
        flama_taban = round(float(min(lows[-6:-2])), 6)
        if direk <= -4.0 and any(closes[-4:-1] < flama_taban) and any(highs[-2:] >= flama_taban * 0.996) and (c_son < flama_taban) and (c_son < o_son):
            return "🚩 AYI BAYRAĞI (RETEST ONAYLANDI 🩸)", "🔴 SHORT", flama_taban

    # Yükselen Üçgen
    if len(tepe_idx) >= 2 and len(dip_idx) >= 2:
        t1, t2 = highs[tepe_idx[-2]], highs[tepe_idx[-1]]
        d1, d2 = lows[dip_idx[-2]], lows[dip_idx[-1]]
        if abs(t1-t2)/t1 <= 0.015 and d2 > d1:
            direnc = round(float(max(t1, t2)), 6)
            if any(closes[-4:-1] > direnc * 1.001) and any(lows[-2:] <= direnc * 1.004) and (c_son > direnc) and (c_son > o_son):
                return "📐 YÜKSELEN ÜÇGEN (RETEST ONAYLANDI 🚀)", "🟢 LONG", direnc

    # Alçalan Üçgen
    if len(tepe_idx) >= 2 and len(dip_idx) >= 2:
        t1, t2 = highs[tepe_idx[-2]], highs[tepe_idx[-1]]
        d1, d2 = lows[dip_idx[-2]], lows[dip_idx[-1]]
        if abs(d1-d2)/d1 <= 0.015 and t2 < t1:
            destek = round(float(min(d1, d2)), 6)
            if any(closes[-4:-1] < destek * 0.999) and any(highs[-2:] >= destek * 0.996) and (c_son < destek) and (c_son < o_son):
                return "📐 ALÇALAN ÜÇGEN (RETEST ONAYLANDI 🩸)", "🔴 SHORT", destek

    return None, None, None

def main():
    print("🚀 KENDİNE22TRADER 7/24 Kesintisiz Arka Plan Motoru Devrede...")
    mexc = ccxt.mexc({'options': {'defaultType': 'swap'}, 'enableRateLimit': True})
    zaman_dilimleri = [("15m", "15 Dakika"), ("30m", "30 Dakika"), ("1h", "1 Saat"), ("4h", "4 Saat"), ("1d", "1 Gün"), ("1w", "1 Hafta")]
    
    while True:
        try:
            tickers = mexc.fetch_tickers()
            usdt_pariteler = [s for s in tickers.keys() if '/USDT' in s]
            usdt_pariteler.sort(key=lambda x: tickers[x].get('quoteVolume', 0) or 0, reverse=True)
            hedef_listesi = usdt_pariteler[:COIN_ADEDI]
            
            for sembol in hedef_listesi:
                temiz_parite = sembol.split(':')[0]
                mexc_link = f"https://www.mexc.com/tr-TR/futures/{temiz_parite.replace('/', '_')}"
                
                for tf_kod, tf_ad in zaman_dilimleri:
                    try:
                        mumlar = mexc.fetch_ohlcv(sembol, timeframe=tf_kod, limit=50)
                        if len(mumlar) >= 30:
                            df = pd.DataFrame(mumlar, columns=['Zaman', 'Acilis', 'Yuksek', 'Dusuk', 'Kapanis', 'Hacim'])
                            gecmis_hacim = df['Hacim'].iloc[:-1].mean()
                            son_hacim = df['Hacim'].iloc[-1]
                            hacim_orani = (son_hacim / gecmis_hacim) if gecmis_hacim > 0 else 0
                            son_kapanis = df['Kapanis'].iloc[-1]
                            
                            formasyon_adi, yon, kirilan_seviye = retest_bul(df, hacim_orani)
                            if formasyon_adi:
                                sinyal_id = f"{temiz_parite}_{formasyon_adi}_{tf_kod}"
                                if sinyal_id not in hafiza:
                                    atr = (df['Yuksek'] - df['Dusuk']).rolling(14).mean().iloc[-1]
                                    sl = round(son_kapanis - (atr * 1.5), 6) if "LONG" in yon else round(son_kapanis + (atr * 1.5), 6)
                                    tp1 = round(son_kapanis + (atr * 1.5), 6) if "LONG" in yon else round(son_kapanis - (atr * 1.5), 6)
                                    tp2 = round(son_kapanis + (atr * 3.0), 6) if "LONG" in yon else round(son_kapanis - (atr * 3.0), 6)
                                    
                                    tg_caption = (
                                        f"🛡️ <b>KENDİNE22TRADER ÇOKLU FORMASYON SİNYALİ</b>\n\n"
                                        f"📌 <b>Parite:</b> {temiz_parite}\n"
                                        f"⏱ <b>Zaman Dilimi:</b> <b>{tf_ad} ({tf_kod})</b>\n"
                                        f"🎯 <b>Yön:</b> {yon}\n"
                                        f"⚡ <b>Formasyon:</b> {formasyon_adi}\n"
                                        f"📏 <b>Kırılan/Retest Seviyesi:</b> {kirilan_seviye} $\n"
                                        f"💰 <b>Onaylı Giriş:</b> {son_kapanis} $\n"
                                        f"📊 <b>Hacim Katı:</b> {round(hacim_orani, 1)}x\n\n"
                                        f"🎯 <b>HEDEF 1 (TP1):</b> {tp1} $\n"
                                        f"🎯 <b>HEDEF 2 (TP2):</b> {tp2} $\n"
                                        f"🛑 <b>STOP-LOSS:</b> {sl} $\n\n"
                                        f"🔗 <a href='{mexc_link}'>MEXC Vadeli Grafiği Aç ↗</a>"
                                    )
                                    foto = grafik_ciz(df, temiz_parite, f"{tf_ad} ({tf_kod})", formasyon_adi, kirilan_seviye, tp1, tp2, sl)
                                    telegram_gonder(foto, tg_caption)
                                    hafiza.add(sinyal_id)
                                    print(f"✅ Sinyal Gönderildi: {sinyal_id}")
                    except Exception:
                        pass
        except Exception as e:
            print(f"Tarama Hatası: {e}")
            
        time.sleep(25)

if __name__ == "__main__":
    main()
