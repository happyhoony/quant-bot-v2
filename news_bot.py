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

    if not GEMINI_KEY:
        send_telegram_message("❌ 깃허브에 제미나이 API 키(GEMINI_API_KEY)가 제대로 입력되지 않았습니다!")
        exit()

    genai.configure(api_key=GEMINI_KEY)

    # 🚨 [핵심 해결책] 구글 서버에 '내가 쓸 수 있는 모델'을 물어보고 자동 선택!
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
    
    if not available_models:
        send_telegram_message("❌ 사용 가능한 Gemini 모델을 찾을 수 없습니다. API 키 문제일 수 있습니다.")
        exit()

    # 사용 가능한 모델 중 가장 빠르고 똑똑한 것(flash나 pro)을 자동 채택
    best_model = available_models[0]
    for name in available_models:
        if 'flash' in name.lower():
            best_model = name
            break
        elif 'pro' in name.lower():
            best_model = name
            
    model = genai.GenerativeModel(best_model)
    
    # 텔레그램 메시지 상단에 '어떤 모델을 찾아냈는지' 표시해줍니다!
    tg_msg = f"🌅 [장전 모닝 뉴스 브리핑]\n📅 {today_str}\n(💡 AI 모델 자동 매칭: {best_model.split('/')[-1]})\n\n"

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
            
            if not ai_res.parts:
                tg_msg += f"📰 {idx+1}. {title}\n💡 시장 의미: AI 민감어 필터링\n🎯 관련주: 개별 확인 필요\n\n"
                continue

            raw_text = ai_res.text.replace('*', '').replace('"', '').replace("'", "").strip()
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            
            meaning = "시장 의미: 내용 요약 불가"
            stocks = "관련주: 관련 종목 없음"
            
            for line in lines:
                if line.startswith("시장 의미:") or "의미:" in line or "시장 의미" in line:
                    meaning = line
                elif line.startswith("관련주:") or "관련주" in line or "종목" in line:
                    stocks = line
            
            tg_msg += f"📰 {idx+1}. {title}\n💡 {meaning}\n🎯 {stocks}\n\n"
            
        except Exception as e:
            error_reason = str(e)[:150]
            tg_msg += f"📰 {idx+1}. {title}\n⚠️ 에러 발생: {error_reason}\n\n"

    tg_msg += "☕ 오늘도 성공적인 투자를 기원합니다!"
    send_telegram_message(tg_msg)

except Exception as e:
    send_telegram_message(f"🚨 시스템 전체 에러 발생: {e}")
