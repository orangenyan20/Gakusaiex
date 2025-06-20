import streamlit as st
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
import os
import io
from PIL import Image, ImageDraw, ImageFont

EMAIL_FROM = st.secrets["email_from"]
APP_PASSWORD = st.secrets["app_password"]
PASSWORD = st.secrets["admin_password"]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
BASE_IMAGE = "template.png"
LOG_FILE = "guest_tickets.csv"
ALL_LOG_FILE = "guest_tickets_all.csv"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load_log():
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        if "整理券番号" in df.columns and not df["整理券番号"].isnull().all():
            max_num = pd.to_numeric(df["整理券番号"], errors='coerce').max()
            next_num = int(max_num) + 1 if not pd.isna(max_num) else 1
        else:
            next_num = 1
        return df, next_num
    else:
        df = pd.DataFrame(columns=["整理券番号", "氏名", "メール"])
        return df, 1


if "next_number" not in st.session_state:
    df, next_number = load_log()
    st.session_state.df = df
    st.session_state.next_number = next_number
else:
    df = st.session_state.df
    next_number = st.session_state.next_number

st.title("🎫 学外ゲスト 整理券発行アプリ")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pw = st.text_input("パスワードを入力してください", type="password")
    if pw == PASSWORD:
        st.session_state.authenticated = True
        st.success("ログイン成功！")
    else:
        st.stop()

st.subheader("🎟 整理券情報入力（学外ゲスト用）")

with st.form("guest_ticket_form"):
    name = st.text_input("氏名")
    email_local = st.text_input("メールアドレスの前半部分（例: example）")
    domain_option = st.selectbox("ドメインを選んでください", ["gmail.com", "yahoo.co.jp", "icloud.com", "その他"])
    custom_domain = ""
    if domain_option == "その他":
        custom_domain = st.text_input("その他のドメインを入力してください（例: example.com）")
    skip_email = st.checkbox("メールを送信せず紙で配布する")
    submitted = st.form_submit_button("整理券を発行")

if submitted:
    email = "紙" if skip_email else f"{email_local}@{custom_domain if domain_option == 'その他' else domain_option}"

    if not name.strip():
        st.error("氏名を入力してください")
    elif email != "紙" and email in df["メール"].values:
        st.warning("このメールにはすでに整理券が発行されています")
    else:
        try:
            image = Image.open(BASE_IMAGE).convert("RGB")
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(FONT_PATH, 36)
            draw.text((50, 60), f"name: {name}", font=font, fill="black")
            draw.text((50, 130), f"number: {next_number}", font=font, fill="black")
            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            if not skip_email:
                msg = MIMEMultipart()
                msg["From"] = EMAIL_FROM
                msg["To"] = email
                msg["Subject"] = "【学祭】アーティストライブ 整理券のご案内"
                body = f"""{name} さん\n\n学祭アーティストライブの整理券を発行しました。\n整理券番号は「{next_number}」です。\n当日はこの添付画像を提示してください。"""
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

        except Exception as e:
            st.error(f"処理失敗: {e}")

st.subheader("📋 整理券ログ")

if st.checkbox("ログを表示する"):
    st.dataframe(df)

if not df.empty:
    txt_buffer = io.BytesIO()
    df.to_csv(txt_buffer, sep='\t', index=False, encoding="utf-8")
    txt_buffer.seek(0)
    st.download_button(
        label="📥 整理券ログをダウンロード（タブ区切り）",
        data=txt_buffer,
        file_name="ゲスト整理券ログ.txt",
        mime="text/plain"
    )

if os.path.exists(ALL_LOG_FILE):
    df_all = pd.read_csv(ALL_LOG_FILE)
    st.subheader("📚 全体ログ（リセットされずに保存され続ける）")
    if st.checkbox("全体ログを表示する"):
        st.dataframe(df_all)
    if not df_all.empty:
        txt_all_buffer = io.BytesIO()
        df_all.to_csv(txt_all_buffer, sep='\t', index=False, encoding="utf-8")
        txt_all_buffer.seek(0)
        st.download_button(
            label="📥 全体ログをダウンロード（タブ区切り）",
            data=txt_all_buffer,
            file_name="ゲスト整理券全体ログ.txt",
            mime="text/plain"
        )
