"""
デバッグ用：AIが返す生のテキストを確認し、パース結果まで追跡する
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".env"))
api_key = os.environ.get("GEMINI_API_KEY", "")

# ai_evaluatorのimport
sys.path.insert(0, str(Path(__file__).parent))
from ai_evaluator import build_evaluation_prompt, _parse_gemini_csv, DEFAULT_MODEL

try:
    from google import genai
    from google.genai import types as genai_types
    client = genai.Client(api_key=api_key)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

dummy_logs = [
    {"テーマ名": "仕事", "ライフログ内容": "今日は新しい課題を発見し、自分なりに解決策を考えて取り組みました。チームにも報告しました。", "投稿日時": "2026-05-14"}
]
student_name = "テスト太郎"
rubric_text = """
課題発見,1,2,3,4,5
探究する意欲,1,2,3,4,5
説明力,1,2,3,4,5
"""

prompt = build_evaluation_prompt(
    student_name=student_name,
    logs=dummy_logs,
    rubric_text=rubric_text,
    use_rubric_items=True
)

print("=== PROMPT TAIL (last 800 chars) ===")
print(prompt[-800:])
print()

# 実際にAI呼び出し
response = client.models.generate_content(
    model=DEFAULT_MODEL,
    contents=prompt,
    config=genai_types.GenerateContentConfig(temperature=0.3)
)
raw = response.text

print("=== RAW AI OUTPUT ===")
print(repr(raw))
print()
print("=== RAW AI OUTPUT (readable) ===")
print(raw)
print()

parsed = _parse_gemini_csv(raw, student_name)
print("=== PARSED RESULT ===")
print(parsed)
print()
if parsed:
    for k, v in parsed.items():
        print(f"  [{k}] = [{v}]")
