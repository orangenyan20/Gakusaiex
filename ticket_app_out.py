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
        df = pd.DataFrame(columns=["整理券番号", "氏名", "メール"])
        return df, 1

if "next_number" not in st.session_state:
    df, next_number = load_log()
    st.session_state.df = df
    st.session_state.next_number = next_number
else:
    df = st.session_state.df
    next_number = st.session_state.next_number

# ------------------------
# ログイン画面
# ------------------------
st.title("🎫 学祭アーティストライブ 整理券発行アプリ（一般用）")

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
with st.expander("📤 ログと整理券番号のメンテナンス"):
    with st.form("maintenance_form"):
        option = st.radio("操作を選んでください", ("何もしない", "ログをリセット", "途中から整理券番号を指定して再開"))
        new_start = st.number_input("再開する整理券番号を入力してください", min_value=1, step=1, value=1)
        pw_check = st.text_input("パスワードを再入力してください", type="password")
        confirm = st.checkbox("本当にこの操作を実行してよろしいですか？")
        maintenance_submit = st.form_submit_button("実行")

    if maintenance_submit:
        if pw_check != PASSWORD:
            st.error("パスワードが間違っています")
        elif not confirm:
            st.warning("確認にチェックが入っていません")
        else:
            if option == "ログをリセット":
                df = pd.DataFrame(columns=["整理券番号", "氏名", "メール"])
                df.to_csv(LOG_FILE, index=False)
                st.session_state.df = df
                st.session_state.next_number = 1
                st.success("ログと整理券番号をリセットしました")
            elif option == "途中から整理券番号を指定して再開":
                st.session_state.next_number = new_start
                st.success(f"整理券番号を {new_start} から再開します")

# ------------------------
# 入力フォーム
# ------------------------
st.subheader("🎟 整理券情報入力")

domain_options = ["gmail.com", "yahoo.co.jp", "icloud.com", "outlook.jp", "yamaguchi-u.ac.jp", "その他"]

with st.form("ticket_form"):
    name = st.text_input("氏名")
    local_part = st.text_input("メールアドレスの＠より前")
    selected_domain = st.selectbox("ドメインを選んでください（その他を選んだ場合は全体を入力）", domain_options)
    full_email_manual = ""

    if selected_domain == "その他":
        full_email_manual = st.text_input("メールアドレスを全て入力してください（例: abc@example.com）")

    skip_email = st.checkbox("メールアドレスを持っていない、または紙で整理券を受け取る")
    submitted = st.form_submit_button("整理券を発行して送信")

if submitted:
    if not name.strip():
        st.error("氏名を入力してください")
    elif skip_email:
        email = "紙"
    elif selected_domain == "その他":
        if not full_email_manual or "@" not in full_email_manual:
            st.error("メールアドレスを正しく入力してください")
            st.stop()
        else:
            email = full_email_manual
    else:
        if not local_part or not re.fullmatch(r"[A-Za-z0-9._%+-]+", local_part):
            st.error("＠より前を正しく入力してください")
            st.stop()
        email = f"{local_part}@{selected_domain}"

    if email != "紙" and email in df["メール"].values:
        st.warning("このメールにはすでに整理券が発行されています")
    else:
        try:
            # 画像生成（氏名は入れない）
            image = Image.open(BASE_IMAGE).convert("RGB")
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(FONT_PATH, 36)
            draw.text((50, 60), f"number: {next_number}", font=font, fill="black")

            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            if email != "紙":
                msg = MIMEMultipart()
                msg["From"] = EMAIL_FROM
                msg["To"] = email
                msg["Subject"] = "【学祭】アーティストライブ 整理券のご案内"
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

            st.success(f"整理券番号 {next_number} を{'発行しました' if email == '紙' else '送信しました'}🎉")

        except Exception as e:
            st.error(f"送信失敗: {e}")

# ------------------------
# CSV確認・ダウンロード (.txt形式)
# ------------------------
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
        file_name="整理券ログ.txt",
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
            file_name="整理券全体ログ.txt",
            mime="text/plain"
        )
