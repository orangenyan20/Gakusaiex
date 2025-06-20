import streamlit as st
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
import os
import io
import re
from PIL import Image, ImageDraw, ImageFont

EMAIL_FROM = st.secrets["email_from"]
APP_PASSWORD = st.secrets["app_password"]
PASSWORD = st.secrets["admin_password"]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
BASE_IMAGE = "template.png"
LOG_FILE = "tickets.csv"
ALL_LOG_FILE = "tickets_all.csv"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def load_log():
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        if "整理券番号" in df.columns and not df["整理券番号"].isnull().all():
            max_num = pd.to_numeric(df["整理券番号"], errors='coerce').max()
            next_num = int(max_num) + 1 if not pd.isna(max_num) else 1
            return df, next_num
        else:
            return pd.DataFrame(columns=["整理券番号", "氏名", "メール"]), 1
    else:
        return pd.DataFrame(columns=["整理券番号", "氏名", "メール"]), 1

if "next_number" not in st.session_state:
    df, next_number = load_log()
    st.session_state.df = df
    st.session_state.next_number = next_number
else:
    df = st.session_state.df
    next_number = st.session_state.next_number

st.title("🎫 学祭アーティストライブ 学外ゲスト整理券発行アプリ")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pw = st.text_input("パスワードを入力してください", type="password")
    if pw == PASSWORD:
        st.session_state.authenticated = True
        st.success("ログイン成功！")
    else:
        st.stop()

st.subheader("🎟 整理券発行フォーム（学外用）")

with st.form("guest_ticket_form"):
    name = st.text_input("氏名（任意でもOK）")
    email_prefix = st.text_input("メールアドレス（@より前）", placeholder="例: guest123")

    domain_list = ["gmail.com", "icloud.com", "yahoo.co.jp", "hotmail.com", "outlook.jp", "その他"]
    domain_choice = st.selectbox("ドメインを選んでください", domain_list)
    domain_custom = ""
    if domain_choice == "その他":
        domain_custom = st.text_input("ドメインを直接入力（例: example.com）")

    skip = st.checkbox("📄 メールアドレスを持っていないため、紙で配布する")
    submitted = st.form_submit_button("整理券を発行")

if submitted:
    if skip:
        email = "紙配布"
    else:
        domain = domain_custom if domain_choice == "その他" else domain_choice
        email = f"{email_prefix}@{domain}"

    if not skip and not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email):
        st.error("メールアドレスが正しくありません")
    elif email in df["メール"].values:
        st.warning("このメールにはすでに整理券が発行されています")
    else:
        try:
            image = Image.open(BASE_IMAGE).convert("RGB")
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(FONT_PATH, 36)
            draw.text((50, 60), f"number: {next_number}", font=font, fill="black")

            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            if not skip:
                msg = MIMEMultipart()
                msg["From"] = EMAIL_FROM
                msg["To"] = email
                msg["Subject"] = "【学祭】アーティストライブ 整理券のご案内"
                body = f"""{name or 'お客様'} さん\n\n学祭アーティストライブの整理券を発行しました。\n整理券番号は「{next_number}」です。\n当日はこの添付画像を提示してください。"""
                msg.attach(MIMEText(body, "plain"))
                image_part = MIMEImage(img_buffer.read(), _subtype="png", name="整理券.png")
                image_part.add_header("Content-Disposition", "attachment", filename="整理券.png")
                msg.attach(image_part)

                with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                    server.login(EMAIL_FROM, APP_PASSWORD)
                    server.send_message(msg)

            new_row = pd.DataFrame([[next_number, name, email]], columns=df.columns)
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(LOG_FILE, index=False)

            if os.path.exists(ALL_LOG_FILE):
                df_all = pd.read_csv(ALL_LOG_FILE)
                df_all = pd.concat([df_all, new_row], ignore_index=True)
            else:
                df_all = new_row
            df_all.to_csv(ALL_LOG_FILE, index=False)

            st.session_state.df = df
            st.session_state.next_number += 1

            st.success(f"整理券番号 {next_number} を発行しました🎉")
            if skip:
                st.info("この方にはメール送信せず、紙で配布してください。")

        except Exception as e:
            st.error(f"送信失敗: {e}")
