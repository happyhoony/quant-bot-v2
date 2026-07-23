import FinanceDataReader as fdr
import yfinance as yf
from datetime import datetime, timedelta, timezone
import time
import os
import OpenDartReader
import google.generativeai as genai
import requests

DART_KEY = os.environ.get('DART_API_KEY')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TG_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST)
today_date_str = now_kst.strftime('%Y-%m-%d')
start_120_str = (now_kst - timedelta(days=120)).strftime('%Y-%m-%d')
recent_3m_str = (now_kst - timedelta(days=90)).strftime('%Y%m%d')

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'HTML'})

try:
    df_krx = fdr.StockListing('KRX')
    df_cap_filtered = df_krx[df_krx['Marcap'] >= 300000000000] # 3천억 이상
    
    passed_stocks = []
    for index, row in df_cap_filtered.head(1500).iterrows():
        code, name, market = row['Code'], row['Name'], row['Market']
        try:
            yahoo_symbol = f"{code}.KS" if market == "KOSPI" else f"{code}.KQ" if market == "KOSDAQ" else code
            df_price = fdr.DataReader(yahoo_symbol, start_120_str, today_date_str)
            if len(df_price) < 60: continue
            
            latest_close = df_price['Close'].iloc[-1]
            high_120 = df_price['High'].max()
            
            # 조건: 고점 대비 5% 이내 (신고가 근접)
            if latest_close >= high_120 * 0.95 and latest_close >= 1000:
                ticker = yf.Ticker(yahoo_symbol)
                eps = ticker.info.get('trailingEps', 0)
                per = ticker.info.get('trailingPE', 0)
                if eps and per and eps > 0 and 10 <= per <= 60:
                    passed_stocks.append({'name': name, 'price': int(latest_close), 'per': round(per, 1)})
                    if len(passed_stocks) >= 10: break
        except:
            continue

    dart = OpenDartReader(DART_KEY)
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

    report_items = []
    for item in passed_stocks:
        time.sleep(1)
        try:
            dart_reports = dart.list(item['name'], start=recent_3m_str)
            news_list = dart_reports['report_nm'].head(5).tolist() if dart_reports is not None and not dart_reports.empty else ["최근 공시 없음"]
        except:
            news_list = ["공시 수집 에러"]

        prompt = f"기업명: {item['name']}\n공시: {news_list}\n단기 투자 모멘텀을 1~10점 사이로 평가하고, 성장성 관점에서 한 줄 요약하세요.\n형식(반드시 2줄):\n성장 스코어: 8점\nAI 요약: 내용"
        try:
            res = model.generate_content(prompt)
            lines = [line.replace('*', '').strip() for line in res.text.strip().split('\n') if line.strip()]
            score_line = next((line for line in lines if "스코어" in line), "성장 스코어: 평가 불가")
            summary_line = next((line for line in lines if "요약" in line), "AI 요약: 내용 없음")
            ai_text = f"{score_line}\n{summary_line}" 
        except:
            ai_text = "AI 분석 지연"
        
        report_items.append({'name': item['name'], 'price': item['price'], 'per': item['per'], 'ai': ai_text})

    tg_msg = f"🚀 [슈퍼 성장주 AI 리포트 v2.0]\n📅 {now_kst.strftime('%Y년 %m월 %d일')}\n\n"
    if not report_items: tg_msg += "⚠️ 오늘 신고가를 갱신한 우량 성장주가 없습니다."
    else:
        for idx, r in enumerate(report_items):
            tg_msg += f"🔥 [{idx+1}] {r['name']}\n▪️ 현재가: {r['price']:,}원 / PER: {r['per']}배\n▪️ {r['ai']}\n\n"
    send_telegram_message(tg_msg)
except Exception as e:
    print(e)
