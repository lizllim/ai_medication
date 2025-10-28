import streamlit as st
from PIL import Image
import google.generativeai as genai
from datetime import datetime, timedelta
import json
import io

# 페이지 설정
st.set_page_config(
    page_title="내 약 도우미 💊",
    page_icon="💊",
    layout="wide"
)

# 세션 상태 초기화 (가장 먼저!)
if 'api_key' not in st.session_state:
    st.session_state.api_key = None
if 'medications' not in st.session_state:
    st.session_state.medications = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Gemini API 설정
def init_gemini():
    if st.session_state.api_key:
        genai.configure(api_key=st.session_state.api_key)
        return True
    return False

# 약봉투 분석 함수
def analyze_prescription(image):
    """Gemini Vision으로 약봉투 이미지 분석"""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = """
        이 약봉투 이미지를 분석해서 다음 정보를 JSON 형식으로 추출해주세요:
        
        {
            "medications": [
                {
                    "name": "약 이름",
                    "dosage": "용량 (예: 500mg)",
                    "frequency": "복용 횟수 (예: 1일 3회)",
                    "timing": "복용 시간 (예: 아침, 점심, 저녁 식후 30분)",
                    "duration": "복용 기간 (예: 7일)",
                    "warnings": "주의사항"
                }
            ]
        }
        
        약 이름, 용량, 복용 방법을 최대한 정확하게 읽어주세요.
        만약 이미지가 약봉투가 아니거나 글씨가 보이지 않으면 "분석 불가"라고 응답해주세요.
        """
        
        response = model.generate_content([prompt, image])
        
        # JSON 파싱
        response_text = response.text
        # ```json 제거
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        result = json.loads(response_text.strip())
        return result
    except Exception as e:
        st.error(f"분석 중 오류 발생: {str(e)}")
        return None

# 복용 스케줄 생성
def generate_schedule(medications):
    """약물 정보를 바탕으로 일주일 스케줄 생성"""
    schedule = {}
    
    for med in medications:
        timing = med.get('timing', '').lower()
        frequency = med.get('frequency', '1일 1회')
        
        # 복용 시간 파싱
        times = []
        if '아침' in timing:
            times.append('08:00')
        if '점심' in timing:
            times.append('12:00')
        if '저녁' in timing:
            times.append('18:00')
        if '취침' in timing or '자기 전' in timing:
            times.append('22:00')
        
        # 기본값
        if not times:
            if '3회' in frequency:
                times = ['08:00', '12:00', '18:00']
            elif '2회' in frequency:
                times = ['08:00', '18:00']
            else:
                times = ['08:00']
        
        for day in range(7):
            date = datetime.now() + timedelta(days=day)
            date_str = date.strftime('%Y-%m-%d')
            
            if date_str not in schedule:
                schedule[date_str] = []
            
            for time in times:
                schedule[date_str].append({
                    'medication': med['name'],
                    'time': time,
                    'dosage': med.get('dosage', ''),
                    'taken': False
                })
    
    return schedule

# 약물 상호작용 체크
def check_drug_interactions(medications):
    """Gemini로 약물 상호작용 확인"""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        med_list = [med['name'] for med in medications]
        
        prompt = f"""
        다음 약물들을 함께 복용할 때 주의해야 할 상호작용이나 부작용이 있는지 알려주세요:
        
        {', '.join(med_list)}
        
        다음 형식으로 답변해주세요:
        
        1. 심각한 상호작용: (있다면 설명, 없으면 "없음")
        2. 주의가 필요한 조합: (있다면 설명, 없으면 "없음")
        3. 일반적인 복용 권장사항
        4. 피해야 할 음식이나 음료
        
        의학적으로 정확하고 신중하게 답변해주세요.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"상호작용 체크 중 오류 발생: {str(e)}"

# 챗봇 응답
def chatbot_response(user_message, medications_context):
    """약 관련 질문에 대한 챗봇 응답"""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        context = f"현재 복용 중인 약물: {', '.join([med['name'] for med in medications_context])}"
        
        prompt = f"""
        당신은 친절한 약사 도우미입니다. 환자의 약 복용 관련 질문에 답변해주세요.
        
        {context}
        
        환자 질문: {user_message}
        
        주의사항:
        - 의학적으로 정확하고 신중하게 답변하세요
        - 심각한 증상이나 응급 상황에는 즉시 의사/약사 상담을 권유하세요
        - 복용 중인 약물과 관련된 정보를 우선적으로 제공하세요
        - 친절하고 이해하기 쉽게 설명하세요
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"응답 생성 중 오류 발생: {str(e)}"

# ===== 메인 UI =====

# API 키 입력 (사이드바)
with st.sidebar:
    st.title("⚙️ 설정")
    api_key_input = st.text_input(
        "Gemini API 키", 
        type="password",
        value=st.session_state.api_key if st.session_state.api_key else "",
        help="https://makersuite.google.com/app/apikey 에서 발급받으세요"
    )
    
    if api_key_input:
        st.session_state.api_key = api_key_input
        if init_gemini():
            st.success("✅ API 연결 완료")
    
    st.divider()
    
    # 메뉴
    menu = st.radio(
        "메뉴 선택",
        ["📸 약 등록", "📅 복용 스케줄", "⚠️ 주의사항", "💬 챗봇 상담"],
        label_visibility="collapsed"
    )

# API 키 확인
if not st.session_state.api_key:
    st.warning("👈 왼쪽 사이드바에서 Gemini API 키를 입력해주세요")
    st.info("API 키는 https://makersuite.google.com/app/apikey 에서 무료로 발급받을 수 있습니다")
    st.stop()

# ===== 페이지별 콘텐츠 =====

if menu == "📸 약 등록":
    st.title("💊 약봉투 등록하기")
    st.write("약봉투 사진을 찍어서 올려주세요. AI가 자동으로 약 정보를 분석합니다.")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "약봉투 사진 업로드",
            type=['png', 'jpg', 'jpeg'],
            help="약 이름과 복용 방법이 선명하게 보이도록 촬영해주세요"
        )
        
        if uploaded_file:
            image = Image.open(uploaded_file)
            st.image(image, caption="업로드된 약봉투", use_container_width=True)
            
            if st.button("🔍 약 정보 분석하기", type="primary", use_container_width=True):
                with st.spinner("AI가 약봉투를 분석하고 있습니다..."):
                    result = analyze_prescription(image)
                    
                    if result and 'medications' in result:
                        st.session_state.medications = result['medications']
                        st.success("✅ 분석 완료!")
                        st.balloons()
                    else:
                        st.error("약봉투를 분석할 수 없습니다. 더 선명한 사진으로 다시 시도해주세요.")
    
    with col2:
        if st.session_state.medications:
            st.subheader("📋 등록된 약물")
            
            for i, med in enumerate(st.session_state.medications):
                with st.expander(f"💊 {med['name']}", expanded=True):
                    st.write(f"**용량:** {med.get('dosage', '정보 없음')}")
                    st.write(f"**복용 횟수:** {med.get('frequency', '정보 없음')}")
                    st.write(f"**복용 시간:** {med.get('timing', '정보 없음')}")
                    st.write(f"**복용 기간:** {med.get('duration', '정보 없음')}")
                    if med.get('warnings'):
                        st.warning(f"⚠️ {med['warnings']}")
            
            if st.button("🗑️ 전체 삭제", use_container_width=True):
                st.session_state.medications = []
                st.rerun()

elif menu == "📅 복용 스케줄":
    st.title("📅 내 복약 스케줄")
    
    if not st.session_state.medications:
        st.info("먼저 '약 등록' 메뉴에서 약을 등록해주세요.")
    else:
        schedule = generate_schedule(st.session_state.medications)
        
        # 날짜별 스케줄 표시
        for date_str in sorted(schedule.keys())[:7]:  # 일주일치만
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            day_name = ['월', '화', '수', '목', '금', '토', '일'][date_obj.weekday()]
            
            st.subheader(f"{date_obj.strftime('%m월 %d일')} ({day_name})")
            
            schedule_items = sorted(schedule[date_str], key=lambda x: x['time'])
            
            cols = st.columns(len(schedule_items) if schedule_items else 1)
            
            for idx, item in enumerate(schedule_items):
                with cols[idx]:
                    with st.container(border=True):
                        st.write(f"**⏰ {item['time']}**")
                        st.write(f"💊 {item['medication']}")
                        if item['dosage']:
                            st.caption(item['dosage'])
                        
                        # 복용 완료 체크박스
                        checked = st.checkbox(
                            "복용 완료",
                            key=f"{date_str}_{item['time']}_{idx}",
                            value=item['taken']
                        )
            
            st.divider()
        
        # 알림 설정
        st.subheader("🔔 알림 설정")
        st.info("💡 실제 앱에서는 여기서 푸시 알림이나 카카오톡 알림을 설정할 수 있습니다.")
        
        notification_times = st.multiselect(
            "알림 받을 시간 선택",
            ["08:00 (아침)", "12:00 (점심)", "18:00 (저녁)", "22:00 (취침 전)"],
            default=["08:00 (아침)", "18:00 (저녁)"]
        )

elif menu == "⚠️ 주의사항":
    st.title("⚠️ 복용 주의사항 및 상호작용")
    
    if not st.session_state.medications:
        st.info("먼저 '약 등록' 메뉴에서 약을 등록해주세요.")
    else:
        st.subheader("💊 현재 복용 중인 약물")
        
        cols = st.columns(len(st.session_state.medications))
        for idx, med in enumerate(st.session_state.medications):
            with cols[idx]:
                st.info(f"**{med['name']}**\n\n{med.get('dosage', '')}")
        
        st.divider()
        
        if st.button("🔍 약물 상호작용 확인하기", type="primary", use_container_width=True):
            with st.spinner("AI가 약물 상호작용을 분석하고 있습니다..."):
                interactions = check_drug_interactions(st.session_state.medications)
                
                st.subheader("📊 분석 결과")
                st.write(interactions)
        
        st.divider()
        
        # 개별 약물 주의사항
        st.subheader("📌 개별 약물 주의사항")
        for med in st.session_state.medications:
            with st.expander(f"💊 {med['name']}"):
                if med.get('warnings'):
                    st.warning(med['warnings'])
                else:
                    st.info("별도의 주의사항이 기재되지 않았습니다.")

elif menu == "💬 챗봇 상담":
    st.title("💬 약 관련 질문하기")
    
    if not st.session_state.medications:
        st.info("먼저 '약 등록' 메뉴에서 약을 등록하면 더 정확한 답변을 받을 수 있습니다.")
    
    st.caption("약 복용과 관련된 궁금한 점을 물어보세요. (예: 이 약은 식후에 먹어야 하나요? 술과 함께 복용해도 되나요?)")
    
    # 채팅 기록 표시
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # 사용자 입력
    if user_input := st.chat_input("질문을 입력하세요..."):
        # 사용자 메시지 표시
        with st.chat_message("user"):
            st.write(user_input)
        
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # AI 응답 생성
        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                response = chatbot_response(user_input, st.session_state.medications)
                st.write(response)
        
        st.session_state.chat_history.append({"role": "assistant", "content": response})
    
    # 채팅 기록 삭제
    if st.session_state.chat_history:
        if st.button("🗑️ 채팅 기록 삭제"):
            st.session_state.chat_history = []
            st.rerun()

# Footer
st.divider()
st.caption("⚠️ 이 앱은 약 복용 보조 도구입니다. 의학적 조언이 필요한 경우 반드시 의사나 약사와 상담하세요.")
