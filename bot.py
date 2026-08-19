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

# --- SABİT BOT VE TELEGRAM AYARLARI ---
BOT_TOKEN = "7820599329:AAEAa13edhS9PLoG1t8R34PLO9xpKlaT_Lc"
CHAT_ID = "-1004434260285"
TOPIC_ID = 3802
COIN_ADEDI = 60

hafiza = set()


# Render Port Dinleyicisi
class HealthCheckHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.send_header("Content-type", "text/plain; charset=utf-8")
    self.end_headers()
    self.wfile.write(b"KENDINE22TRADER Formasyon Botu 7/24 Aktif!")

  def log_message(self, format, *args):
    return


def start_http_server():
  port = int(os.environ.get("PORT", 10000))
  server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
  print(f"🌐 HTTP Sunucu Port {port} üzerinde başlatıldı.")
  server.serve_forever()


def telegram_metin_gonder(metin):
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
  data = {
      "chat_id": CHAT_ID,
      "message_thread_id": TOPIC_ID,
      "text": metin,
      "parse_mode": "HTML",
  }
  try:
    requests.post(url, data=data, timeout=10)
  except Exception as e:
    print(f"Telegram Metin Hatası: {e}")


def telegram_gonder(foto_buf, caption):
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
  data = {
      "chat_id": CHAT_ID,
      "message_thread_id": TOPIC_ID,
      "caption": caption,
      "parse_mode": "HTML",
  }
  files = {"photo": ("chart.png", foto_buf, "image/png")}
  try:
    res = requests.post(url, data=data, files=files, timeout=15)
    if res.status_code != 200:
      print(f"Telegram Fotoğraf Hatası Yanıtı: {res.text}")
  except Exception as e:
    print(f"Telegram Fotoğraf Hatası: {e}")


def grafik_ciz(
    df_mum, sembol, tf_etiket, formasyon_adi, kirilan_seviye, tp1, tp2, sl
):
  df_grafik = df_mum.copy()
  df_grafik["Zaman"] = pd.to_datetime(df_grafik["Zaman"], unit="ms")
  df_grafik.set_index("Zaman", inplace=True)
  df_grafik.rename(
      columns={
          "Acilis": "Open",
          "Yuksek": "High",
          "Dusuk": "Low",
          "Kapanis": "Close",
          "Hacim": "Volume",
      },
      inplace=True,
  )
  df_plot = df_grafik.tail(42)

  mc = mpf.make_marketcolors(
      up="#00FF88", down="#FF3366", inherit=True, volume="in"
  )
  s = mpf.make_mpf_style(
      base_mpf_style="nightclouds",
      marketcolors=mc,
      gridcolor="#20242C",
      facecolor="#0E1117",
      edgecolor="#30363D",
      figcolor="#0E1117",
  )
  hlines_dict = dict(
      hlines=[kirilan_seviye, tp1, tp2, sl],
      colors=["#00D4FF", "#00FF88", "#38EF7D", "#FF3366"],
      linestyle=["-", "--", "-.", ":"],
      linewidths=[2.2, 1.6, 1.4, 1.6],
  )

  buf = io.BytesIO()
  fig, axes = mpf.plot(
      df_plot,
      type="candle",
      volume=True,
      style=s,
      hlines=hlines_dict,
      returnfig=True,
      figsize=(10, 6),
      savefig=dict(dpi=140, bbox_inches="tight"),
  )
  ax_main = axes[0]
  ax_main.set_title(
      f"KENDİNE22TRADER | {sembol} ({tf_etiket}) - {formasyon_adi}",
      fontsize=12,
      fontweight="bold",
      color="#F4E07B",
      pad=12,
  )

  son_x = len(df_plot) - 1
  ax_main.text(
      son_x,
      kirilan_seviye,
      f"  ⚡ Retest: {kirilan_seviye}$",
      color="#00D4FF",
      fontsize=8.5,
      fontweight="bold",
      bbox=dict(
          boxstyle="round,pad=0.25",
          facecolor="#0D223A",
          edgecolor="#00D4FF",
          alpha=0.9,
      ),
      verticalalignment="center",
  )
  ax_main.text(
      son_x,
      tp1,
      f"  🎯 TP1: {tp1}$",
      color="#00FF88",
      fontsize=8,
      fontweight="bold",
      bbox=dict(
          boxstyle="round,pad=0.2",
          facecolor="#092E1B",
          edgecolor="#00FF88",
          alpha=0.9,
      ),
      verticalalignment="center",
  )
  ax_main.text(
      son_x,
      sl,
      f"  🛑 STOP: {sl}$",
      color="#FF3366",
      fontsize=8,
      fontweight="bold",
      bbox=dict(
          boxstyle="round,pad=0.2",
          facecolor="#350F18",
          edgecolor="#FF3366",
          alpha=0.9,
      ),
      verticalalignment="center",
  )

  fig.savefig(buf, format="png", bbox_inches="tight", facecolor="#0E1117")
  buf.seek(0)
  plt.close("all")
  return buf


def retest_bul(df, hacim_orani):
  highs, lows, closes, opens = (
      df["Yuksek"].values,
      df["Dusuk"].values,
      df["Kapanis"].values,
      df["Acilis"].values,
  )
  c_son, o_son = closes[-1], opens[-1]

  dip_idx, tepe_idx = [], []
  for i in range(2, len(df) - 3):
    if (
        lows[i] <= lows[i - 1]
        and lows[i] <= lows[i - 2]
        and lows[i] <= lows[i + 1]
        and lows[i] <= lows[i + 2]
    ):
      dip_idx.append(i)
    if (
        highs[i] >= highs[i - 1]
        and highs[i] >= highs[i - 2]
        and highs[i] >= highs[i + 1]
        and highs[i] >= highs[i + 2]
    ):
      tepe_idx.append(i)

  # W Dip
  if len(dip_idx) >= 2:
    d1, d2 = dip_idx[-2], dip_idx[-1]
    if (
        abs(lows[d1] - lows[d2]) / lows[d1] <= 0.03
        and (d2 - d1) >= 4
        and (len(df) - 1 - d2) <= 15
    ):
      boyun = round(float(max([highs[k] for k in range(d1, d2 + 1)])), 6)
      if (
          any(closes[-6:-1] > boyun * 1.001)
          and any(lows[-4:] <= boyun * 1.01)
          and (c_son >= boyun * 0.998)
          and (c_son >= o_son)
      ):
        return "📐 W FORMASYONU (RETEST ONAYLANDI 🚀)", "🟢 LONG", boyun

  # M Tepe
  if len(tepe_idx) >= 2:
    t1, t2 = tepe_idx[-2], tepe_idx[-1]
    if (
        abs(highs[t1] - highs[t2]) / highs[t1] <= 0.03
        and (t2 - t1) >= 4
        and (len(df) - 1 - t2) <= 15
    ):
      taban = round(float(min([lows[k] for k in range(t1, t2 + 1)])), 6)
      if (
          any(closes[-6:-1] < taban * 0.999)
          and any(highs[-4:] >= taban * 0.99)
          and (c_son <= taban * 1.002)
          and (c_son <= o_son)
      ):
        return "📐 M FORMASYONU (RETEST ONAYLANDI 🩸)", "🔴 SHORT", taban

  # TOBO
  if len(dip_idx) >= 3:
    sol, bas, sag = dip_idx[-3], dip_idx[-2], dip_idx[-1]
    if (
        lows[bas] < lows[sol]
        and lows[bas] < lows[sag]
        and abs(lows[sol] - lows[sag]) / lows[sol] <= 0.04
    ):
      boyun = round(
          float(max(max(highs[sol:bas]), max(highs[bas : sag + 1]))), 6
      )
      if (
          any(closes[-6:-1] > boyun * 1.001)
          and any(lows[-4:] <= boyun * 1.01)
          and (c_son >= boyun * 0.998)
      ):
        return "👤 TOBO (RETEST ONAYLANDI 🚀)", "🟢 LONG", boyun

  # OBO
  if len(tepe_idx) >= 3:
    sol, bas, sag = tepe_idx[-3], tepe_idx[-2], tepe_idx[-1]
    if (
        highs[bas] > highs[sol]
        and highs[bas] > highs[sag]
        and abs(highs[sol] - highs[sag]) / highs[sol] <= 0.04
    ):
      taban = round(
          float(min(min(lows[sol:bas]), min(lows[bas : sag + 1]))), 6
      )
      if (
          any(closes[-6:-1] < taban * 0.999)
          and any(highs[-4:] >= taban * 0.99)
          and (c_son <= taban * 1.002)
      ):
        return "👤 OBO (RETEST ONAYLANDI 🩸)", "🔴 SHORT", taban

  # Bull Flag
  if len(df) >= 20:
    direk = ((closes[-5] - closes[-16]) / closes[-16]) * 100
    flama_tavan = round(float(max(highs[-5:-1])), 6)
    if (
        direk >= 3.0
        and any(closes[-4:-1] > flama_tavan * 0.999)
        and any(lows[-2:] <= flama_tavan * 1.008)
        and (c_son >= flama_tavan * 0.998)
    ):
      return "🚩 BOĞA BAYRAĞI (RETEST ONAYLANDI 🚀)", "🟢 LONG", flama_tavan

  # Bear Flag
  if len(df) >= 20:
    direk = ((closes[-5] - closes[-16]) / closes[-16]) * 100
    flama_taban = round(float(min(lows[-5:-1])), 6)
    if (
        direk <= -3.0
        and any(closes[-4:-1] < flama_taban * 1.001)
        and any(highs[-2:] >= flama_taban * 0.992)
        and (c_son <= flama_taban * 1.002)
    ):
      return "🚩 AYI BAYRAĞI (RETEST ONAYLANDI 🩸)", "🔴 SHORT", flama_taban

  # Yükselen Üçgen
  if len(tepe_idx) >= 2 and len(dip_idx) >= 2:
    t1, t2 = highs[tepe_idx[-2]], highs[tepe_idx[-1]]
    d1, d2 = lows[dip_idx[-2]], lows[dip_idx[-1]]
    if abs(t1 - t2) / t1 <= 0.02 and d2 > d1:
      direnc = round(float(max(t1, t2)), 6)
      if (
          any(closes[-4:-1] > direnc * 0.999)
          and any(lows[-2:] <= direnc * 1.008)
          and (c_son >= direnc * 0.998)
      ):
        return "📐 YÜKSELEN ÜÇGEN (RETEST ONAYLANDI 🚀)", "🟢 LONG", direnc

  # Alçalan Üçgen
  if len(tepe_idx) >= 2 and len(dip_idx) >= 2:
    t1, t2 = highs[tepe_idx[-2]], highs[tepe_idx[-1]]
    d1, d2 = lows[dip_idx[-2]], lows[dip_idx[-1]]
    if abs(d1 - d2) / d1 <= 0.02 and t2 < t1:
      destek = round(float(min(d1, d2)), 6)
      if (
          any(closes[-4:-1] < destek * 1.001)
          and any(highs[-2:] >= destek * 0.992)
          and (c_son <= destek * 1.002)
      ):
        return "📐 ALÇALAN ÜÇGEN (RETEST ONAYLANDI 🩸)", "🔴 SHORT", destek

  return None, None, None


def main():
  threading.Thread(target=start_http_server, daemon=True).start()
  print("🚀 KENDİNE22TRADER 7/24 Kesintisiz Formasyon Motoru Başlatıldı...")

  # Başlangıç Test Mesajı
  telegram_metin_gonder(
      "🟢 <b>KENDİNE22TRADER Formasyon Motoru Devrede!</b>\n"
      "Mevcut pariteler 15m, 30m, 1h, 4h, 1d ve 1w zaman dilimlerinde taranmaya"
      " başlandı. Retest onayı alan coinler grafikli olarak bu kanala"
      " aktarılacaktır."
  )

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      ),
      "Accept": "application/json, text/plain, */*",
  }

  zaman_dilimleri = [
      ("Min15", "15m", "15 Dakika"),
      ("Min30", "30m", "30 Dakika"),
      ("Min60", "1h", "1 Saat"),
      ("Hour4", "4h", "4 Saat"),
      ("Day1", "1d", "1 Gün"),
      ("Week1", "1w", "1 Hafta"),
  ]

  while True:
    try:
      url_tickers = "https://contract.mexc.com/api/v1/contract/ticker"
      res = requests.get(url_tickers, headers=headers, timeout=8).json()

      if res.get("success", False):
        data_tickers = res.get("data", [])
        usdt_pariteler = [
            d for d in data_tickers if d.get("symbol", "").endswith("_USDT")
        ]
        usdt_pariteler.sort(
            key=lambda x: float(x.get("amount24", 0) or 0), reverse=True
        )
        hedef_listesi = usdt_pariteler[:COIN_ADEDI]

        for coin in hedef_listesi:
          sembol_raw = coin["symbol"]
          temiz_parite = sembol_raw.replace("_", "/")
          mexc_link = f"https://www.mexc.com/tr-TR/futures/{sembol_raw}"

          for api_tf, tf_kod, tf_ad in zaman_dilimleri:
            try:
              url_kline = f"https://contract.mexc.com/api/v1/contract/kline/{sembol_raw}?interval={api_tf}"
              kline_res = requests.get(
                  url_kline, headers=headers, timeout=3
              ).json()

              if kline_res.get("success", False) and kline_res.get("data"):
                k_data = kline_res["data"]
                times = k_data.get("time", [])
                opens = k_data.get("open", [])
                closes = k_data.get("close", [])
                highs = k_data.get("high", [])
                lows = k_data.get("low", [])
                vols = k_data.get("vol", [])

                if len(closes) >= 30:
                  df = pd.DataFrame({
                      "Zaman": [t * 1000 for t in times[-50:]],
                      "Acilis": [float(x) for x in opens[-50:]],
                      "Yuksek": [float(x) for x in highs[-50:]],
                      "Dusuk": [float(x) for x in lows[-50:]],
                      "Kapanis": [float(x) for x in closes[-50:]],
                      "Hacim": [float(x) for x in vols[-50:]],
                  })

                  gecmis_hacim = df["Hacim"].iloc[:-1].mean()
                  son_hacim = df["Hacim"].iloc[-1]
                  hacim_orani = (
                      (son_hacim / gecmis_hacim) if gecmis_hacim > 0 else 0
                  )
                  son_kapanis = df["Kapanis"].iloc[-1]

                  formasyon_adi, yon, kirilan_seviye = retest_bul(
                      df, hacim_orani
                  )
                  if formasyon_adi:
                    sinyal_id = f"{sembol_raw}_{formasyon_adi}_{tf_kod}"
                    if sinyal_id not in hafiza:
                      atr = (
                          (df["Yuksek"] - df["Dusuk"])
                          .rolling(14)
                          .mean()
                          .iloc[-1]
                      )
                      if np.isnan(atr):
                        atr = son_kapanis * 0.02

                      sl = (
                          round(son_kapanis - (atr * 1.5), 6)
                          if "LONG" in yon
                          else round(son_kapanis + (atr * 1.5), 6)
                      )
                      tp1 = (
                          round(son_kapanis + (atr * 1.5), 6)
                          if "LONG" in yon
                          else round(son_kapanis - (atr * 1.5), 6)
                      )
                      tp2 = (
                          round(son_kapanis + (atr * 3.0), 6)
                          if "LONG" in yon
                          else round(son_kapanis - (atr * 3.0), 6)
                      )

                      tg_caption = (
                          "🛡️ <b>KENDİNE22TRADER ÇOKLU FORMASYON SİNYALİ</b>\n\n"
                          f"📌 <b>Parite:</b> {temiz_parite}\n"
                          f"⏱ <b>Zaman Dilimi:</b> <b>{tf_ad} ({tf_kod})</b>\n"
                          f"🎯 <b>Yön:</b> {yon}\n"
                          f"⚡ <b>Formasyon:</b> {formasyon_adi}\n"
                          f"📏 <b>Kırılan/Retest Seviyesi:</b> {kirilan_seviye}"
                          " $\n"
                          f"💰 <b>Onaylı Giriş:</b> {son_kapanis} $\n"
                          f"📊 <b>Hacim Katı:</b> {round(hacim_orani, 1)}x\n\n"
                          f"🎯 <b>HEDEF 1 (TP1):</b> {tp1} $\n"
                          f"🎯 <b>HEDEF 2 (TP2):</b> {tp2} $\n"
                          f"🛑 <b>STOP-LOSS:</b> {sl} $\n\n"
                          f"🔗 <a href='{mexc_link}'>MEXC Vadeli Grafiği Aç"
                          " ↗</a>"
                      )
                      foto = grafik_ciz(
                          df,
                          temiz_parite,
                          f"{tf_ad} ({tf_kod})",
                          formasyon_adi,
                          kirilan_seviye,
                          tp1,
                          tp2,
                          sl,
                      )
                      telegram_gonder(foto, tg_caption)
                      hafiza.add(sinyal_id)
                      print(f"✅ Sinyal Gönderildi: {sinyal_id}")
            except Exception:
              pass
    except Exception as e:
      print(f"Genel Tarama Hatası: {e}")

    time.sleep(30)


if __name__ == "__main__":
  main()
