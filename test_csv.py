import io
import csv
from ai_evaluator import _parse_gemini_csv

raw_text = """
生徒名,総合評価,総合コメント,課題発見,課題発見_根拠,説明力,説明力_根拠
山田太郎,3.5,素晴らしいですね。,2.5,「あああ」と書いてありますが、それは良いですね。,3.0,「いいい」ですね。
"""

parsed = _parse_gemini_csv(raw_text, "山田太郎")
print("Parsed:", parsed)
