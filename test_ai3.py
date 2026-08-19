import os
from dotenv import load_dotenv
load_dotenv('.env')

import google.genai as genai
from google.genai import types
from ai_evaluator import build_evaluation_prompt, _parse_gemini_csv

api_key = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=api_key)

rubric_text = "主体性\n思考・判断・表現\n知識・技能"
logs = [{"テーマ名": "体育祭", "ライフログ内容": "頑張った"}]
prompt = build_evaluation_prompt("新井湊太", logs, rubric_text, True, "小学生")

res = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=prompt,
    config=types.GenerateContentConfig(temperature=0.3, top_p=0.95)
)
print("--- AI RAW OUTPUT ---")
print(res.text)
print("--- PARSED ---")
print(_parse_gemini_csv(res.text, "新井湊太"))
