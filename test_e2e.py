"""
実際のAI評価フローをエンドツーエンドでテスト。
根拠コメントがpdf_builderに正しく渡るか確認する。
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".env"))
api_key = os.environ.get("GEMINI_API_KEY", "")
sys.path.insert(0, str(Path(__file__).parent))

from ai_evaluator import evaluate_students_with_gemini
from pdf_builder import _get_score_items_with_reasons, _build_template_context

dummy_students = [
    {
        "name": "テスト太郎",
        "logs": [
            {"テーマ名": "日常", "ライフログ内容": "今日は新しい課題を発見しました。自分なりに解決策を考えてチームに報告しました。困難でも諦めずに続けました。", "投稿日時": "2026-05-14"}
        ]
    }
]

rubric_text = """
①課題発見,1,2,3,4,5
②探究する意欲,1,2,3,4,5
③説明力,1,2,3,4,5
④レジリエンス,1,2,3,4,5
⑤相互作用,1,2,3,4,5
"""

print("=== Step1: AI評価実行 ===")
results, errors = evaluate_students_with_gemini(
    students=dummy_students,
    rubric_text=rubric_text,
    api_key=api_key,
    use_rubric_items=True
)
print(f"errors: {errors}")
row = results[0]
print(f"\n=== Step2: 取得したrowのキー一覧 ===")
for k, v in row.items():
    v_str = str(v)[:60] if v else "(空)"
    print(f"  [{k}] => [{v_str}]")

print(f"\n=== Step3: _get_score_items_with_reasons ===")
items = _get_score_items_with_reasons(row)
print(f"アイテム数: {len(items)}")
for it in items:
    print(f"  label=[{it['label']}] score=[{it['score']}] reason=[{str(it['reason'])[:50]}]")
