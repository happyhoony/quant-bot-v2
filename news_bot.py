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
    # 2. 구글 뉴스(경제 섹션) RSS 가져오기
    rss_url = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"
    res = requests.get(rss_url)
    root = ET.fromstring(res.text)
    
    news_titles = []
    for item in root.findall('.//item')[:5]:
        title = item.find('title').text
        news_titles.append(title)

    # 3. 제미나이 AI 설정
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

    tg_msg = f"🌅 <b>[장전 모닝 뉴스 브리핑]</b>\n📅 {today_str}\n\n"

    # 4. 각 뉴스마다 AI 분석 요청
    for idx, title in enumerate(news_titles):
        time.sleep(1)
        
        # 들여쓰기 에러를 원천 차단하기 위해 괄호와 \n(줄바꿈) 사용
        prompt = (
            f"당신은 여의도 최고의 퀀트 애널리스트입니다.\n"
            f"뉴스 헤드라인: '{title}'\n"
            f"위 뉴스가 한국 주식시장에 미치는 영향과 수혜주를 분석해주세요.\n\n"
            f"[규칙]\n"
            f"1. 영어, 괄호([ ]), 부가 설명은 절대 쓰지 마세요.\n"
            f"2. 반드시 아래 2줄 형식에 맞춰서 한국어로만 대답하세요.\n\n"
            f"시장 의미: (여기에 뉴스 요약 및 시장 영향 작성)\n"
            f"관련주: (여기에 수혜 종목명 2~3개 작성)"
        )
        
        try:
            ai_res = model.generate_content(prompt)
            raw_text = ai_res.text.replace('*', '').replace('"', '').replace("'", "").strip()
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            
            meaning = next((line for line in lines if "의미" in line), "시장 의미: 분석 불가")
            stocks = next((line for line in lines if "관련주" in line or "종목" in line), "관련주: 파악 불가")
            
            tg_msg += f"📰 <b>{idx+1}. {title}</b>\n"
            tg_msg += f"💡 {meaning}\n"
            tg_msg += f"🎯 {stocks}\n\n"
        except Exception as e:
            tg_msg += f"📰 <b>{idx+1}. {title}</b>\n⚠️ AI 분석 지연\n\n"

    tg_msg += "☕ 오늘도 성공적인 투자를 기원합니다!"
    
    # 5. 텔레그램 발송
    send_telegram_message(tg_msg)

except Exception as e:
    print("에러 발생:", e)
