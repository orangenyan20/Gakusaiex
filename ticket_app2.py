import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)

spreadsheet = client.open_by_url(st.secrets["config"]["spreadsheet_url"])
worksheet = spreadsheet.sheet1
worksheet.append_row(["テスト", "連携OK"])
