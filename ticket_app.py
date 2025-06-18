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

df, next_number = load_log()

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
# ログリセット機能
# ------------------------
with st.expander("⚠️ ログと整理券番号をリセットする"):
    with st.form("reset_form"):
        pw_check = st.text_input("パスワードを再入力してください", type="password")
        confirm = st.checkbox("本当にログをリセットしてよろしいですか？")
        reset_submit = st.form_submit_button("リセット実行")

    if reset_submit:
        if pw_check != PASSWORD:
            st.error("パスワードが間違っています")
        elif not confirm:
            st.warning("確認にチェックが入っていません")
        else:
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)
            df = pd.DataFrame(columns=["整理券番号", "学籍番号", "氏名", "メール"])
            df.to_csv(LOG_FILE, index=False)
            next_number = 1
            st.success("ログと整理券番号をリセットしました")

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
    elif email in df["メール"].values:
        st.warning("このメールにはすでに整理券が発行されています")
    else:
        try:
            # 画像生成（氏名は入れない）
            image = Image.open(BASE_IMAGE).convert("RGB")
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(FONT_PATH, 36)
            draw.text((50, 60), f"id: {gakuseki}", font=font, fill="black")
            draw.text((50, 130), f"number: {next_number}", font=font, fill="black")

            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            # メール作成（氏名入り）
            msg = MIMEMultipart()
            msg["From"] = EMAIL_FROM
            msg["To"] = email
            msg["Subject"] = "【テストメール】アーティストライブ 整理券のご案内"
            body = f"""{name} さん

学祭アーティストライブの整理券を発行しました。
整理券番号は「{next_number}」です。

当日はこの添付画像を提示してください。
"""
            msg.attach(MIMEText(body, "plain"))

            image_part = MIMEImage(img_buffer.read(), _subtype="png", name="整理券.png")
            image_part.add_header("Content-Disposition", "attachment", filename="整理券.png")
            msg.attach(image_part)

            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(EMAIL_FROM, APP_PASSWORD)
                server.send_message(msg)

            # ログ保存
            new_row = pd.DataFrame([[next_number, gakuseki, name, email]], columns=df.columns)
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(LOG_FILE, index=False)

            st.success("整理券を送信しました🎉")

            # 整理券番号を次に更新
            next_number += 1

        except Exception as e:
            st.error(f"送信失敗: {e}")

# ------------------------
# CSV確認・ダウンロード (.txt形式)
# ------------------------
st.subheader("📋 整理券ログ")

if os.path.exists(LOG_FILE):
    df = pd.read_csv(LOG_FILE)

if st.checkbox("ログを表示する"):
    st.dataframe(df)

if not df.empty:
    txt_buffer = io.BytesIO()
df.to_csv(txt_buffer, index=False, sep="\t", encoding="utf-8")  # ← タブ区切り＆UTF-8
txt_buffer.seek(0)

st.download_button(
    label="📥 整理券ログをダウンロード（タブ区切り .txt）",
    data=txt_buffer,
    file_name="整理券ログ.txt",  # 拡張子は .tsv でもOK！
    mime="text/tab-separated-values"
)
