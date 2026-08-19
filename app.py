import io
import time
import urllib.parse
import ccxt
import matplotlib
import mplfinance as mpf
import numpy as np
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

matplotlib.use('Agg')

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title='MEXC VIP Saf Geometrik Formasyon Radarı', layout='wide'
)

if 'formasyon_hafiza' not in st.session_state:
  st.session_state.formasyon_hafiza = set()

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
    help='Formasyon için açtığınız konunun ID numarası (Ana grupsa boş bırakın)',
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
  st_autorefresh(interval=yenileme_araligi * 1000, key='formasyon_tarayici')
  st.sidebar.success(f'🟢 Canlı mod aktif: Her {yenileme_araligi} sn')

st.sidebar.markdown('---')
st.sidebar.header('🎯 Geometrik Formasyon Tercihleri')

zaman_dilimi = st.sidebar.selectbox(
    'Zaman Dilimi (Timeframe)',
    options=['15m', '1h', '4h', '1d'],
    index=0,
)

aktif_formasyonlar = st.sidebar.multiselect(
    'Taranacak Grafik Formasyonları',
    options=[
        'W Formasyonu (İkili Dip)',
        'M Formasyonu (İkili Tepe)',
        'TOBO (Ters Omuz Baş Omuz)',
        'OBO (Omuz Baş Omuz)',
        'Boğa Bayrağı (Bull Flag)',
        'Ayı Bayrağı (Bear Flag)',
        'Yükselen Üçgen',
        'Alçalan Üçgen',
    ],
    default=[
        'W Formasyonu (İkili Dip)',
        'M Formasyonu (İkili Tepe)',
        'TOBO (Ters Omuz Baş Omuz)',
        'OBO (Omuz Baş Omuz)',
        'Boğa Bayrağı (Bull Flag)',
        'Ayı Bayrağı (Bear Flag)',
        'Yükselen Üçgen',
        'Alçalan Üçgen',
    ],
)

coin_adedi = st.sidebar.select_slider(
    'Taranacak En Yüksek Hacimli Coin Sayısı',
    options=[30, 50, 100, 150, 200],
    value=100,
)

st.title('📐 MEXC Vadeli Saf Geometrik Grafik Formasyonları Radarı')


# --- GRAFİK OLUŞTURMA ---
def grafik_olustur(df_mum, sembol, zaman_dilimi):
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

  mc = mpf.make_marketcolors(up='#00ff88', down='#ff3366', inherit=True)
  s = mpf.make_mpf_style(
      base_mpf_style='nightclouds', marketcolors=mc, gridcolor='#2b2b2b'
  )

  buf = io.BytesIO()
  mpf.plot(
      df_grafik.tail(45),
      type='candle',
      volume=True,
      style=s,
      title=f'{sembol} ({zaman_dilimi}) - Formasyon Kırılımı',
      savefig=dict(fname=buf, dpi=120, bbox_inches='tight'),
  )
  buf.seek(0)
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


# --- TEKNİK HESAPLAMALAR & TP/SL ---
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
# 📐 SAF GEOMETRİK GRAFİK FORMASYONLARI MOTORU (50 MUMLUK ALAN)
# ==============================================================
def geometrik_formasyon_bul(df, hacim_orani):
  highs = df['Yuksek'].values
  lows = df['Dusuk'].values
  closes = df['Kapanis'].values
  opens = df['Acilis'].values

  c_son = closes[-1]
  c_on = closes[-2]
  o_son = opens[-1]

  # Yerel Swing Noktalarını Çıkar
  dip_idx = []
  tepe_idx = []
  for i in range(3, len(df) - 3):
    if (
        lows[i] < lows[i - 1]
        and lows[i] < lows[i - 2]
        and lows[i] < lows[i - 3]
        and lows[i] < lows[i + 1]
        and lows[i] < lows[i + 2]
        and lows[i] < lows[i + 3]
    ):
      dip_idx.append(i)
    if (
        highs[i] > highs[i - 1]
        and highs[i] > highs[i - 2]
        and highs[i] > highs[i - 3]
        and highs[i] > highs[i + 1]
        and highs[i] > highs[i + 2]
        and highs[i] > highs[i + 3]
    ):
      tepe_idx.append(i)

  # 1. 📐 W FORMASYONU (İKİLİ DİP BOYUN KIRILIMI)
  if 'W Formasyonu (İkili Dip)' in aktif_formasyonlar and len(dip_idx) >= 2:
    d1, d2 = dip_idx[-2], dip_idx[-1]
    if (
        abs(lows[d1] - lows[d2]) / lows[d1] <= 0.02
        and (d2 - d1) >= 6
        and (len(df) - 1 - d2) <= 8
    ):
      ara_tepeler = [highs[k] for k in range(d1, d2 + 1)]
      if ara_tepeler:
        boyun = max(ara_tepeler)
        if (
            c_son >= boyun
            and c_on < boyun
            and c_son > o_son
            and hacim_orani >= 1.2
        ):
          return '📐 W FORMASYONU (İKİLİ DİP BOYUN KIRILIMI)', '🟢 LONG'

  # 2. 📐 M FORMASYONU (İKİLİ TEPE TABAN KIRILIMI)
  if 'M Formasyonu (İkili Tepe)' in aktif_formasyonlar and len(tepe_idx) >= 2:
    t1, t2 = tepe_idx[-2], tepe_idx[-1]
    if (
        abs(highs[t1] - highs[t2]) / highs[t1] <= 0.02
        and (t2 - t1) >= 6
        and (len(df) - 1 - t2) <= 8
    ):
      ara_dipler = [lows[k] for k in range(t1, t2 + 1)]
      if ara_dipler:
        taban = min(ara_dipler)
        if (
            c_son <= taban
            and c_on > taban
            and c_son < o_son
            and hacim_orani >= 1.2
        ):
          return '📐 M FORMASYONU (İKİLİ TEPE TABAN KIRILIMI)', '🔴 SHORT'

  # 3. 👤 TOBO (TERS OMUZ BAŞ OMUZ)
  if 'TOBO (Ters Omuz Baş Omuz)' in aktif_formasyonlar and len(dip_idx) >= 3:
    sol_omuz, bas, sag_omuz = dip_idx[-3], dip_idx[-2], dip_idx[-1]
    if (
        lows[bas] < lows[sol_omuz]
        and lows[bas] < lows[sag_omuz]
        and abs(lows[sol_omuz] - lows[sag_omuz]) / lows[sol_omuz] <= 0.03
    ):
      boyun_bolgesi = max(
          max(highs[sol_omuz:bas]),
          max(highs[bas : sag_omuz + 1]),
      )
      if (
          c_son >= boyun_bolgesi
          and c_on < boyun_bolgesi
          and c_son > o_son
          and hacim_orani >= 1.2
      ):
        return '👤 TOBO (TERS OMUZ BAŞ OMUZ KIRILIMI)', '🟢 LONG'

  # 4. 👤 OBO (OMUZ BAŞ OMUZ)
  if 'OBO (Omuz Baş Omuz)' in aktif_formasyonlar and len(tepe_idx) >= 3:
    sol_omuz, bas, sag_omuz = tepe_idx[-3], tepe_idx[-2], tepe_idx[-1]
    if (
        highs[bas] > highs[sol_omuz]
        and highs[bas] > highs[sag_omuz]
        and abs(highs[sol_omuz] - highs[sag_omuz]) / highs[sol_omuz] <= 0.03
    ):
      taban_bolgesi = min(
          min(lows[sol_omuz:bas]),
          min(lows[bas : sag_omuz + 1]),
      )
      if (
          c_son <= taban_bolgesi
          and c_on > taban_bolgesi
          and c_son < o_son
          and hacim_orani >= 1.2
      ):
        return '👤 OBO (OMUZ BAŞ OMUZ KIRILIMI)', '🔴 SHORT'

  # 5. 🚩 BOĞA BAYRAĞI (BULL FLAG)
  if 'Boğa Bayrağı (Bull Flag)' in aktif_formasyonlar and len(df) >= 20:
    direk_kazanc = ((closes[-5] - closes[-16]) / closes[-16]) * 100
    flama_aralik = (max(highs[-5:-1]) - min(lows[-5:-1])) / closes[-5] * 100
    if (
        direk_kazanc >= 4.5
        and flama_aralik <= 2.2
        and c_son > max(highs[-5:-1])
        and c_son > o_son
        and hacim_orani >= 1.3
    ):
      return '🚩 BOĞA BAYRAĞI (BULL FLAG KIRILIMI)', '🟢 LONG'

  # 6. 🚩 AYI BAYRAĞI (BEAR FLAG)
  if 'Ayı Bayrağı (Bear Flag)' in aktif_formasyonlar and len(df) >= 20:
    direk_kayip = ((closes[-5] - closes[-16]) / closes[-16]) * 100
    flama_aralik = (max(highs[-5:-1]) - min(lows[-5:-1])) / closes[-5] * 100
    if (
        direk_kayip <= -4.5
        and flama_aralik <= 2.2
        and c_son < min(lows[-5:-1])
        and c_son < o_son
        and hacim_orani >= 1.3
    ):
      return '🚩 AYI BAYRAĞI (BEAR FLAG KIRILIMI)', '🔴 SHORT'

  # 7. 📐 YÜKSELEN ÜÇGEN (ASCENDING TRIANGLE)
  if 'Yükselen Üçgen' in aktif_formasyonlar and len(tepe_idx) >= 2 and len(dip_idx) >= 2:
    t1, t2 = highs[tepe_idx[-2]], highs[tepe_idx[-1]]
    d1, d2 = lows[dip_idx[-2]], lows[dip_idx[-1]]
    if abs(t1 - t2) / t1 <= 0.015 and d2 > d1:
      if (
          c_son >= max(t1, t2)
          and c_on < max(t1, t2)
          and c_son > o_son
          and hacim_orani >= 1.2
      ):
        return '📐 YÜKSELEN ÜÇGEN (DİRENÇ KIRILIMI)', '🟢 LONG'

  # 8. 📐 ALÇALAN ÜÇGEN (DESCENDING TRIANGLE)
  if 'Alçalan Üçgen' in aktif_formasyonlar and len(tepe_idx) >= 2 and len(dip_idx) >= 2:
    t1, t2 = highs[tepe_idx[-2]], highs[tepe_idx[-1]]
    d1, d2 = lows[dip_idx[-2]], lows[dip_idx[-1]]
    if abs(d1 - d2) / d1 <= 0.015 and t2 < t1:
      if (
          c_son <= min(d1, d2)
          and c_on > min(d1, d2)
          and c_son < o_son
          and hacim_orani >= 1.2
      ):
        return '📐 ALÇALAN ÜÇGEN (DESTEK KIRILIMI)', '🔴 SHORT'

  return None, None


# --- PİYASA TARAYICI ---
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

        formasyon_adi, yon = geometrik_formasyon_bul(df, hacim_orani)

        if formasyon_adi:
          temiz_parite = sembol.split(':')[0]
          mexc_kod = temiz_parite.replace('/', '_')
          mexc_link = f'https://www.mexc.com/tr-TR/futures/{mexc_kod}'

          atr = hesapla_atr(df)
          yon_turu = 'LONG' if 'LONG' in yon else 'SHORT'
          tp1, tp2, sl = hesapla_tp_sl(son_kapanis, atr, yon=yon_turu)

          sinyal_id = f'{temiz_parite}_{formasyon_adi}_{zaman_dilimi}'

          if (
              telegram_aktif
              and sinyal_id not in st.session_state.formasyon_hafiza
          ):
            tg_caption = (
                f'📐 <b>MEXC GRAFİK FORMASYON SİNYALİ</b>\n\n'
                f'📌 <b>Parite:</b> {temiz_parite}\n'
                f'🎯 <b>Yön:</b> {yon}\n'
                f'⚡ <b>Formasyon:</b> {formasyon_adi}\n'
                f'⏱ <b>Zaman:</b> {zaman_dilimi}\n'
                f'💰 <b>Kırılım Fiyatı:</b> {son_kapanis} $\n'
                f'📊 <b>Hacim Katı:</b> {round(hacim_orani, 1)}x\n\n'
                f'🎯 <b>HEDEF 1 (TP1):</b> {tp1} $\n'
                f'🎯 <b>HEDEF 2 (TP2):</b> {tp2} $\n'
                f'🛑 <b>STOP-LOSS:</b> {sl} $\n\n'
                f"🔗 <a href='{mexc_link}'>MEXC Grafiği Aç ↗</a>"
            )
            try:
              foto_buffer = grafik_olustur(df, temiz_parite, zaman_dilimi)
              telegram_fotograf_gonder(foto_buffer, tg_caption)
            except Exception:
              pass

            st.session_state.formasyon_hafiza.add(sinyal_id)

          sonuclar.append({
              'Yön': yon,
              'Tespit Edilen Geometrik Formasyon': formasyon_adi,
              'Sembol': temiz_parite,
              'Fiyat ($)': son_kapanis,
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
    '🔍 Geometrik Formasyonları Tara', type='primary', use_container_width=True
)

if oto_yenileme or manuel_tara:
  with st.spinner('Grafik formasyonları taranıyor...'):
    df_sonuc = piyasa_tara()

  if not df_sonuc.empty:
    st.success(
        f'Tespit Edilen Formasyonlar ({pd.Timestamp.now().strftime("%H:%M:%S")}):'
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
        'Şu an seçilen kriterlerde aktif formasyon kırılımı bulunamadı'
        f' ({pd.Timestamp.now().strftime("%H:%M:%S")}).'
    )
