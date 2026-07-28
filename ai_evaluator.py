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


def build_evaluation_prompt(
    student_name: str,
    logs: list,
    rubric_text: str,
    use_rubric_items: bool = False,
    target_grade: str = "中学生",
    expected_headers: list = None
) -> str:
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
    elif target_grade == "中学生":
        extra_columns = ""
        extra_example = ""
        extra_instruction = ""
    else:  # 高校生など
        extra_columns = ""
        extra_example = ""
        extra_instruction = ""

    if use_rubric_items:
        output_instruction = f"""
【出力形式】
必ずCSV形式のみで回答してください（説明文・コードブロックは不要）。
必ず「ヘッダー行」と「データ行」の合計2行を出力してください。ヘッダー行を省略するとシステムエラーになるため絶対に省略しないでください。

【ヘッダー作成の厳密なルール】
1. ヘッダー行は必ず以下のフォーマットで出力してください。
生徒名,総合評価,総合コメント,（評価項目1）,（評価項目1）_根拠,（評価項目2）,（評価項目2）_根拠,...{extra_columns}
（例：生徒名,総合評価,総合コメント,主体性,主体性_根拠,課題発見,課題発見_根拠）
2. 「評価項目のスコア列（数値）」と「その根拠コメント列（_根拠）」は、必ずペアで出力してください。スコア列を省略して根拠コメント列だけを出力することは絶対にやめてください。
3. （最重要）データ行の各根拠コメントの中には、絶対に半角カンマ(,)を含めないでください。カンマは全角の「、」に置き換えてください。

【データ行の出力例】
{student_name},3.8,ここに全体の総合コメントを書く,4.0,ここに評価項目1の根拠コメントを書く,3.5,ここに評価項目2の根拠を書く,...{extra_example}
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
必ず「ヘッダー行」と「データ行」の合計2行を出力してください。ヘッダー行を省略するとシステムエラーになるため絶対に省略しないでください。

（最重要）データ行の各根拠コメントの中には、絶対に半角カンマ(,)を含めないでください。カンマは全角の「、」に置き換えてください。

生徒名,総合評価,総合コメント,{labels_str}{extra_columns}
{student_name},3.8,ここに全体の総合コメントを書く,4.0,ここに自己管理の根拠コメントを書く,3.5,ここに思考力・探究心の根拠を書く,...{extra_example}
"""

    if expected_headers:
        header_str = ",".join(expected_headers)
        # スコア列と根拠列のペアをデータ行の例として組み立てる
        example_values = [student_name, "3.8", "ここに総合コメントを記入"]
        for h in expected_headers[3:]:  # 生徒名・総合評価・総合コメントの後ろ
            if h.endswith("_根拠"):
                example_values.append("ここに根拠コメントを記入（半角カンマ不可）")
            else:
                example_values.append("3.5")
        example_str = ",".join(example_values)

        output_instruction = f"""
【出力形式 - 絶対に守ること】
必ずCSV形式のみで回答してください（説明文・コードブロックは一切不要）。
必ず「ヘッダー行」と「データ行」の合計2行のみを出力してください。

【ヘッダー行（変更禁止）】
以下のヘッダーを一字一句変えずにそのまま出力してください：
{header_str}

【データ行のルール】
1. 「スコア列（数値）」と「根拠コメント列（_根拠）」は必ずペアで、スコアを省略しないこと。
2. 数値列には必ず1.0〜5.0の数値を入れること（根拠コメントを入れてはいけない）。
3. 根拠コメント列には必ずコメント文を入れること（数値だけ入れてはいけない）。
4. 根拠コメントの中に半角カンマ(,)を絶対に含めないこと。全角の「、」に置き換えること。

【データ行の出力例】
{example_str}
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
    target_grade: str = "中学生",
    expected_headers: list = None
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
            target_grade=target_grade,
            expected_headers=expected_headers
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
        parsed = _parse_gemini_csv(raw_text, name, expected_headers)
        if parsed:
            # ＝＝＝ ここから第2段階（Two-Stage）評価 ＝＝＝
            if target_grade == "高校生":
                try:
                    hs_json_str = _generate_hs_career_json(name, logs, client, model_name)
                    parsed["hs_career_json"] = hs_json_str
                except Exception as json_e:
                    print(f"高校生JSON取得エラー({name}): {json_e}")
            
            elif target_grade == "中学生":
                try:
                    jhs_json_str = _generate_jhs_career_json(name, logs, client, model_name)
                    parsed["jhs_career_json"] = jhs_json_str
                except Exception as json_e:
                    print(f"中学生JSON取得エラー({name}): {json_e}")
            # ＝＝＝ ここまで ＝＝＝
            
            return parsed, None
        else:
            err = f"{name}：CSV解析失敗 → {raw_text[:120]}"
            return {"生徒名": name, "総合評価": "3.0", "コメント": "（解析エラー）"}, err
    except Exception as e:
        err = f"{name}：APIエラー → {str(e)}"
        return {"生徒名": name, "総合評価": "0", "コメント": f"エラー: {str(e)[:50]}"}, err


def _parse_gemini_csv(raw_text: str, student_name: str, expected_headers: list = None) -> dict:
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

        if header_idx is None:
            return None

        # ── expected_headers がある場合、AIのヘッダーを完全無視して位置だけでマッピング ──
        # AIが列名を変えたり省略したりしても常に正しい列に値が入るようにする
        if expected_headers:
            headers = expected_headers
            # データ行だけ取り出す（ヘッダー行の次の行 or 1行しかない場合はその行）
            if len(all_rows) == 1:
                raw_data = [v.strip() for v in all_rows[0]]
            else:
                raw_data = [v.strip() for v in all_rows[header_idx + 1]]

            # データが列数より多い場合は余剰分をマージして長さを合わせる
            if len(raw_data) > len(headers):
                excess = len(raw_data) - len(headers)

                def _is_numeric(v: str) -> bool:
                    return bool(re.match(r'^\d+\.?\d*$', v.strip()))

                # スコア位置（偶数インデックス 3,5,7...）の数値が壊れないようマージ先を選ぶ
                merged = None
                for merge_at in range(2, len(raw_data) - excess + 1):
                    candidate = raw_data[:merge_at] + [", ".join(raw_data[merge_at:merge_at + excess + 1])] + raw_data[merge_at + excess + 1:]
                    if len(candidate) == len(headers):
                        merged = candidate
                        break
                raw_data = merged if merged else raw_data[:len(headers)]

            # データが列数より少ない場合は空文字で埋める
            if len(raw_data) < len(headers):
                raw_data.extend([""] * (len(headers) - len(raw_data)))

            cleaned = {}
            for h, v in zip(headers, raw_data):
                if h:
                    cleaned[h] = v
            if "生徒名" not in cleaned or not cleaned["生徒名"]:
                cleaned["生徒名"] = student_name
            return cleaned if len(cleaned) >= 2 else None

        # ── expected_headers なし（1人目）：AIの出力をそのまま解析 ──
        if header_idx + 1 >= len(all_rows):
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
    """評価結果をCSVバイト列に変換（BOM付きUTF-8 = Excel対応）

    【設計方針】
    - 1人目の生徒が持つ列名を「正式な列リスト」として確定する
    - 2人目以降の生徒dictに1人目と異なる列名が含まれる場合は、
      列の「位置（インデックス）」を基準にマッピングして正式な列名に書き換える
    - これにより、AIが毎回違う列名を使っても列のズレ・二重化が発生しない
    - hs_career_json / jhs_career_json は常に末尾に付与する
    """
    if not results:
        return b""

    SPECIAL_KEYS = {"hs_career_json", "jhs_career_json"}

    # ── 1人目の列構造を正式な列リストとして確定 ──
    first = results[0]
    canonical_keys = [k for k in first.keys() if k not in SPECIAL_KEYS]
    # 特殊キーは末尾に追加（存在する場合のみ）
    special_keys_present = [k for k in SPECIAL_KEYS if any(k in r for r in results)]
    all_keys = canonical_keys + special_keys_present

    # ── 各行を canonical_keys に揃えて書き出す ──
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction='ignore', restval='')
    writer.writeheader()

    for r in results:
        # r のキーのうち SPECIAL_KEYS 以外を「値リスト」として取り出す
        r_normal_keys = [k for k in r.keys() if k not in SPECIAL_KEYS]
        r_values = [r[k] for k in r_normal_keys]

        # canonical_keys と r_normal_keys が一致する場合はそのまま使用
        if r_normal_keys == canonical_keys:
            row_dict = {k: r.get(k, '') for k in all_keys}
        else:
            # 列名が異なる場合は「位置」でマッピング（AIが列名を変えた場合の救済）
            row_dict = {}
            for i, canon_key in enumerate(canonical_keys):
                if i < len(r_values):
                    row_dict[canon_key] = r_values[i]
                else:
                    row_dict[canon_key] = ''
            # 特殊キーを追加
            for sk in special_keys_present:
                row_dict[sk] = r.get(sk, '')

        writer.writerow(row_dict)

    return buf.getvalue().encode('utf-8-sig')



def _generate_hs_career_json(student_name: str, logs: list, client, model_name: str) -> str:
    """高校生向け第2段階評価：キャリアコンサルタントとしてJSONを出力する"""
    log_block = ""
    for i, log in enumerate(logs, 1):
        theme = log.get("テーマ名", "（テーマなし）")
        content = log.get("ライフログ内容", "")
        if content and str(content) != "nan":
            log_block += f"\n【ログ{i}】テーマ：{theme}\n{content}\n"

    if not log_block.strip():
        log_block = "（ライフログの記録なし）"

    prompt = f"""あなたは、生徒の隠れた才能や可能性を引き出す、経験豊富で非常に優秀な進路指導専門のキャリアコンサルタントです。
システムから入力される生徒のログデータやコメント（興味、関心、将来の夢、得意科目、日常の些細な行動など）を深く分析し、指定された【学部・学科リスト】の中から、その生徒の適性に最も合致する学部・分野を1位から3位まで判定してください。

### 指示・条件
1. 必ず【学部・学科リスト】に存在する「学部名」と「分野名」の組み合わせから選定すること。
2. 生徒全員が同じ学校行事（例：体育祭や修学旅行）について書いている場合があります。その場合でも、生徒一人ひとりの「役割の違い（リーダー、裏方、分析、調整役など）」や「着眼点の違い」を鋭く捉え、**できる限り多様な学部・分野を提案してください**。全員に同じ学部（例：経営学部や社会学部など）ばかりを提案する偏りを避け、その生徒ならではの個性にフォーカスしたユニークな視点で選定すること。
3. 【選定理由（reason）】は、**必ず100文字以上150文字程度**の丁寧で温かみのある文章で作成すること。以下の構成を必ず含めてください。
   - ① ログから読み取れる生徒の強みや適性への共感と分析
   - ② その学部・分野に進むことで、具体的にどのような知識やスキルが身につくか
   - ③ その学びが、生徒の将来の可能性をどう広げるか
4. 【おすすめの職業（professions）】は、選定した学部・分野の学びに直結し、かつ生徒の興味関心を活かせる「具体的で魅力的な職業」を各順位ごとに3つ提案すること。（例：漠然とした「エンジニア」ではなく「UI/UXデザイナー」や「データサイエンティスト」など、高校生が憧れるような具体的な名称にすること）
5. 出力は、既存のシステムを壊さないよう、必ず以下のJSON配列フォーマットのみを出力すること。Markdownの装飾(```json など)や、その他の挨拶・説明文は一切出力してはならない。

### 出力JSONフォーマット
[
  {{
    "rank": 1,
    "faculty": "学部名",
    "department": "分野名",
    "reason": "ここに100文字以上の、生徒に寄り添った丁寧で説得力のある解説文を出力します。",
    "professions": ["具体的な職業名1", "具体的な職業名2", "具体的な職業名3"]
  }},
  {{
    "rank": 2,
    "faculty": "学部名",
    "department": "分野名",
    "reason": "ここに100文字以上の、生徒に寄り添った丁寧で説得力のある解説文を出力します。",
    "professions": ["具体的な職業名1", "具体的な職業名2", "具体的な職業名3"]
  }},
  {{
    "rank": 3,
    "faculty": "学部名",
    "department": "分野名",
    "reason": "ここに100文字以上の、生徒に寄り添った丁寧で説得力のある解説文を出力します。",
    "professions": ["具体的な職業名1", "具体的な職業名2", "具体的な職業名3"]
  }}
]

### 学部・学科リスト
・文学部（文学、史学・地理学、哲学、心理学）
・外国語学部（語学）
・人文・教養・人間科学部（文化学、教養学、総合科学、人間科学／人文系その他）
・教育・教員養成系学部（教育学、小学校・幼稚園課程、中等教育課程、特別支援教育課程、養護教諭課程）
・法学部（法学、政治学・政策学）
・経済・経営・商学部（経済学、経営学・経営情報学・商学・会計学）
・社会・社会福祉学部（社会学・観光学・メディア学、社会福祉学）
・国際関係学部（国際関係学・国際文化学）
・理学部（数学・情報科学、物理学、化学、生物学・生命科学、地学、環境科学／その他）
・工学部（機械工学、電気・電子工学、情報工学、土木工学、建築学、原子力工学、応用物理学、応用化学、生物工学、資源工学、材料工学、航空・宇宙工学、経営工学・管理工学、船舶・海洋工学・商船学、医用・生体工学、光工学分野／その他）
・農・獣医畜産・水産学部（農学、農芸化学、農業工学、農業経済学、森林科学、獣医学、畜産学・動物学、水産学、生物生産・生物資源学）
・医学部（医学）
・歯学部（歯学）
・薬学部（薬学）
・看護・医療・栄養学部（看護学、医療・保健学、栄養学）
・家政・生活科学部（家政・生活科学、食物学、被服学、住居学、児童学・子ども学）
・体育・健康科学部（体育・健康科学）
・芸術学部（美術、デザイン、工芸、音楽、芸術系その他（CG等含む））

【生徒名】
{student_name}

【ライフログ】
{log_block}
"""
    from google.genai import types
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
        )
    )
    # Markdownブロックがあれば除去する
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _generate_jhs_career_json(student_name: str, logs: list, client, model_name: str) -> str:
    """中学生向け第2段階評価：専門家としてJSONを出力する"""
    log_block = ""
    for i, log in enumerate(logs, 1):
        theme = log.get("テーマ名", "（テーマなし）")
        content = log.get("ライフログ内容", "")
        if content and str(content) != "nan":
            log_block += f"\n【ログ{i}】テーマ：{theme}\n{content}\n"

    if not log_block.strip():
        log_block = "（ライフログの記録なし）"

    prompt = f"""あなたは、中学生の隠れた才能を見抜き、未来へのモチベーションを高める進路・才能開発の専門家です。
システムから渡される生徒の日々のログ（日記、振り返り、興味関心の記録など）を深く分析し、その生徒ならではの「強み」と「最適な高校環境・進路」を導き出してください。

### 指示・条件
1. 単調な性格診断や、ありきたりな進路指導（例：「優しい性格です」「普通科が向いています」など）は絶対に避けること。
2. 生徒全員が同じ学校行事（例：体育祭）について書いている場合でも、一人ひとりの「着眼点」や「感情の動き」の違いを鋭く捉え、**多様な強みや分野を提案してください**。同じような強みや分野ばかりになる偏りを避けること。
3. 生徒のログから読み取れる具体的な行動や思考のクセを「強み」として評価すること。
4. 【進路に関するアドバイス（advice）】は、この出力において最も重要な項目です。分析した強みを踏まえ、「どのような高校環境が合っているか」「将来どんな分野でその力が活きるか」を**200文字以上250文字程度**で、具体的かつ熱量を持って詳細に語りかけること。
5. 以下のJSONフォーマットのみを出力すること。Markdownの装飾(```json など)や挨拶文は一切含めないこと。

### 出力JSONフォーマット
{{
  "title": "ログから見えてきた、あなたのテーマ（※生徒のログの傾向を象徴するタイトルを20文字程度で作成）",
  "strengths": {{
    "keywords": ["強みを示すキーワード1", "強みを示すキーワード2", "強みを示すキーワード3"],
    "analysis": "ここに100文字以上150文字程度で、生徒の強みに対する分析を出力します。ログの具体的なエピソードを必ず引用し、なぜそれが強みと言えるのかを伝えてください。"
  }},
  "future_path": {{
    "recommended_environment": "〇〇を重視する高校・学習環境（例：理数探究に強い学校、生徒の自主性を重んじる自由な校風、など）",
    "future_fields": ["将来の可能性が広がる分野1", "将来の可能性が広がる分野2"],
    "advice": "ここに200文字以上250文字程度で、進路に関する詳細なアドバイスを出力します。分析した強みが、どのような高校環境（学習スタイル、校風、部活や探究の環境など）で最も伸びるのか、また将来の分野（IT、クリエイティブ、対人支援など）にどう繋がっていくのか、中学生が自分の未来に期待を持てるように具体的に解説してください。"
  }},
  "next_action": "明日からできる小さな挑戦や、調べてみると面白い探究テーマ（40文字程度）"
}}

【生徒名】
{student_name}

【ライフログ】
{log_block}
"""
    from google.genai import types
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
        )
    )
    # Markdownブロックがあれば除去する
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()
