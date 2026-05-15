import os
from pathlib import Path
from dotenv import load_dotenv
from ai_evaluator import build_evaluation_prompt, evaluate_students_with_gemini

load_dotenv(Path(".env"))
api_key = os.environ.get("GEMINI_API_KEY", "")

dummy_logs = [
    {"テーマ名": "テスト", "ライフログ内容": "今日は課題を発見して、解決策を探求しました。", "投稿日時": "2026-05-14"}
]
dummy_students = [{"name": "テスト太郎", "logs": dummy_logs}]

dummy_rubric = """
評価項目,1,2,3,4,5
課題発見,×,△,〇,◎,☆
探究する意欲,×,△,〇,◎,☆
説明力,×,△,〇,◎,☆
"""

# use_rubric_items = True のパターンをテスト
results, errors = evaluate_students_with_gemini(
    students=dummy_students,
    rubric_text=dummy_rubric,
    api_key=api_key,
    use_rubric_items=True
)

print("=== RESULTS ===")
for r in results:
    print(r)
print("=== ERRORS ===")
print(errors)
