import streamlit as st
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
import io
import re
from PIL import Image, ImageDraw, ImageFont
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ------------------------
# 設定（Secretsから取得）
# ------------------------
EMAIL_FROM = st.secrets["config"]["email_from"]
APP_PASSWORD = st.secrets["config"]["app_password"]
PASSWORD = st.secrets["config"]["admin_password"]
SPREADSHEET_URL = st.secrets["config"]["spreadsheet_url"]
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BASE_IMAGE = "template.png"

# ------------------------
# Google Sheets接続
# ------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
sheet = client.open_by_url(SPREADSHEET_URL).sheet1

# ------------------------
# ログ取得 & 整理券番号決定
# ------------------------
def load_data():
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            max_number = pd.to_numeric(df["整理券番号"], errors='coerce').max()
            return df, int(max_number) + 1
        else:
            return pd.DataFrame(columns=["整理券番号", "学籍番号", "氏名", "メール"]), 1
    except:
        return pd.DataFrame(columns=["整理券番号", "学籍番号", "氏名", "メール"]), 1

df, next_number = load_data()

# ------------------------
# 認証
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
# フォーム
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
            # 画像生成
            image = Image.open(BASE_IMAGE).convert("RGB")
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(FONT_PATH, 36)
            draw.text((50, 60), f"id: {gakuseki}", font=font, fill="black")
            draw.text((50, 130), f"number: {next_number}", font=font, fill="black")
            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            # メール送信
            msg = MIMEMultipart()
            msg["From"] = EMAIL_FROM
            msg["To"] = email
            msg["Subject"] = "【テストメール】アーティストライブ 整理券のご案内"
            body = f"""{name} さん\n\n学祭アーティストライブの整理券を発行しました。\n整理券番号は「{next_number}」です。\n\n当日はこの添付画像を提示してください。\n"""
            msg.attach(MIMEText(body, "plain"))
            image_part = MIMEImage(img_buffer.read(), _subtype="png", name="整理券.png")
            image_part.add_header("Content-Disposition", "attachment", filename="整理券.png")
            msg.attach(image_part)

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(EMAIL_FROM, APP_PASSWORD)
                server.send_message(msg)

            # スプレッドシートに保存
            sheet.append_row([next_number, gakuseki, name, email])

            st.success(f"整理券番号 {next_number} を送信しました🎉")
        except Exception as e:
            st.error(f"送信失敗: {e}")

# ------------------------
# ログ表示＆ダウンロード
# ------------------------
st.subheader("📋 整理券ログ")
if st.checkbox("ログを表示する"):
    st.dataframe(df)

if not df.empty:
    buffer = io.BytesIO()
    df.to_csv(buffer, sep="\t", index=False)
    buffer.seek(0)
    st.download_button("📥 ログをダウンロード（タブ区切り）", data=buffer, file_name="整理券ログ.txt", mime="text/plain")
