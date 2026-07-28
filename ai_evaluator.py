"""
ai_evaluator.py
Gemini API (google-genai SDK) を使って、
生徒ライフログ x ルーブリック -> 評価結果CSV を自動生成するモジュール。
生徒1人につき複数のライフログを結合して一括評価する。
"""
import time
import re
import csv
import io
import pandas as pd

from google import genai
from google.genai import types

# ─── モデル一覧（現在利用可能な最新API） ───────────────
AVAILABLE_MODELS = {
    "gemini-3.1-flash-lite":  "[推奨] Gemini 3.1 Flash Lite - 超高速・最新モデル",
    "gemini-2.5-flash":       "Gemini 2.5 Flash - 高精度・安定",
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro Preview - 最高精度",
    "gemini-2.5-pro":         "Gemini 2.5 Pro - 安定版最高精度",
}

DEFAULT_MODEL = "gemini-3.1-flash-lite"


FIXED_LABELS = ["自己管理", "思考力・探究心", "コミュニケーション", "主体性・行動力", "協働・共創力"]

# ルーブリック未アップロード時に使用するデフォルトルーブリック
DEFAULT_RUBRIC = """
[評価基準（5項目）]
・自己管理（1〜5点）：目標設定・時間管理・計画的な行動・振り返りの習慣
・思考力・探究心（1〜5点）：疲問を持ち、深く考え、自ら調べる姿勢
・コミュニケーション（1〜5点）：自分の考えを伝え、他者の意見を傾聴する力
・主体性・行動力（1〜5点）：自ら考えて行動し、責任をもって取り組む姿勢
・協働・共創力（1〜5点）：仒間と協力し、より良い成果を目指す力
"""


def build_evaluation_prompt(student_name: str, logs: list,
                            rubric_text: str, use_rubric_items: bool = False,
                            target_grade: str = "中学生") -> str:
    """
    1名分の評価プロンプトを生成する。
    logs = [{"テーマ名": ..., "ライフログ内容": ..., "投稿日時": ...}, ...]
    target_grade に応じて、RPGステータスや進路提案のカラムを付与する。
    """
    log_block = ""
    for i, log in enumerate(logs, 1):
        theme = log.get("テーマ名", "（テーマなし）")
        content = log.get("ライフログ内容", "")
        date = log.get("投稿日時", "")
        if content and str(content) != "nan":
            log_block += f"\n【ログ{i}】テーマ：{theme}　投稿日：{date}\n{content}\n"

    if not log_block.strip():
        log_block = "（ライフログの記録なし）"

    # 学年による追加カラムと追加プロンプト
    extra_columns = ""
    extra_example = ""
    extra_instruction = ""
    if target_grade == "小学生":
        extra_columns = ",隠れジョブ,ステータス1名,ステータス1値,ステータス2名,ステータス2値,ステータス3名,ステータス3値,ステータス4名,ステータス4値,ステータス5名,ステータス5値,スキル1名,スキル1効果,スキル2名,スキル2効果,鑑定書"
        extra_example = ",パラディン ＋ 迷える班員を導く鉄壁の盾,ワクワク探求力,95,するどいツッコミ度,80,コツコツ経験値稼ぎ力,90,みんなを守る防御力,85,ひらめき魔法力,75,鉄壁のディフェンス,「〇〇をサポートした」という言葉から分析。仲間のピンチを救う効果がある,アイデアスパーク,「〇〇を思いついた」という言葉から分析。新しい視点で問題を解決する,君はいつも仲間を助けながら、地道な努力を欠かさない素晴らしい才能の持ち主だ。この調子で冒険を続けよう！"
        extra_instruction = """
【小学生向け特別分析（RPG風）】
あなたは、子どもたちの隠れた才能を見抜く「異世界のギルドマスター」であり、同時に「優秀なデータアナリスト」です。
入力された児童生徒の振り返り・コメントテキストを自然言語処理の視点で分析し、その子の性格、思考の癖、行動パターンを抽出した上で、ワクワクするようなRPG風の「隠れジョブ」と「オリジナルステータス」を生成してください。

以下のステップで思考し、出力に反映させてください。
1. 【抽出】テキストから「ポジティブな感情の表出」「他者との関わり方（協調・牽引・支援など）」「課題解決へのアプローチ（直感・論理・忍耐など）」を抽出する。
2. 【変換】抽出した要素を、RPGの概念（物理攻撃、魔法、防御、回復、探索、テイマーなど）にマッピングする。
3. 【命名】生徒が思わず友達と見せ合いたくなるような、ユニークで肯定的な「ジョブ名」と「パラメータ名」を生成する。
4. 【出力ルール】口調は威厳がありつつも優しいギルドマスターのトーン。ネガティブな表現は一切使わず、全て「独自の強み」として肯定的に変換すること。

CSVの各列には以下の内容を必ず出力してください：
・隠れジョブ: [ベース職業] ＋ [テキストから抽出した独自の二つ名] （例：パラディン ＋ 迷える班員を導く鉄壁の盾）
・ステータス1名〜5名: テキストの分析結果から作成した独自パラメータ名（例：ワクワク探求力）
・ステータス1値〜5値: 上記に対応する数値（1〜99）
・スキル1名〜2名: 具体的な記述に基づいたオリジナルパッシブスキル名
・スキル1効果〜2効果: その効果の解説（テキストの「〜〜」という言葉から分析。〇〇の効果がある）
・鑑定書: なぜこのジョブとステータスになったのか、テキストの分析結果を交えたギルドマスターからの熱い鑑定メッセージ（200文字程度）
"""
    else:
        extra_columns = ",おすすめ学部,学部理由,おすすめ職業,職業理由"
        extra_example = ",情報学部,プログラミングへの関心が高いから,データサイエンティスト,分析力が活かせるから"
        extra_instruction = f"""
【{target_grade}向け特別分析】
生徒の性格や特徴を分析し、将来の進路提案を行ってください。
1. おすすめの大学学部（例：経済学部、情報学部など）とその理由
2. おすすめの職業（例：システムエンジニア、企画営業など）とその理由
"""

    if use_rubric_items:
        output_instruction = f"""
【出力形式】
必ずCSV形式のみで回答してください（説明文・コードブロックは不要）。
ヘッダー行とデータ行の2行だけを出力してください。

【ヘッダー作成の厳密なルール】
1. ヘッダーは必ず以下のように作成してください。
   生徒名,総合評価,総合コメント,（実際の評価項目1）,（実際の評価項目1）_根拠,（実際の評価項目2）,（実際の評価項目2）_根拠,...{extra_columns}
2. 根拠コメントの列名は、必ず「評価項目名」に「_根拠」という文字を直接くっつけた名前にしてください（例：「課題発見_根拠」）。「根拠」という単体や別の名前はNGです。
3. （最重要）データ行の各根拠コメントの中には、絶対に半角カンマ(,)を含めないでください。カンマは全角の「、」に置き換えてください。
"""
    else:
        # "自己管理,自己管理_根拠,思考力・探究心,思考力・探究心_根拠,..." のように組み立てる
        labels_and_reasons = []
        for label in FIXED_LABELS:
            labels_and_reasons.append(label)
            labels_and_reasons.append(f"{label}_根拠")
        labels_str = ",".join(labels_and_reasons)
        
        output_instruction = f"""
【出力形式】
必ずCSV形式のみで回答してください（説明文・コードブロックは不要）。
ヘッダー行とデータ行の2行だけを出力してください。
（最重要）データ行の各根拠コメントの中には、絶対に半角カンマ(,)を含めないでください。カンマは全角の「、」に置き換えてください。

生徒名,総合評価,総合コメント,{labels_str}{extra_columns}
{student_name},3.8,ここに全体の総合コメントを書く,4.0,ここに自己管理の根拠コメントを書く,3.5,ここに思考力・探究心の根拠を書く,...{extra_example}
"""

    return f"""あなたは教育評価の専門家です。以下の生徒のライフログ（複数件）を総合的に読み解き、ルーブリックに基づいて評価してください。

【ルーブリック（評価基準）】
{rubric_text}

【生徒名】
{student_name}

【ライフログ（全{len(logs)}件・時系列順）】
{log_block}

【評価ルール】
- 全てのライフログを通読し、生徒の成長・傾向・特徴を把握してから評価してください
- 各スコアは 1.0〜5.0 の範囲で 0.1 刻みで評価してください
- 総合評価は全項目の平均として算出してください
- 記録が少ない場合でも、書かれた内容から読み取れることを最大限評価してください

【総合コメントの書き方（400文字程度）】
- 生徒の全体的な成長や強みを具体的に述べる
- ログの内容を引用しながら、どこが素晴らしいか伝える
- 今後さらに伸ばすための具体的なポイントやアドバイスを2〜3点入れる
- 応援や期待の気持ちを込めた締めの言葉で終える

【各項目の根拠コメントの書き方（200文字以上）】
- 必ずログの文章を「」で引用して根拠を示すこと
- 引用後の解釈・評価は、以下の多様な表現からランダムに使い分けること（毎回同じ言い回しは避ける）：
  ・「〇〇と記録していますね。これは△△の力が表れている証拠です」
  ・「〇〇という記述から、△△に対する意識の高さが伝わってきます」
  ・「〇〇と振り返っている点に、△△への成長が感じられます」
  ・「〇〇という言葉が印象的です。ここには△△という姿勢が見えます」
  ・「〇〇と書いているように、△△の面で着実に力をつけています」
- さらに、今後どうすればより良くなるかのヒントも1文添えること
- 定型的・機械的にならないよう、項目ごとに文体やトーンを変えること

{extra_instruction}

{output_instruction}
""".strip()


def evaluate_students_with_gemini(
    students: list,
    rubric_text: str,
    api_key: str,
    model_name: str = DEFAULT_MODEL,
    use_rubric_items: bool = False,
    progress_callback=None,
    target_grade: str = "中学生"
) -> tuple:
    """
    全生徒をGemini APIで自動評価する。

    Args:
        students : [{"name": "氏名", "logs": [...]}]
        rubric_text : ルーブリックテキスト
        api_key : Gemini APIキー
        model_name : 使用するGeminiモデル名
        use_rubric_items : ルーブリック項目をそのまま評価軸に使うか
        progress_callback : (current, total, name) -> None
        target_grade : 学年カテゴリ（小学生/中学生/高校生）

    Returns:
        (results, errors)
    """
    client = genai.Client(api_key=api_key)

    results = []
    errors = []
    total = len(students)

    for i, student in enumerate(students):
        name = student["name"]
        logs = student["logs"]

        if progress_callback:
            progress_callback(i, total, name)

        try:
            prompt = build_evaluation_prompt(
                student_name=name,
                logs=logs,
                rubric_text=rubric_text,
                use_rubric_items=use_rubric_items,
                target_grade=target_grade
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    top_p=0.95,
                )
            )
            raw_text = response.text

            parsed = _parse_gemini_csv(raw_text, name)
            if parsed:
                results.append(parsed)
            else:
                errors.append(f"{name}：CSV解析失敗 -> {raw_text[:100]}")
                results.append({"生徒名": name, "総合評価": "3.0", "コメント": "（解析エラー）"})

        except Exception as e:
            errors.append(f"{name}：APIエラー -> {str(e)}")
            results.append({"生徒名": name, "総合評価": "0", "コメント": f"エラー: {str(e)[:50]}"})

        # レート制限対策
        time.sleep(0.5)

    if progress_callback:
        progress_callback(total, total, "完了")

    return results, errors


def evaluate_single_student(
    student: dict,
    rubric_text: str,
    api_key: str,
    model_name: str = DEFAULT_MODEL,
    use_rubric_items: bool = False,
    target_grade: str = "中学生"
) -> tuple:
    """
    1名分の評価を行う。STOPボタン対応用の単一学生処理関数。

    Returns:
        (result_dict, error_str_or_None)
    """
    client = genai.Client(api_key=api_key)
    name = student["name"]
    logs = student["logs"]

    try:
        prompt = build_evaluation_prompt(
            student_name=name,
            logs=logs,
            rubric_text=rubric_text,
            use_rubric_items=use_rubric_items,
            target_grade=target_grade
        )
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                top_p=0.95,
            )
        )
        raw_text = response.text
        parsed = _parse_gemini_csv(raw_text, name)
        if parsed:
            return parsed, None
        else:
            err = f"{name}：CSV解析失敗 → {raw_text[:120]}"
            return {"生徒名": name, "総合評価": "3.0", "コメント": "（解析エラー）"}, err
    except Exception as e:
        err = f"{name}：APIエラー → {str(e)}"
        return {"生徒名": name, "総合評価": "0", "コメント": f"エラー: {str(e)[:50]}"}, err


def _parse_gemini_csv(raw_text: str, student_name: str) -> dict:
    """GeminiのCSV出力テキストを解析してdictに変換。

    【設計方針】
    - 行ごとのカンマ数フィルタを廃止。
      → 以前のフィルタは「改行入り引用フィールド」を誤って切断していた。
    - raw text をそのまま csv.reader に渡す。
      → csv.reader は RFC4180 準拠の引用符・改行を正しく処理できる。
    - ヘッダー行は「生徒名」「総合評価」を含む行として自動検出する。
    - データ列がヘッダー列より多い場合（引用符なしカンマ混入）はスマートマージで修復。
    """
    # コードブロックを除去
    code_block = re.search(r'```(?:csv)?\s*\n?(.*?)```', raw_text, re.DOTALL)
    if code_block:
        raw_text = code_block.group(1).strip()

    try:
        # raw text を直接 csv.reader に渡す（行フィルタ不要）
        reader = csv.reader(io.StringIO(raw_text))
        all_rows = [row for row in reader if row and any(cell.strip() for cell in row)]

        if len(all_rows) < 1:
            return None

        # ── ヘッダー行の自動検出 ────────────────────────────────────
        # 「生徒名」「総合評価」を含む行をヘッダーとみなす
        header_idx = None
        for i, row in enumerate(all_rows):
            joined = " ".join(row)
            if ("生徒名" in joined or "総合評価" in joined) and len(row) >= 3:
                header_idx = i
                break

        # 見つからなければ最初の十分な列数の行をヘッダーとみなす
        if header_idx is None:
            for i, row in enumerate(all_rows):
                if len(row) >= 3:
                    header_idx = i
                    break

        if header_idx is None or header_idx + 1 >= len(all_rows):
            return None

        headers = [h.strip() for h in all_rows[header_idx]]
        data    = [v.strip() for v in all_rows[header_idx + 1]]

        # ── 列数ズレの自動修復（引用符なしカンマ混入対策） ────────────
        if len(data) > len(headers):
            excess = len(data) - len(headers)

            def _is_numeric(v: str) -> bool:
                return bool(re.match(r'^\d+\.?\d*$', v.strip()))

            def _try_merge(d: list, idx: int, n: int):
                if idx + n >= len(d):
                    return None
                merged = ", ".join(d[idx: idx + n + 1])
                return d[:idx] + [merged] + d[idx + n + 1:]

            score_positions = {1, 3, 5, 7, 9, 11}
            best_data = None
            for try_idx in range(2, min(len(data), len(headers) + excess)):
                candidate = _try_merge(data, try_idx, excess)
                if candidate is None or len(candidate) != len(headers):
                    continue
                ok = all(
                    not _is_numeric(data[i]) or _is_numeric(candidate[i])
                    for i in score_positions if i < len(candidate)
                )
                if ok:
                    best_data = candidate
                    break
            if best_data is None:
                best_data = _try_merge(data, 2, excess) or data
            data = best_data

        # ── ヘッダーの名前補正 ──────────────────────────────────────
        for i in range(len(headers)):
            if headers[i] in ("根拠", "コメント", "理由", "根拠コメント"):
                if i > 0 and headers[i-1] not in ("生徒名", "総合評価", "総合コメント", "コメント"):
                    headers[i] = f"{headers[i-1]}_根拠"
            elif headers[i].endswith("スコア"):
                headers[i] = headers[i].replace("スコア", "")

        # ── 辞書化 ─────────────────────────────────────────────────
        cleaned = {}
        for h, v in zip(headers, data):
            if h:
                cleaned[h] = v

        if "生徒名" not in cleaned or not cleaned["生徒名"]:
            cleaned["生徒名"] = student_name

        return cleaned if len(cleaned) >= 2 else None

    except Exception:
        return None


def group_logs_by_student(df) -> list:

    """
    DataFrameから生徒ごとにライフログをグループ化する。
    Returns:
        [{"name": "姓名", "user_id": ..., "logs": [...], "log_count": ..., "group": ...}]
    """
    students = []

    if "ユーザーID" not in df.columns:
        return students

    for user_id, group in df.groupby("ユーザーID"):
        first_row = group.iloc[0]
        sei = str(first_row.get("姓", "")).strip() if pd.notna(first_row.get("姓")) else ""
        mei = str(first_row.get("名", "")).strip() if pd.notna(first_row.get("名")) else ""
        full_name = f"{sei}{mei}".strip() or f"ID:{user_id}"

        # 投稿日時でソート
        if "投稿日時" in group.columns:
            group = group.sort_values("投稿日時")

        logs = []
        for _, row in group.iterrows():
            content = row.get("ライフログ内容", "")
            if pd.notna(content) and str(content).strip():
                logs.append({
                    "テーマ名": str(row.get("テーマ名", "")) if pd.notna(row.get("テーマ名")) else "",
                    "ライフログ内容": str(content).strip(),
                    "投稿日時": str(row.get("投稿日時", "")) if pd.notna(row.get("投稿日時")) else "",
                    "メイングループ": str(row.get("メイングループ", "")) if pd.notna(row.get("メイングループ")) else "",
                })

        students.append({
            "name": full_name,
            "user_id": user_id,
            "logs": logs,
            "log_count": len(logs),
            "group": logs[0].get("メイングループ", "") if logs else ""
        })

    return students


def results_to_csv_bytes(results: list) -> bytes:
    """評価結果をCSVバイト列に変換（BOM付きUTF-8 = Excel対応）"""
    if not results:
        return b""
    all_keys = []
    for r in results:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction='ignore')
    writer.writeheader()
    for r in results:
        writer.writerow(r)
    return buf.getvalue().encode('utf-8-sig')
