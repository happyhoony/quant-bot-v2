import requests
import xml.etree.ElementTree as ET
import google.generativeai as genai
import os
from datetime import datetime, timedelta, timezone
import time

# 1. API 키 셋업
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TG_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST)
today_str = now_kst.strftime('%Y년 %m월 %d일')

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'HTML'})

try:
    rss_url = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"
    res = requests.get(rss_url)
    root = ET.fromstring(res.text)
    
    news_titles = []
    for item in root.findall('.//item')[:5]:
        news_titles.append(item.find('title').text)

    # API 키가 깃허브에 잘 연결되었는지 확인
    if not GEMINI_KEY:
        send_telegram_message("❌ 깃허브에 제미나이 API 키(GEMINI_API_KEY)가 제대로 입력되지 않았습니다!")
        exit()

    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    tg_msg = f"🌅 <b>[장전 모닝 뉴스 브리핑]</b>\n📅 {today_str}\n\n"

    for idx, title in enumerate(news_titles):
        time.sleep(3)
        prompt = (
            f"당신은 주식 애널리스트입니다.\n"
            f"뉴스: '{title}'\n"
            f"이 뉴스가 한국 증시에 미치는 영향과 수혜주를 분석해주세요.\n"
            f"반드시 아래 형식으로만 2줄로 답하세요.\n\n"
            f"시장 의미: (여기에 내용)\n"
            f"관련주: (여기에 종목명 2~3개)"
        )
        
        try:
            ai_res = model.generate_content(prompt)
            raw_text = ai_res.text.replace('*', '').replace('"', '').replace("'", "").strip()
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            
            meaning = "시장 의미: 내용 요약 불가"
            stocks = "관련주: 관련 종목 없음"
            
            for line in lines:
                if line.startswith("시장 의미:") or "의미:" in line or "시장 의미" in line:
                    meaning = line
                elif line.startswith("관련주:") or "관련주" in line or "종목" in line:
                    stocks = line
            
            tg_msg += f"📰 <b>{idx+1}. {title}</b>\n💡 {meaning}\n🎯 {stocks}\n\n"
            
        except Exception as e:
            # 🚨 핵심: 에러의 '진짜 원인'을 텔레그램으로 쏴줍니다!
            error_reason = str(e)[:150]
            tg_msg += f"📰 <b>{idx+1}. {title}</b>\n⚠️ 에러 발생: {error_reason}\n\n"

    tg_msg += "☕ 오늘도 성공적인 투자를 기원합니다!"
    send_telegram_message(tg_msg)

except Exception as e:
    send_telegram_message(f"🚨 시스템 전체 에러 발생: {e}")
