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
    for item in root.findall('.//item')[:5]: # 가장 중요한 상위 5개 뉴스
        title = item.find('title').text
        news_titles.append(title)

    # 3. 제미나이 AI 설정
    genai.configure(api_key=GEMINI_KEY)
    try:
        model = genai.GenerativeModel('gemma-4-26b-a4b-it')
    except:
        model = genai.GenerativeModel('gemini-1.5-flash')

    tg_msg = f"🌅 [장전 모닝 뉴스 브리핑]\n📅 {today_str}\n\n"

    # 4. 각 뉴스마다 AI 분석 요청
    for idx, title in enumerate(news_titles):
        time.sleep(1) # AI 과부하 방지
        prompt = f"""
        오늘 아침 주요 경제 뉴스 헤드라인입니다: "{title}"
        이 뉴스가 한국 주식시장에 미치는 의미와, 이로 인해 수혜를 볼 수 있는 관련주(종목명) 2~3개를 분석해 주세요.
        반드시 아래 형식에 맞춰 2줄로만 간결하게 답변하세요.
        시장 의미: (어떤 테마/섹터에 호재인지 요약)
        관련주: (관련 기업명 나열)
        """
        try:
            ai_res = model.generate_content(prompt)
            # 불필요한 특수문자 제거 및 정리
            lines = [line.replace('*', '').strip() for line in ai_res.text.strip().split('\n') if line.strip()]
            meaning = next((line for line in lines if "의미" in line), "시장 의미: 분석 불가")
            stocks = next((line for line in lines if "관련주" in line), "관련주: 파악 불가")
            
            tg_msg += f"📰 {idx+1}. {title}\n"
            tg_msg += f"💡 {meaning}\n"
            tg_msg += f"🎯 {stocks}\n\n"
        except Exception as e:
            tg_msg += f"📰 {idx+1}. {title}\n⚠️ AI 분석 지연\n\n"

    tg_msg += "☕ 오늘도 성공적인 투자를 기원합니다!"
    
    # 5. 텔레그램 발송
    send_telegram_message(tg_msg)

except Exception as e:
    print("에러 발생:", e)
