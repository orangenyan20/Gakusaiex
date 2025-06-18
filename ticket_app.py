import streamlit as st
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from PIL import Image, ImageDraw, ImageFont
import os
import io
import re

# ------------------------
# 設定（Secretsから取得）
# ------------------------
EMAIL_FROM = st.secrets["email_from"]
APP_PASSWORD = st.secrets["app_password"]
PASSWORD = st.secrets["admin_password"]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
BASE_IMAGE = "template.png"
LOG_FILE = "tickets.csv"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ------------------------
# ログ読み込み or 初期化
# ------------------------
if os.path.exists(LOG_FILE):
    df = pd.read_csv(LOG_FILE)
    next_number = df["整理券番号"].max() + 1
else:
    df = pd.DataFrame(columns=["整理券番号", "学籍番号", "氏名", "メール"])
    next_number = 1

# ------------------------
# ログイン画面
# ------------------------
st.title("🎫 学祭アーティストライブ 整理券発行アプリ")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pw = st.text_input("パスワードを入力してください", type="password")
    if pw == PASSWORD:
        st.session_state.authenticated = True
        st.success("ログイン成功！")
    else:
        st.stop()

# ------------------------
# 入力フォーム
# ------------------------
st.subheader("🎟 整理券情報入力")

with st.form("ticket_form"):
    gakuseki = st.text_input("学籍番号（10桁）", max_chars=10)
    name = st.text_input("氏名")
    email_prefix = st.text_input("学内メールID（英数字7桁）", max_chars=7)
    submitted = st.form_submit_button("整理券を発行して送信")

if submitted:
    email = f"{email_prefix}@yamaguchi-u.ac.jp"

    if len(gakuseki) != 10 or not gakuseki.isdigit():
        st.error("学籍番号は10桁の数字で入力してください")
    elif not re.fullmatch(r"[A-Za-z0-9]{7}", email_prefix):
        st.error("メールIDは英数字7桁で入力してください")
    elif email in df["メール"].values:
        st.warning("このメールにはすでに整理券が発行されています")
    else:
        try:
            # 画像生成
            image = Image.open(BASE_IMAGE).convert("RGB")
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(FONT_PATH, 40)
            draw.text((50, 50), f"整理券番号: {next_number}", font=font, fill="black")
            draw.text((50, 120), f"氏名: {name}", font=font, fill="black")
            draw.text((50, 190), f"学籍番号: {gakuseki}", font=font, fill="black")

            output_path = f"整理券_{next_number}.png"
            image.save(output_path)

            # メール作成
            msg = MIMEMultipart()
            msg["From"] = EMAIL_FROM
            msg["To"] = email
            msg["Subject"] = "【テストメール】【学祭】アーティストライブ 整理券のご案内"
            body = f"""{name} さん

学祭アーティストライブの整理券を発行しました。
整理券番号は「{next_number}」です。

当日はこの画像を提示してください。
"""
            msg.attach(MIMEText(body, "plain"))

            with open(output_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment; filename=整理券.png")
                msg.attach(part)

            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(EMAIL_FROM, APP_PASSWORD)
                server.send_message(msg)

            # ログ保存
            new_row = pd.DataFrame([[next_number, gakuseki, name, email]], columns=df.columns)
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(LOG_FILE, index=False)

            next_number += 1
            st.success("整理券を送信しました🎉")

        except Exception as e:
            st.error(f"送信失敗: {e}")

# ------------------------
# CSV確認・ダウンロード
# ------------------------
st.subheader("📋 整理券ログ")

if st.checkbox("ログを表示する"):
    st.dataframe(df)

if not df.empty:
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="📥 CSVをダウンロード",
        data=csv_buffer.getvalue(),
        file_name="整理券ログ.csv",
        mime="text/csv"
    )
