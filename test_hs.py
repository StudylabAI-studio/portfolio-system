import json
import pandas as pd
from ai_evaluator import _generate_hs_career_json
import google.genai as genai
import os

api_key = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=api_key)

logs = [
    {"テーマ名": "体育祭", "ライフログ内容": "綱引きとリレーに参加した。クラスで円陣を組んで頑張った。"}
]

print("Attempt 1:")
try:
    res1 = _generate_hs_career_json("生徒A", logs, client, "gemini-3.1-flash-lite")
    print(res1)
except Exception as e:
    print(e)
