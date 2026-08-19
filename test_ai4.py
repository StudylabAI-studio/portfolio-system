import os
from dotenv import load_dotenv
load_dotenv('.env')

import google.genai as genai
from google.genai import types
from ai_evaluator import evaluate_single_student

api_key = os.environ.get("GEMINI_API_KEY", "")

rubric_text = "①主体性\n②思考・判断\n③知識・技能"
student = {"name": "テスト太郎", "logs": [{"テーマ名": "テスト", "ライフログ内容": "テスト内容", "投稿日時": "2026-01-01"}]}

print("Evaluating...")
res, err = evaluate_single_student(
    student=student,
    rubric_text=rubric_text,
    api_key=api_key,
    model_name="gemini-3.1-flash-lite",
    use_rubric_items=True,
    target_grade="小学生"
)
print("Result:", res)
print("Error:", err)
