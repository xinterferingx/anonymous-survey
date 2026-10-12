import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
import json
import tempfile
import xml.etree.ElementTree as ET
from io import StringIO

KEY_PATH = "serviceAccountKey.json"

try:
    if hasattr(st, "secrets") and "FIREBASE_KEY" in st.secrets:
        firebase_key = st.secrets["FIREBASE_KEY"]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            if isinstance(firebase_key, str):
                f.write(firebase_key)
            else:
                json.dump(firebase_key, f, ensure_ascii=False)
            KEY_PATH = f.name
except Exception:
    pass

if not firebase_admin._apps:
    if not os.path.exists(KEY_PATH):
        st.error("❌ Ошибка: не найден ключ Firebase!\n\n"
                 "Локально: положи serviceAccountKey.json рядом с app.py\n"
                 "В облаке: добавь FIREBASE_KEY in Secrets (Settings → Secrets)")
        st.stop()

    cred = credentials.Certificate(KEY_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.set_page_config(page_title="Отношение к анонимным отзывам", layout="wide")

st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #090a0f 0%, #17051c 50%, #05141c 100%) !important;
        background-attachment: fixed !important;
    }
    
    h1 {
        color: #00ffcc !important;
        text-shadow: 0 0 10px #00ffcc, 0 0 20px #00ffcc;
        font-family: 'Courier New', Courier, monospace;
    }
    h3, p, label, .stMarkdown {
        color: #ff00ff !important;
        text-shadow: 0 0 5px rgba(255, 0, 255, 0.4);
    }
    div[data-testid="stForm"] {
        border: 2px solid #00ffcc !important;
        box-shadow: 0 0 20px #00ffcc, inset 0 0 15px rgba(0, 255, 204, 0.2) !important;
        background-color: rgba(20, 23, 36, 0.75) !important;
        border-radius: 10px !important;
        backdrop-filter: blur(10px);
    }
    button[type="submit"] {
        background-color: transparent !important;
        color: #00ffcc !important;
        border: 2px solid #00ffcc !important;
        box-shadow: 0 0 10px #00ffcc !important;
        font-weight: bold !important;
        transition: 0.3s !important;
        width: 100% !important;
    }
    button[type="submit"]:hover {
        background-color: #00ffcc !important;
        color: #0d0e15 !important;
        box-shadow: 0 0 25px #00ffcc !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Опрос: Отношение к анонимным отзывам в сети")
st.markdown("Исследуем, насколько пользователи доверяют анонимному мнению и как оно влияет на их решения.")

with st.form("review_survey"):
    st.subheader("Заполните анкету")

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        age = st.number_input("Ваш возраст", min_value=14, max_value=80, step=1)
    
    with c2:
        gender = st.selectbox("Пол", ["Мужской", "Женский", "Не указывать"])
    
    with c3:
        credibility = st.slider(
            "Достоверность (1-10):",
            min_value=1, max_value=10, value=5
        )
        
    with c4:
        influence = st.slider(
            "Влияние на выбор (1-10):",
            min_value=1, max_value=10, value=5
        )
        
    with c5:
        moderation = st.selectbox(
            "Нужна ли модерация?",
            ["Да, строгая", "Частично", "Нет, не нужна"]
        )
        
    with c6:
        platforms = st.multiselect(
            "Где чаще читаете?",
            ["Маркетплейсы", "Соцсети", "Сайты отзывов", "Форумы", "Карты", "Нигде"],
            placeholder="Выбрать"
        )

    comment = st.text_area("Дополнительные комментарии (необязательно)")
    submit = st.form_submit_button("Отправить ответ")

if submit:
    if not platforms:
        st.warning("⚠️ Пожалуйста, выберите хотя бы один вариант, где читаете отзывы!")
    else:
        record = {
            "age": int(age),
            "gender": gender,
            "credibility_rating": int(credibility),
            "influence_rating": int(influence),
            "moderation_opinion": moderation,
            "platforms_used": platforms,
            "comment": comment,
            "timestamp": datetime.utcnow()
        }

        try:
            db.collection("anonymous_reviews_responses").add(record)
            st.success("✅ Спасибо! Ваш ответ сохранён.")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Ошибка сохранения: {e}")

st.divider()

if st.checkbox("📊 Показать аналитику (режим преподавателя)"):
    docs = db.collection("anonymous_reviews_responses").stream()
    data = [doc.to_dict() for doc in docs]

    if not data:
        st.info("📭 Пока нет собранных данных.")
    else:
        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        st.subheader("📋 Сводка по данным")
        col1, col2, col3 = st.columns(3)
        col1.metric("Всего ответов", len(df))
        col2.metric("Средний возраст", round(df["age"].mean(), 1))
        col3.metric("Средний уровень влияния", round(df["influence_rating"].mean(), 2))

        st.dataframe(df.head(20), use_container_width=True)

        st.subheader("💾 Экспорт данных")
        col_exp1, col_exp2 = st.columns(2)

        with col_exp1:
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 Скачать CSV",
                data=csv_buffer.getvalue(),
                file_name="reviews_survey_data.csv",
                mime="text/csv",
                use_container_width=True
            )

        with col_exp2:
            def df_to_xml(df):
                root = ET.Element("reviews_survey")
                for _, row in df.iterrows():
                    response = ET.SubElement(root, "response")
                    for col in df.columns:
                        child = ET.SubElement(response, col)
                        val = row[col]
                        if isinstance(val, list):
                            child.text = ", ".join(str(x) for x in val)
                        elif pd.isna(val):
                            child.text = ""
                        else:
                            child.text = str(val)
                return ET.tostring(root, encoding="unicode")

            xml_data = df_to_xml(df)
            st.download_button(
                label="📥 Скачать XML",
                data=xml_data,
                file_name="reviews_survey_data.xml",
                mime="application/xml",
                use_container_width=True
            )

        plotly_template = "plotly_dark"

        st.subheader("📊 Распределение оценок достоверности отзывов")
        fig1 = px.histogram(
            df, x="credibility_rating", nbins=10,
            title="Оценка достоверности анонимных отзывов (1-10)",
            labels={"credibility_rating": "Оценка достоверности", "count": "Количество"},
            color_discrete_sequence=["#00ffcc"],
            template=plotly_template
        )
        st.plotly_chart(fig1, use_container_width=True)

        st.subheader("📈 Возраст респондентов vs Влияние отзывов на выбор")
        fig2 = px.scatter(
            df, x="age", y="influence_rating",
            color="gender", size="credibility_rating",
            title="Зависимость влияния отзывов от возраста",
            labels={"age": "Возраст", "influence_rating": "Уровень влияния (1-10)"},
            template=plotly_template
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("🛡️ Мнение о необходимости модерации")
        fig3 = px.pie(
            df, names="moderation_opinion",
            title="Нужно ли модерировать анонимные отзывы?",
            template=plotly_template,
            color_discrete_sequence=["#00ffcc", "#ff00ff", "#636EFA"]
        )
        st.plotly_chart(fig3, use_container_width=True)

        st.subheader("🌐 Популярные платформы для чтения отзывов")
        all_platforms = []
        for items in df["platforms_used"]:
            all_platforms.extend(items)
        platforms_df = pd.DataFrame({"platform": all_platforms})
        fig4 = px.bar(
            platforms_df["platform"].value_counts().reset_index(),
            x="platform", y="count",
            title="Где пользователи чаще изучают отзывы",
            labels={"platform": "Платформа", "count": "Количество упоминаний"},
            template=plotly_template,
            color_discrete_sequence=["#ff00ff"]
        )
        st.plotly_chart(fig4, use_container_width=True)
