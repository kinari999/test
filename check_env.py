from dotenv import load_dotenv, dotenv_values
import os

# `.env` の値を直接取得する
config = dotenv_values("C:/Users/IT2024/Desktop/test/.env")
REMOVE_BG_API_KEY = config.get("REMOVE_BG_API_KEY")

print("取得したAPIキー:", REMOVE_BG_API_KEY)
