import io
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import matplotlib
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
import requests

matplotlib.use('Agg')

# --- TELEGRAM & HEDEF AYARLARI ---
BOT_TOKEN = "7820599329:AAEAa13edhS9PLoG1t8R34PLO9xpKlaT_Lc"
CHAT_ID = "-1004434260285"
TOPIC_ID = 3802
COIN_ADEDI = 200

hafiza = set()


# Render Port Dinleyicisi (7/24 Kesintisiz Çalışma)
class HealthCheckHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.send_header('Content-type', 'text/plain; charset=utf-8')
    self.end_headers()
    self.wfile.write(b'KENDINE22TRADER Formasyon Motoru Aktif!')

  def log_message(self, format, *args):
    return


def start_http_server():
  port = int(os.environ.get('PORT', 10000))
  server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
  server.serve_forever()


def telegram_foto_gonder(foto_buf, caption):
  url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto'
  data = {
      'chat_id': CHAT_ID,
      'message_thread_id': TOPIC_ID,
      'caption': caption,
      'parse_mode': 'HTML',
  }
  files = {'photo': ('chart.png', foto_buf, 'image/png')}
  try:
    requests.post(url, data=data, files=files, timeout=15)
  except Exception as e:
    print(f'Telegram Hata: {e}')


def grafik_ciz(df, sembol, tf_etiket, formasyon_adi, tp1, tp2, sl, kirilim_fiyat):
  df_grafik = df.copy()
  df_grafik['Zaman'] = pd.to_datetime(df_grafik['Zaman'], unit='ms')
  df_grafik.set_index('Zaman', inplace=True)
  df_grafik.rename(
      columns={
          'Acilis': 'Open',
          'Yuksek': 'High',
          'Dusuk': 'Low',
          'Kapanis': 'Close',
          'Hacim': 'Volume',
      },
      inplace=True,
  )
  df_plot = df_grafik.tail(40)

  mc = mpf.make_marketcolors(
      up='#10B981', down='#EF4444', inherit=True, volume='in'
  )
  s = mpf.make_mpf_style(
      base_mpf_style='nightclouds',
      marketcolors=mc,
      gridcolor='#20242C',
      facecolor='#0E1117',
      edgecolor='#30363D',
      figcolor='#0E1117',
  )
  hlines_dict = dict(
      hlines=[tp1, tp2, sl, kirilim_fiyat],
      colors=['#10B981', '#34D399', '#EF4444', '#F59E0B'],
      linestyle=['--', '-.', ':', '-'],
      linewidths=[1.6, 1.4, 1.6, 1.8],
  )

  buf = io.BytesIO()
  fig, axes = mpf.plot(
      df_plot,
      type='candle',
      volume=True,
      style=s,
      hlines=hlines_dict,
      returnfig=True,
      figsize=(9.5, 5.5),
      savefig=dict(dpi=130, bbox_inches='tight'),
  )
  ax_main = axes[0]
  ax_main.set_title(
      f'KENDİNE22TRADER | {sembol} ({tf_etiket}) {formasyon_adi.upper()}',
      fontsize=11,
      fontweight='bold',
      color='#F59E0B',
      pad=10,
  )

  fig.savefig(buf, format='png', bbox_inches='tight', facecolor='#0E1117')
  buf.seek(0)
  plt.close('all')
  return buf


# --- FORMASYON VE KIRILIM MOTORU ---
def formasyon_tara(df):
  if len(df) < 30:
    return None, None, 0

  closes = df['Kapanis'].values
  highs = df['Yuksek'].values
  lows = df['Dusuk'].values
  vols = df['Hacim'].values

  son_kapanis = closes[-1]
  direnc_bolgesi = np.max(highs[-25:-2])
  destek_bolgesi = np.min(lows[-25:-2])

  # Hacim artış doğrulaması (Fake kırılım önleme)
  ort_vol = np.mean(vols[-20:-1])
  son_vol = vols[-1]
  hacim_onay = son_vol > (ort_vol * 1.35)

  # 1. Direnç Kırılımı / Yükselen Üçgen Kırılımı (LONG)
  if (
      (son_kapanis > direnc_bolgesi)
      and (closes[-2] <= direnc_bolgesi)
      and hacim_onay
  ):
    return 'Direnç & Üçgen Kırılımı (Breakout)', 'LONG', direnc_bolgesi

  # 2. Destek Kırılımı / Çift Tepe Kırılımı (SHORT)
  elif (
      (son_kapanis < destek_bolgesi)
      and (closes[-2] >= destek_bolgesi)
      and hacim_onay
  ):
    return 'Destek Kırılımı (Breakdown)', 'SHORT', destek_bolgesi

  return None, None, 0


def main():
  threading.Thread(target=start_http_server, daemon=True).start()
  print('📐 KENDİNE22TRADER Formasyon Motoru (Topic 3802) Başlatıldı...')

  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
          ' like Gecko) Chrome/120.0.0.0 Safari/537.36'
      )
  }
  zaman_dilimleri = [
      ('Min15', '15m', '15 Dakika'),
      ('Min30', '30m', '30 Dakika'),
      ('Min60', '1h', '1 Saat'),
      ('Hour4', '4h', '4 Saat'),
  ]

  while True:
    try:
      url_tickers = 'https://contract.mexc.com/api/v1/contract/ticker'
      res = requests.get(url_tickers, headers=headers, timeout=8).json()

      if res.get('success', False):
        tickers = [
            d
            for d in res.get('data', [])
            if d.get('symbol', '').endswith('_USDT')
        ]
        tickers.sort(
            key=lambda x: float(x.get('amount24', 0) or 0), reverse=True
        )
        hedef_pariteler = tickers[:COIN_ADEDI]

        for coin in hedef_pariteler:
          sembol_raw = coin['symbol']
          temiz_parite = sembol_raw.replace('_', '/')
          mexc_link = f'https://www.mexc.com/tr-TR/futures/{sembol_raw}'

          for api_tf, tf_kod, tf_ad in zaman_dilimleri:
            try:
              url_kline = f'https://contract.mexc.com/api/v1/contract/kline/{sembol_raw}?interval={api_tf}'
              kline_res = requests.get(
                  url_kline, headers=headers, timeout=3
              ).json()

              if kline_res.get('success', False) and kline_res.get('data'):
                k_data = kline_res['data']
                times = k_data.get('time', [])
                opens = k_data.get('open', [])
                closes = k_data.get('close', [])
                highs = k_data.get('high', [])
                lows = k_data.get('low', [])
                vols = k_data.get('vol', [])

                if len(closes) >= 30:
                  df = pd.DataFrame({
                      'Zaman': [t * 1000 for t in times[-45:]],
                      'Acilis': [float(x) for x in opens[-45:]],
                      'Yuksek': [float(x) for x in highs[-45:]],
                      'Dusuk': [float(x) for x in lows[-45:]],
                      'Kapanis': [float(x) for x in closes[-45:]],
                      'Hacim': [float(x) for x in vols[-45:]],
                  })

                  formasyon, yon, kirilim_fiyat = formasyon_tara(df)

                  if formasyon:
                    son_kapanis = df['Kapanis'].iloc[-1]
                    son_zaman = df['Zaman'].iloc[-1]
                    sinyal_id = f'{sembol_raw}_{formasyon}_{tf_kod}_{son_zaman}'

                    if sinyal_id not in hafiza:
                      atr = (
                          (df['Yuksek'] - df['Dusuk'])
                          .rolling(14)
                          .mean()
                          .iloc[-1]
                      )
                      if np.isnan(atr):
                        atr = son_kapanis * 0.02

                      if yon == 'LONG':
                        sl = round(kirilim_fiyat - (atr * 1.2), 6)
                        tp1 = round(son_kapanis + (atr * 1.8), 6)
                        tp2 = round(son_kapanis + (atr * 3.5), 6)
                        yon_str = '🟢 LONG (Yukarı Kırılım)'
                      else:
                        sl = round(kirilim_fiyat + (atr * 1.2), 6)
                        tp1 = round(son_kapanis - (atr * 1.8), 6)
                        tp2 = round(son_kapanis - (atr * 3.5), 6)
                        yon_str = '🔴 SHORT (Aşağı Kırılım)'

                      caption = (
                          f'📐 <b>KT22 TEKNİK FORMASYON RADARI</b>\n\n'
                          f'📌 <b>Parite:</b> {temiz_parite}\n'
                          f'⏱ <b>Zaman Dilimi:</b> {tf_ad} ({tf_kod})\n'
                          f'🔍 <b>Formasyon:</b> {formasyon}\n'
                          f'🎯 <b>Yön:</b> {yon_str}\n'
                          f'💰 <b>Kırılım / Giriş:</b> {son_kapanis} $\n'
                          f'🟡 <b>Kritik Seviye:</b> {kirilim_fiyat} $\n\n'
                          f'🎯 <b>HEDEF 1 (TP1):</b> {tp1} $\n'
                          f'🎯 <b>HEDEF 2 (TP2):</b> {tp2} $\n'
                          f'🛑 <b>STOP-LOSS:</b> {sl} $\n\n'
                          f"🔗 <a href='{mexc_link}'>MEXC Vadeli Grafiği Aç"
                          ' ↗</a>'
                      )

                      foto = grafik_ciz(
                          df,
                          temiz_parite,
                          f'{tf_ad} ({tf_kod})',
                          formasyon,
                          tp1,
                          tp2,
                          sl,
                          kirilim_fiyat,
                      )
                      telegram_foto_gonder(foto, caption)
                      hafiza.add(sinyal_id)
                      print(f'✅ Formasyon Sinyali: {sinyal_id}')
                      time.sleep(1.5)
            except Exception:
              pass
    except Exception as e:
      print(f'Tarama Döngü Hatası: {e}')

    time.sleep(25)


if __name__ == '__main__':
  main()
