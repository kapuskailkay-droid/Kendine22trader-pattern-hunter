import io
import time
import urllib.parse
import ccxt
import matplotlib
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

matplotlib.use('Agg')

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title='MEXC VIP Çizimli Formasyon Radarı', layout='wide'
)

if 'retest_hafiza' not in st.session_state:
  st.session_state.retest_hafiza = set()

# --- YAN PANEL: TELEGRAM AYARLARI ---
st.sidebar.header('📱 Telegram Bildirim Ayarları')
telegram_aktif = st.sidebar.checkbox('🚀 Telegram\'a Gönder', value=True)
bot_token = st.sidebar.text_input(
    'Telegram Bot Token',
    type='password',
    placeholder='BotFather\'dan aldığınız token',
)
chat_id = st.sidebar.text_input('Telegram Chat ID', value='-1004434260285')
topic_id = st.sidebar.text_input(
    'Formasyon Sekmesi Topic ID',
    value='',
    help='Formasyon sekmenizin Topic ID numarası',
)

st.sidebar.markdown('---')
st.sidebar.header('⚙️ Canlı Yayın & Tarama')

oto_yenileme = st.sidebar.checkbox('🔄 Otomatik Canlı Taramayı Aç', value=False)
yenileme_araligi = st.sidebar.selectbox(
    'Tarama Sıklığı',
    options=[30, 60, 120, 300],
    index=1,
    format_func=lambda x: f'{x} Saniyede Bir',
)

if oto_yenileme:
  st_autorefresh(interval=yenileme_araligi * 1000, key='retest_tarayici')
  st.sidebar.success(f'🟢 Canlı mod aktif: Her {yenileme_araligi} sn')

st.sidebar.markdown('---')
st.sidebar.header('🎯 Retest Onaylı Formasyonlar')

zaman_dilimi = st.sidebar.selectbox(
    'Zaman Dilimi (Timeframe)',
    options=['15m', '1h', '4h', '1d'],
    index=0,
)

aktif_formasyonlar = st.sidebar.multiselect(
    'Taranacak Onaylı Formasyonlar',
    options=[
        'W Formasyonu (Retest Onaylı İkili Dip)',
        'M Formasyonu (Retest Onaylı İkili Tepe)',
        'TOBO (Retest Onaylı Ters OBO)',
        'OBO (Retest Onaylı OBO)',
        'Boğa Bayrağı (Retest Onaylı Bull Flag)',
        'Ayı Bayrağı (Retest Onaylı Bear Flag)',
        'Yükselen Üçgen (Retest Onaylı)',
        'Alçalan Üçgen (Retest Onaylı)',
    ],
    default=[
        'W Formasyonu (Retest Onaylı İkili Dip)',
        'M Formasyonu (Retest Onaylı İkili Tepe)',
        'TOBO (Retest Onaylı Ters OBO)',
        'OBO (Retest Onaylı OBO)',
        'Boğa Bayrağı (Retest Onaylı Bull Flag)',
        'Ayı Bayrağı (Retest Onaylı Bear Flag)',
        'Yükselen Üçgen (Retest Onaylı)',
        'Alçalan Üçgen (Retest Onaylı)',
    ],
)

coin_adedi = st.sidebar.select_slider(
    'Taranacak En Yüksek Hacimli Coin Sayısı',
    options=[30, 50, 100, 150, 200],
    value=100,
)

st.title('🛡️ MEXC Vadeli ÇİZİMLİ RETEST FORMASYON RADARI')


# --- FORMASYON ÇİZGİLERİ İLE GRAFİK OLUŞTURMA ---
def grafik_olustur_cizimli(
    df_mum, sembol, zaman_dilimi, formasyon_adi, kirilan_seviye, tp1, sl
):
  df_grafik = df_mum.copy()
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

  mc = mpf.make_marketcolors(up='#00ff88', down='#ff3366', inherit=True)
  s = mpf.make_mpf_style(
      base_mpf_style='nightclouds', marketcolors=mc, gridcolor='#262626'
  )

  hlines_dict = dict(
      hlines=[kirilan_seviye, tp1, sl],
      colors=['#00d4ff', '#00ff88', '#ff3366'],
      linestyle=['--', '-.', ':'],
      linewidths=[1.8, 1.4, 1.4],
  )

  buf = io.BytesIO()
  fig, axes = mpf.plot(
      df_plot,
      type='candle',
      volume=True,
      style=s,
      hlines=hlines_dict,
      returnfig=True,
      savefig=dict(dpi=130, bbox_inches='tight'),
  )

  # Grafik Üzerine Yazılar ve Göstergeler Ekle
  ax_main = axes[0]
  ax_main.set_title(
      f'{sembol} ({zaman_dilimi}) - {formasyon_adi}',
      fontsize=11,
      fontweight='bold',
      color='white',
      pad=10,
  )

  # Çizgi Etiketleri (Sağ Taraf)
  son_x = len(df_plot) - 1
  ax_main.text(
      son_x,
      kirilan_seviye,
      f'  Kırılım/Retest: {kirilan_seviye}$',
      color='#00d4ff',
      fontsize=8,
      verticalalignment='center',
      fontweight='bold',
  )
  ax_main.text(
      son_x,
      tp1,
      f'  TP1: {tp1}$',
      color='#00ff88',
      fontsize=8,
      verticalalignment='center',
  )
  ax_main.text(
      son_x,
      sl,
      f'  SL: {sl}$',
      color='#ff3366',
      fontsize=8,
      verticalalignment='center',
  )

  fig.savefig(buf, format='png', bbox_inches='tight', facecolor='#121212')
  buf.seek(0)
  plt.close(fig)
  return buf


# --- TELEGRAM MESAJ GÖNDERME ---
def telegram_fotograf_gonder(foto_buf, caption_metni):
  if telegram_aktif and bot_token and chat_id:
    url = f'https://api.telegram.org/bot{bot_token.strip()}/sendPhoto'
    params = {}
    if topic_id and str(topic_id).strip() != '':
      try:
        params['message_thread_id'] = int(str(topic_id).strip())
      except ValueError:
        pass
    data = {
        'chat_id': chat_id.strip(),
        'caption': caption_metni,
        'parse_mode': 'HTML',
    }
    files = {'photo': ('chart.png', foto_buf, 'image/png')}
    try:
      requests.post(url, params=params, data=data, files=files, timeout=12)
    except Exception:
      pass


# --- HESAPLAYICILAR ---
def hesapla_atr(df, periyot=14):
  h_l = df['Yuksek'] - df['Dusuk']
  h_pc = (df['Yuksek'] - df['Kapanis'].shift(1)).abs()
  l_pc = (df['Dusuk'] - df['Kapanis'].shift(1)).abs()
  tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
  atr_val = tr.rolling(window=periyot).mean().iloc[-1]
  return atr_val if not np.isnan(atr_val) else df['Kapanis'].iloc[-1] * 0.02


def hesapla_tp_sl(fiyat, atr, yon='LONG'):
  if yon == 'LONG':
    sl = round(fiyat - (atr * 1.5), 6)
    tp1 = round(fiyat + (atr * 1.5), 6)
    tp2 = round(fiyat + (atr * 3.0), 6)
  else:
    sl = round(fiyat + (atr * 1.5), 6)
    tp1 = round(fiyat - (atr * 1.5), 6)
    tp2 = round(fiyat - (atr * 3.0), 6)
  return tp1, tp2, sl


# ==============================================================
# 🎯 RETEST & FORMASYON MOTORU
# ==============================================================
def retest_formasyon_bul(df, hacim_orani):
  highs = df['Yuksek'].values
  lows = df['Dusuk'].values
  closes = df['Kapanis'].values
  opens = df['Acilis'].values

  c_son = closes[-1]
  o_son = opens[-1]

  dip_idx = []
  tepe_idx = []
  for i in range(3, len(df) - 4):
    if (
        lows[i] < lows[i - 1]
        and lows[i] < lows[i - 2]
        and lows[i] < lows[i + 1]
        and lows[i] < lows[i + 2]
    ):
      dip_idx.append(i)
    if (
        highs[i] > highs[i - 1]
        and highs[i] > highs[i - 2]
        and highs[i] > highs[i + 1]
        and highs[i] > highs[i + 2]
    ):
      tepe_idx.append(i)

  # 1. 📐 W FORMASYONU (RETEST ONAYLI İKİLİ DİP)
  if (
      'W Formasyonu (Retest Onaylı İkili Dip)' in aktif_formasyonlar
      and len(dip_idx) >= 2
  ):
    d1, d2 = dip_idx[-2], dip_idx[-1]
    if (
        abs(lows[d1] - lows[d2]) / lows[d1] <= 0.022
        and (d2 - d1) >= 5
        and (len(df) - 1 - d2) <= 12
    ):
      boyun = round(float(max([highs[k] for k in range(d1, d2 + 1)])), 6)
      kirilim_oldu = any(closes[-5:-1] > boyun * 1.002)
      retest_degdi = any(lows[-3:] <= boyun * 1.006) and any(
          lows[-3:] >= boyun * 0.992
      )
      if (
          kirilim_oldu
          and retest_degdi
          and (c_son > boyun)
          and (c_son > o_son)
          and hacim_orani >= 1.1
      ):
        return '📐 W FORMASYONU (RETEST ONAYLI)', '🟢 LONG', boyun

  # 2. 📐 M FORMASYONU (RETEST ONAYLI İKİLİ TEPE)
  if (
      'M Formasyonu (Retest Onaylı İkili Tepe)' in aktif_formasyonlar
      and len(tepe_idx) >= 2
  ):
    t1, t2 = tepe_idx[-2], tepe_idx[-1]
    if (
        abs(highs[t1] - highs[t2]) / highs[t1] <= 0.022
        and (t2 - t1) >= 5
        and (len(df) - 1 - t2) <= 12
    ):
      taban = round(float(min([lows[k] for k in range(t1, t2 + 1)])), 6)
      kirilim_oldu = any(closes[-5:-1] < taban * 0.998)
      retest_degdi = any(highs[-3:] >= taban * 0.994) and any(
          highs[-3:] <= taban * 1.008
      )
      if (
          kirilim_oldu
          and retest_degdi
          and (c_son < taban)
          and (c_son < o_son)
          and hacim_orani >= 1.1
      ):
        return '📐 M FORMASYONU (RETEST ONAYLI)', '🔴 SHORT', taban

  # 3. 👤 TOBO (RETEST ONAYLI TERS OBO)
  if 'TOBO (Retest Onaylı Ters OBO)' in aktif_formasyonlar and len(dip_idx) >= 3:
    sol, bas, sag = dip_idx[-3], dip_idx[-2], dip_idx[-1]
    if (
        lows[bas] < lows[sol]
        and lows[bas] < lows[sag]
        and abs(lows[sol] - lows[sag]) / lows[sol] <= 0.035
    ):
      boyun = round(
          float(max(max(highs[sol:bas]), max(highs[bas : sag + 1]))), 6
      )
      kirilim_oldu = any(closes[-5:-1] > boyun * 1.002)
      retest_degdi = any(lows[-3:] <= boyun * 1.006) and any(
          lows[-3:] >= boyun * 0.992
      )
      if (
          kirilim_oldu
          and retest_degdi
          and (c_son > boyun)
          and (c_son > o_son)
          and hacim_orani >= 1.1
      ):
        return '👤 TOBO (RETEST ONAYLI)', '🟢 LONG', boyun

  # 4. 👤 OBO (RETEST ONAYLI OBO)
  if 'OBO (Retest Onaylı OBO)' in aktif_formasyonlar and len(tepe_idx) >= 3:
    sol, bas, sag = tepe_idx[-3], tepe_idx[-2], tepe_idx[-1]
    if (
        highs[bas] > highs[sol]
        and highs[bas] > highs[sag]
        and abs(highs[sol] - highs[sag]) / highs[sol] <= 0.035
    ):
      taban = round(
          float(min(min(lows[sol:bas]), min(lows[bas : sag + 1]))), 6
      )
      kirilim_oldu = any(closes[-5:-1] < taban * 0.998)
      retest_degdi = any(highs[-3:] >= taban * 0.994) and any(
          highs[-3:] <= taban * 1.008
      )
      if (
          kirilim_oldu
          and retest_degdi
          and (c_son < taban)
          and (c_son < o_son)
          and hacim_orani >= 1.1
      ):
        return '👤 OBO (RETEST ONAYLI)', '🔴 SHORT', taban

  # 5. 🚩 BOĞA BAYRAĞI (RETEST ONAYLI)
  if 'Boğa Bayrağı (Retest Onaylı Bull Flag)' in aktif_formasyonlar and len(df) >= 20:
    direk = ((closes[-6] - closes[-18]) / closes[-18]) * 100
    flama_tavan = round(float(max(highs[-6:-2])), 6)
    flama_taban = min(lows[-6:-2])
    if (
        direk >= 4.0
        and ((flama_tavan - flama_taban) / closes[-6] * 100) <= 2.8
    ):
      kirilim_oldu = any(closes[-4:-1] > flama_tavan)
      retest_degdi = any(lows[-2:] <= flama_tavan * 1.004) and any(
          lows[-2:] >= flama_tavan * 0.992
      )
      if (
          kirilim_oldu
          and retest_degdi
          and (c_son > flama_tavan)
          and (c_son > o_son)
      ):
        return '🚩 BOĞA BAYRAĞI (RETEST ONAYLI)', '🟢 LONG', flama_tavan

  # 6. 🚩 AYI BAYRAĞI (RETEST ONAYLI)
  if 'Ayı Bayrağı (Retest Onaylı Bear Flag)' in aktif_formasyonlar and len(df) >= 20:
    direk = ((closes[-6] - closes[-18]) / closes[-18]) * 100
    flama_tavan = max(highs[-6:-2])
    flama_taban = round(float(min(lows[-6:-2])), 6)
    if (
        direk <= -4.0
        and ((flama_tavan - flama_taban) / closes[-6] * 100) <= 2.8
    ):
      kirilim_oldu = any(closes[-4:-1] < flama_taban)
      retest_degdi = any(highs[-2:] >= flama_taban * 0.996) and any(
          highs[-2:] <= flama_taban * 1.008
      )
      if (
          kirilim_oldu
          and retest_degdi
          and (c_son < flama_taban)
          and (c_son < o_son)
      ):
        return '🚩 AYI BAYRAĞI (RETEST ONAYLI)', '🔴 SHORT', flama_taban

  # 7. 📐 YÜKSELEN ÜÇGEN (RETEST ONAYLI)
  if (
      'Yükselen Üçgen (Retest Onaylı)' in aktif_formasyonlar
      and len(tepe_idx) >= 2
      and len(dip_idx) >= 2
  ):
    t1, t2 = highs[tepe_idx[-2]], highs[tepe_idx[-1]]
    d1, d2 = lows[dip_idx[-2]], lows[dip_idx[-1]]
    if abs(t1 - t2) / t1 <= 0.015 and d2 > d1:
      direnc = round(float(max(t1, t2)), 6)
      kirilim_oldu = any(closes[-4:-1] > direnc * 1.001)
      retest_degdi = any(lows[-2:] <= direnc * 1.004) and any(
          lows[-2:] >= direnc * 0.994
      )
      if kirilim_oldu and retest_degdi and (c_son > direnc) and (c_son > o_son):
        return '📐 YÜKSELEN ÜÇGEN (RETEST ONAYLI)', '🟢 LONG', direnc

  # 8. 📐 ALÇALAN ÜÇGEN (RETEST ONAYLI)
  if (
      'Alçalan Üçgen (Retest Onaylı)' in aktif_formasyonlar
      and len(tepe_idx) >= 2
      and len(dip_idx) >= 2
  ):
    t1, t2 = highs[tepe_idx[-2]], highs[tepe_idx[-1]]
    d1, d2 = lows[dip_idx[-2]], lows[dip_idx[-1]]
    if abs(d1 - d2) / d1 <= 0.015 and t2 < t1:
      destek = round(float(min(d1, d2)), 6)
      kirilim_oldu = any(closes[-4:-1] < destek * 0.999)
      retest_degdi = any(highs[-2:] >= destek * 0.996) and any(
          highs[-2:] <= destek * 1.006
      )
      if kirilim_oldu and retest_degdi and (c_son < destek) and (c_son < o_son):
        return '📐 ALÇALAN ÜÇGEN (RETEST ONAYLI)', '🔴 SHORT', destek

  return None, None, None


# --- PİYASA TARAMA MOTORU ---
def piyasa_tara():
  mexc = ccxt.mexc(
      {'options': {'defaultType': 'swap'}, 'enableRateLimit': True}
  )

  try:
    tickers = mexc.fetch_tickers()
  except Exception as e:
    st.error(f'MEXC Bağlantı Hatası: {e}')
    return pd.DataFrame()

  usdt_pariteler = [s for s in tickers.keys() if '/USDT' in s]
  usdt_pariteler.sort(
      key=lambda x: tickers[x].get('quoteVolume', 0) or 0, reverse=True
  )
  hedef_listesi = usdt_pariteler[:coin_adedi]

  sonuclar = []

  for sembol in hedef_listesi:
    try:
      mumlar = mexc.fetch_ohlcv(sembol, timeframe=zaman_dilimi, limit=50)
      if len(mumlar) >= 30:
        df = pd.DataFrame(
            mumlar,
            columns=['Zaman', 'Acilis', 'Yuksek', 'Dusuk', 'Kapanis', 'Hacim'],
        )

        gecmis_hacim = df['Hacim'].iloc[:-1].mean()
        son_hacim = df['Hacim'].iloc[-1]
        hacim_orani = son_hacim / gecmis_hacim if gecmis_hacim > 0 else 0
        son_kapanis = df['Kapanis'].iloc[-1]

        formasyon_adi, yon, kirilan_seviye = retest_formasyon_bul(
            df, hacim_orani
        )

        if formasyon_adi:
          temiz_parite = sembol.split(':')[0]
          mexc_kod = temiz_parite.replace('/', '_')
          mexc_link = f'https://www.mexc.com/tr-TR/futures/{mexc_kod}'

          atr = hesapla_atr(df)
          yon_turu = 'LONG' if 'LONG' in yon else 'SHORT'
          tp1, tp2, sl = hesapla_tp_sl(son_kapanis, atr, yon=yon_turu)

          sinyal_id = f'{temiz_parite}_{formasyon_adi}_{zaman_dilimi}'

          # Telegram Gönderimi
          if (
              telegram_aktif
              and sinyal_id not in st.session_state.retest_hafiza
          ):
            tg_caption = (
                f'🛡️ <b>MEXC RETEST ONAYLI FORMASYON SİNYALİ</b>\n\n'
                f'📌 <b>Parite:</b> {temiz_parite}\n'
                f'🎯 <b>Yön:</b> {yon}\n'
                f'⚡ <b>Formasyon:</b> {formasyon_adi}\n'
                f'📏 <b>Kırılan/Retest Seviyesi:</b> {kirilan_seviye} $\n'
                f'⏱ <b>Zaman:</b> {zaman_dilimi}\n'
                f'💰 <b>Onaylı Giriş:</b> {son_kapanis} $\n'
                f'📊 <b>Hacim Katı:</b> {round(hacim_orani, 1)}x\n\n'
                f'🎯 <b>HEDEF 1 (TP1):</b> {tp1} $\n'
                f'🎯 <b>HEDEF 2 (TP2):</b> {tp2} $\n'
                f'🛑 <b>STOP-LOSS:</b> {sl} $\n\n'
                f"🔗 <a href='{mexc_link}'>MEXC Grafiği Aç ↗</a>"
            )
            try:
              foto_buffer = grafik_olustur_cizimli(
                  df,
                  temiz_parite,
                  zaman_dilimi,
                  formasyon_adi,
                  kirilan_seviye,
                  tp1,
                  sl,
              )
              telegram_fotograf_gonder(foto_buffer, tg_caption)
            except Exception:
              pass

            st.session_state.retest_hafiza.add(sinyal_id)

          sonuclar.append({
              'Yön': yon,
              'Onaylanan Formasyon': formasyon_adi,
              'Kırılan/Retest Hattı': f'{kirilan_seviye} $',
              'Sembol': temiz_parite,
              'Onay Fiyatı ($)': son_kapanis,
              'TP1 ($)': tp1,
              'SL ($)': sl,
              'Hacim Katı': f'{round(hacim_orani, 1)}x',
              'Grafik': mexc_link,
          })
    except Exception:
      pass

  return pd.DataFrame(sonuclar)


# --- ÇALIŞTIRMA VE GÖRÜNTÜLEME ---
manuel_tara = st.button(
    '🔍 Çizimli Retest Formasyonlarını Tara',
    type='primary',
    use_container_width=True,
)

if oto_yenileme or manuel_tara:
  with st.spinner('Grafik formasyonları ve retest seviyeleri çiziliyor...'):
    df_sonuc = piyasa_tara()

  if not df_sonuc.empty:
    st.success(
        '🎯 Retest Yapıp Onay Almış Fırsatlar'
        f' ({pd.Timestamp.now().strftime("%H:%M:%S")}):'
    )
    st.dataframe(
        df_sonuc,
        column_config={
            'Grafik': st.column_config.LinkColumn(
                'MEXC Link', display_text='Grafiği Aç ↗'
            )
        },
        use_container_width=True,
    )
  else:
    st.info(
        'Şu an kırılım sonrası retestini tamamlayıp yön teyidi veren formasyon'
        f' bulunamadı ({pd.Timestamp.now().strftime("%H:%M:%S")}).'
    )
