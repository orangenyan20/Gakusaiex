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
from datetime import datetime

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
ALL_LOG_FILE = "tickets_all.csv"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ------------------------
# ログ読み込み or 初期化
# ------------------------
def load_log():
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        if "整理券番号" in df.columns and not df["整理券番号"].isnull().all():
            max_num = pd.to_numeric(df["整理券番号"], errors='coerce').max()
            if pd.isna(max_num):
                next_num = 1
            else:
                next_num = int(max_num) + 1
        else:
            next_num = 1
        return df, next_num
    else:
        df = pd.DataFrame(columns=["整理券番号", "学籍番号", "氏名", "メール"])
        return df, 1

def save_log(df):
    df.to_csv(LOG_FILE, index=False)
    if os.path.exists(ALL_LOG_FILE):
        all_df = pd.read_csv(ALL_LOG_FILE)
        all_df = pd.concat([all_df, df], ignore_index=True)
    else:
        all_df = df.copy()
    all_df.to_csv(ALL_LOG_FILE, index=False)

# ロード
if "start_number" not in st.session_state:
    df, next_number = load_log()
    st.session_state.df = df
    st.session_state.next_number = next_number

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
# メンテナンス機能
# ------------------------
st.subheader("🛠 メンテナンス")
with st.expander("ログと整理券番号のメンテナンス"):
    with st.form("maintenance_form"):
        mode = st.radio("操作を選択してください", ["整理券番号を任意の番号から再開", "ログと整理券番号をリセット"])
        if mode == "整理券番号を任意の番号から再開":
            new_start = st.number_input("再開する整理券番号を入力してください", min_value=1, step=1)
        pw_check = st.text_input("パスワードを再入力してください", type="password")
        confirm = st.checkbox("本当に実行してよろしいですか？")
        submit = st.form_submit_button("実行")

    if submit:
        if pw_check != PASSWORD:
            st.error("パスワードが間違っています")
        elif not confirm:
            st.warning("確認にチェックが入っていません")
        else:
            if mode == "ログと整理券番号をリセット":
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
                st.session_state.df = pd.DataFrame(columns=["整理券番号", "学籍番号", "氏名", "メール"])
                st.session_state.next_number = 1
                st.success("ログと整理券番号をリセットしました")
            else:
                st.session_state.next_number = int(new_start)
                st.success(f"次の整理券番号を {new_start} に設定しました")

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
    elif not name.strip():
        st.error("氏名を入力してください")
    elif email in st.session_state.df["メール"].values:
        st.warning("このメールにはすでに整理券が発行されています")
    else:
        try:
            image = Image.open(BASE_IMAGE).convert("RGB")
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(FONT_PATH, 36)
            draw.text((50, 60), f"id: {gakuseki}", font=font, fill="black")
            draw.text((50, 130), f"number: {st.session_state.next_number}", font=font, fill="black")

            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            msg = MIMEMultipart()
            msg["From"] = EMAIL_FROM
            msg["To"] = email
            msg["Subject"] = "アーティストライブ 整理券発行のお知らせ"
            body = f"""{name} さん\n\n学祭アーティストライブの整理券を発行しました。\n整理券番号は「{st.session_state.next_number}」です。\n\n当日はこの添付画像を提示してください。\n"""
            msg.attach(MIMEText(body, "plain"))

            image_part = MIMEImage(img_buffer.read(), _subtype="png")
            image_part.add_header("Content-Disposition", "attachment", filename="整理券.png")
            msg.attach(image_part)

            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(EMAIL_FROM, APP_PASSWORD)
                server.send_message(msg)

            new_row = pd.DataFrame([[st.session_state.next_number, gakuseki, name, email]], columns=st.session_state.df.columns)
            st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
            save_log(new_row)

            st.success(f"整理券番号 {st.session_state.next_number} を送信しました🎉")
            st.session_state.next_number += 1

        except Exception as e:
            st.error(f"送信失敗: {e}")

# ------------------------
# ログ確認・ダウンロード (.txt形式)
# ------------------------
st.subheader("📋 整理券ログ")
if st.checkbox("ログを表示する"):
    st.dataframe(st.session_state.df)

if not st.session_state.df.empty:
    txt_buffer = io.BytesIO()
    st.session_state.df.to_csv(txt_buffer, index=False, sep="\t", encoding="utf-8")
    txt_buffer.seek(0)
    st.download_button(
        label="📥 整理券ログをダウンロード（.txt）",
        data=txt_buffer,
        file_name="整理券ログ.txt",
        mime="text/plain"
    )

# 永続ログのダウンロードも追加
if os.path.exists(ALL_LOG_FILE):
    st.subheader("📁 全体の送信履歴ログ")
    all_df = pd.read_csv(ALL_LOG_FILE)
    if st.checkbox("全体ログを表示する"):
        st.dataframe(all_df)

    if not all_df.empty:
        all_txt_buffer = io.BytesIO()
        all_df.to_csv(all_txt_buffer, index=False, sep="\t", encoding="utf-8")
        all_txt_buffer.seek(0)
        st.download_button(
            label="📥 全体ログをダウンロード（.txt）",
            data=all_txt_buffer,
            file_name="全体ログ.txt",
            mime="text/plain"
        )
