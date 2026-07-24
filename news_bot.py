import requests
import xml.etree.ElementTree as ET
import google.generativeai as genai
import os
from datetime import datetime, timedelta, timezone
import time

# ==========================================
# 1. API 키 및 기본 셋업
# ==========================================
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
TG_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TG_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 한국 시간(KST) 설정
KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST)
today_str = now_kst.strftime('%Y년 %m월 %d일')

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'HTML'})

try:
    # ==========================================
    # 2. 구글 뉴스(경제 섹션) 헤드라인 5개 수집
    # ==========================================
    rss_url = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"
    res = requests.get(rss_url)
    root = ET.fromstring(res.text)
    
    news_titles = []
    for item in root.findall('.//item')[:5]:
        news_titles.append(item.find('title').text)

    # API 키 누락 방어막
    if not GEMINI_KEY:
        send_telegram_message("❌ 깃허브에 제미나이 API 키(GEMINI_API_KEY)가 입력되지 않았습니다.")
        exit()

    genai.configure(api_key=GEMINI_KEY)

    # ==========================================
    # 3. 🚨 불사조 탐색 로직 (구글 정책 변경 대비)
    # ==========================================
    best_model = "gemini-3.5-flash" # 1순위 타겟 모델
    
    try:
        # 1순위 모델이 살아있는지 가벼운 질문("test")으로 찔러보기
        genai.GenerativeModel(best_model).generate_content("test")
    except:
        # 실패 시, 사용 가능한 모든 모델 명단을 가져와서 하나씩 찔러보기
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                try:
                    genai.GenerativeModel(m.name).generate_content("test")
                    best_model = m.name # 정상 응답한 모델의 이름으로 갱신!
                    break
                except:
                    continue
                    
    # 최종 생존이 확인된 가장 강력한 모델 장착
    model = genai.GenerativeModel(best_model)
    
    # ==========================================
    # 4. 뉴스 분석 및 텔레그램 메시지 조립
    # ==========================================
    tg_msg = f"🌅 <b>[장전 모닝 뉴스 브리핑]</b>\n📅 {today_str}\n<i>(💡 AI 생존 모델: {best_model} 출격!)</i>\n\n"

    for idx, title in enumerate(news_titles):
        # 🚨 구글 서버 과부하(디도스 의심 차단)를 막기 위한 3초 대기
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
            
            # AI가 전쟁/폭력 등 민감한 기사라며 답변을 거부했을 때의 방어막
            if not ai_res.parts:
                tg_msg += f"📰 <b>{idx+1}. {title}</b>\n💡 시장 의미: AI 민감어 필터링 (분석 제한)\n🎯 관련주: 개별 확인 필요\n\n"
                continue

            # 텍스트 깔끔하게 정제 (별표, 따옴표 제거)
            raw_text = ai_res.text.replace('*', '').replace('"', '').replace("'", "").strip()
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            
            meaning = "시장 의미: 내용 요약 불가"
            stocks = "관련주: 관련 종목 없음"
            
            # 정답 라인 추출
            for line in lines:
                if line.startswith("시장 의미:") or "의미:" in line or "시장 의미" in line:
                    meaning = line
                elif line.startswith("관련주:") or "관련주" in line or "종목" in line:
                    stocks = line
            
            tg_msg += f"📰 <b>{idx+1}. {title}</b>\n💡 {meaning}\n🎯 {stocks}\n\n"
            
        except Exception as e:
            # 낱개 뉴스 분석 실패 시 이유를 텔레그램에 기록
            error_reason = str(e)[:150]
            tg_msg += f"📰 <b>{idx+1}. {title}</b>\n⚠️ 에러 발생: {error_reason}\n\n"

    tg_msg += "☕ 오늘도 성공적인 투자를 기원합니다!"
    
    # ==========================================
    # 5. 최종 텔레그램 발송
    # ==========================================
    send_telegram_message(tg_msg)

except Exception as e:
    # 전체 시스템 붕괴 시 구조 신호 발송
    send_telegram_message(f"🚨 시스템 전체 에러 발생: {e}")
