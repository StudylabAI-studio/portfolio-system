"""
pdf_builderの_get_score_items_with_reasonsが正しく動くかテスト
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pdf_builder import _get_score_items_with_reasons

# AIが出力するデータを模倣（文字化け前提でも列順でペアリングできるか）
test_row = {
    "生徒名": "テスト太郎",
    "総合評価": "3.0",
    "総合コメント": "素晴らしい成長が見られます。",
    "課題発見": "2.5",
    "課題発見_根拠": "「新しい課題を発見した」と書いてるということは、主体的に問題を見つける力があるということですね。",
    "探究する意欲": "3.0",
    "探究する意欲_根拠": "「自分なりに解決策を考えた」と書いてるということは、自ら調べ考える探究心があるということですね。",
    "説明力": "3.5",
    "説明力_根拠": "「チームに報告した」と書いてるということは、自分の考えを他者に伝えようとする意識があるということですね。",
}

items = _get_score_items_with_reasons(test_row)
print(f"=== 取得できたアイテム数: {len(items)} ===")
for item in items:
    print(f"  ラベル: [{item['label']}]")
    print(f"  スコア: [{item['score']}]")
    print(f"  根拠: [{item['reason'][:40]}...]")
    print()
