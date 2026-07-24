import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import os
import OpenDartReader
import google.generativeai as genai
import requests

print("🚀 [삼박자 퀀트 AI 시스템 v2.0] 텔레그램 실시간 알림 가동...\n")

# 1. API 키 셋업
DART_KEY = os.environ.get('DART_API_KEY')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TG_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 시간 셋업
KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST)

today_date_str = now_kst.strftime('%Y-%m-%d')
start_210_str = (now_kst - timedelta(days=210)).strftime('%Y-%m-%d')
recent_3m_str = (now_kst - timedelta(days=90)).strftime('%Y%m%d')
today_str_kr = now_kst.strftime('%Y년 %m월 %d일')

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}
    try:
        requests.post(url, data=payload)
        print("📱 [텔레그램 발송 완료]")
    except Exception as e:
        print(f"❌ [발송 에러] {e}")

try:
    print("1️⃣ [수급/가격 분석] 메이저 수급 유입 및 정배열 종목을 찾습니다...")
    df_krx = fdr.StockListing('KRX')
    df_cap_filtered = df_krx[df_krx['Marcap'] >= 200000000000].sort_values(by='Marcap', ascending=False)
    
    chart_passed_stocks = []
    for index, row in df_cap_filtered.head(2000).iterrows():
        code, name = row['Code'], row['Name']
        try:
            market = row['Market']
            yahoo_symbol = f"{code}.KS" if market == "KOSPI" else f"{code}.KQ" if market == "KOSDAQ" else code
            
            df_price = fdr.DataReader(yahoo_symbol, start_210_str, today_date_str)
            if df_price.empty or len(df_price) < 120: continue
                
            df_price['MA5'] = df_price['Close'].rolling(5).mean()
            df_price['MA20'] = df_price['Close'].rolling(20).mean()
            df_price['MA60'] = df_price['Close'].rolling(60).mean()
            df_price['MA120'] = df_price['Close'].rolling(120).mean()
            df_price['Vol_MA20'] = df_price['Volume'].rolling(20).mean()
            
            latest = df_price.iloc[-1]
            
            # 🚨 [조건 완화] 빡빡했던 차트와 거래량 조건을 널널하게 풀었습니다.
            cond_aligned = (latest['Close'] > latest['MA20'] and latest['MA20'] > latest['MA60'])
            cond_price = (latest['Close'] >= 1000)
            cond_vol_base = (latest['Vol_MA20'] >= 100000)
            cond_vol_spike = (latest['Volume'] >= latest['Vol_MA20'] * 1.3) # 2배 -> 1.3배로 완화
            cond_red_candle = (latest['Close'] > latest['Open']) 
            
            if cond_aligned and cond_price and cond_vol_base and cond_vol_spike and cond_red_candle:
                vol_multiple = round(latest['Volume'] / latest['Vol_MA20'], 1)
                chart_passed_stocks.append({
                    'code': code, 'name': name, 'price': int(latest['Close']), 
                    'yahoo_symbol': yahoo_symbol, 'vol_multiple': vol_multiple
                })
        except:
            continue

    print(f"2️⃣ [재무 분석] {len(chart_passed_stocks)}개 종목의 펀더멘털을 검사합니다...")
    fundamental_passed_stocks = []
    for item in chart_passed_stocks:
        try:
            time.sleep(0.5) 
            ticker = yf.Ticker(item['yahoo_symbol'])
            info = ticker.info
            eps = info.get('trailingEps', 0)
            per = info.get('trailingPE', 0)
            if eps is None: eps = 0
            if per is None: per = 0

            # 🚨 [조건 완화] PER 허들을 50에서 100으로 낮췄습니다.
            if eps > 0 and 0 < per <= 100:
                item['per'] = round(per, 2)
                fundamental_passed_stocks.append(item)
        except:
            continue
    final_stocks = fundamental_passed_stocks[:15]

    print(f"3️⃣ [정보 분석] {len(final_stocks)}개 종목의 AI 모멘텀을 평가합니다...")
    dart = OpenDartReader(DART_KEY)
    genai.configure(api_key=GEMINI_KEY)
    
    # 🚨 [불사조 탐색 로직] 구글 정책 변경 대비 자동 생존 코드 장착
    best_model = "gemini-3.5-flash"
    try:
        genai.GenerativeModel(best_model).generate_content("test")
    except:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                try:
                    genai.GenerativeModel(m.name).generate_content("test")
                    best_model = m.name
                    break
                except:
                    continue
    model = genai.GenerativeModel(best_model)

    report_items = []
    for item in final_stocks:
        corp_name = item['name']
        time.sleep(1.5) 
        try:
            dart_reports = dart.list(corp_name, start=recent_3m_str)
            news_list = dart_reports['report_nm'].head(5).tolist() if dart_reports is not None and not dart_reports.empty else ["최근 공시 없음"]
        except:
            news_list = ["공시 수집 에러"]

        prompt = f"기업명: {corp_name}\n최근 공시: {news_list}\n당신은 한국의 퀀트 애널리스트입니다. 공시를 분석해 단기 투자 매력도 점수(1~10점)와 한 줄 요약을 작성하세요. 반드시 아래 형식대로 2줄로만 답하세요.\n모멘텀 스코어: 8점\nAI 요약: 대규모 수주로 상승 모멘텀 강력함."
        try:
            res = model.generate_content(prompt)
            lines = [line.replace('*', '').strip() for line in res.text.strip().split('\n') if line.strip()]
            score_line = next((line for line in lines if "스코어" in line), "모멘텀 스코어: 평가 불가")
            summary_line = next((line for line in lines if "요약" in line), "AI 요약: 내용 없음")
            ai_text = f"{score_line}\n{summary_line}" 
        except:
            ai_text = "AI 분석 지연"
        report_items.append({'name': corp_name, 'price': item['price'], 'per': item['per'], 'vol_mult': item['vol_multiple'], 'ai': ai_text})

    tg_msg = f"📊 [삼박자 퀀트 AI 리포트 v2.0]\n📅 분석 일자: {today_str_kr}\n<i>(💡 AI 생존 모델: {best_model} 장착)</i>\n\n"
    
    if len(report_items) == 0:
        tg_msg += "⚠️ 오늘 장 기준으로 완화된 조건을 만족하는 종목도 포착되지 않았습니다. (강력한 하락장 또는 관망세)"
    else:
        for idx, r in enumerate(report_items):
            tg_msg += f"🔥 [{idx+1}] {r['name']} (거래량 {r['vol_mult']}배 증가)\n▪️ 현재가: {r['price']:,}원 / PER: {r['per']}배\n▪️ {r['ai']}\n\n"
            
    send_telegram_message(tg_msg)

except Exception as e:
    print("❌ 에러 발생:", e)
