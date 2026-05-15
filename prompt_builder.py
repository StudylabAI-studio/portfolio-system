"""
prompt_builder.py
生徒のライフログとルーブリックを受け取り、
AI（Gemini等）に貼り付けるための評価プロンプト文を生成するモジュール。
"""


FIXED_LABELS = ["自己管理", "思考力・探究心", "コミュニケーション", "主体性・行動力", "協働・共創力"]


def build_prompt(student_name: str, log_text: str, rubric_text: str,
                 use_rubric_items: bool = False) -> str:
    """
    1名分の評価プロンプトを生成する。

    Args:
        student_name: 生徒名
        log_text: 生徒のライフログ・日記等のテキスト
        rubric_text: ルーブリックのテキスト（評価基準）
        use_rubric_items: Trueの場合、ルーブリックの項目をそのまま評価項目に使う

    Returns:
        AI（Gemini等）に貼り付けるプロンプト文字列
    """
    if use_rubric_items:
        eval_instruction = """
あなたは教育評価の専門家です。
以下のルーブリック（評価基準）に記載されている評価観点をそのまま評価項目として使用してください。
ルーブリックに含まれる全ての評価観点について、0.1刻み（小数点第1位）で1.0〜5.0のスコアを算出してください。

【出力形式（CSVのヘッダー行）】
必ず1行目にCSVのヘッダー、2行目にデータを出力してください。
ヘッダーは「生徒名,総合評価,<評価観点1>,<評価観点2>,...,コメント」の形式です。
（<評価観点>はルーブリックに記載された実際の項目名に置き換える）
"""
        csv_example = "例：生徒名,総合評価,課題発見,探究する意欲,説明力,レジリエンス,相互作用,コメント"
    else:
        eval_instruction = f"""
あなたは教育評価の専門家です。
以下の5つの評価軸でスコアを算出してください：
{', '.join(FIXED_LABELS)}

各項目を0.1刻み（小数点第1位）で1.0〜5.0のスコアで評価してください。

【出力形式（CSVのヘッダー行）】
必ず1行目にCSVのヘッダー、2行目にデータを出力してください。
ヘッダーは「生徒名,総合評価,{','.join(FIXED_LABELS)},コメント」の形式です。
"""
        csv_example = f"例：生徒名,総合評価,{','.join(FIXED_LABELS)},コメント"

    prompt = f"""
{eval_instruction}

【ルーブリック（評価基準）】
{rubric_text}

【生徒名】
{student_name}

【生徒のライフログ・学習記録】
{log_text}

【指示】
上記のライフログを読み、ルーブリックを参考にしながら、この生徒を評価してください。
- 総合評価は5段階（1.0〜5.0、0.1刻み）で算出してください
- 各評価項目も同様に5段階（1.0〜5.0、0.1刻み）で算出してください
- コメントは生徒へのメッセージとして、200文字以内で励ましの言葉を含めて書いてください
- 出力はCSV形式のみで行ってください（説明文や前置きは不要です）

{csv_example}

CSV出力：
"""
    return prompt.strip()


def build_batch_prompt(students_data: list, rubric_text: str,
                       use_rubric_items: bool = False) -> str:
    """
    複数生徒分の評価プロンプトをまとめて生成する（コピペ用）。

    Args:
        students_data: [{"name": "氏名", "log": "ログ文"}, ...] のリスト
        rubric_text: ルーブリックテキスト
        use_rubric_items: ルーブリック項目をそのまま使うか

    Returns:
        全生徒分のプロンプトを結合した文字列
    """
    prompts = []
    for student in students_data:
        p = build_prompt(
            student_name=student.get("name", "不明"),
            log_text=student.get("log", ""),
            rubric_text=rubric_text,
            use_rubric_items=use_rubric_items
        )
        prompts.append(p)
        prompts.append("\n---（次の生徒）---\n")

    return "\n".join(prompts)


def parse_ai_csv_output(raw_text: str) -> list[dict]:
    """
    AIが出力した生テキスト（CSVを含む）を解析し、
    各生徒のデータをdictのリストとして返す。
    AIが出力した余分なテキストや説明文を自動的に除去する。

    Args:
        raw_text: AIが出力した生テキスト

    Returns:
        [{"生徒名": ..., "総合評価": ..., ...}, ...] のリスト
    """
    import io
    import csv

    lines = raw_text.strip().split('\n')
    csv_lines = []
    header_found = False

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # CSVらしい行（カンマを2つ以上含む）を抽出
        if line.count(',') >= 2:
            csv_lines.append(line)
            if not header_found:
                header_found = True

    if not csv_lines:
        return []

    csv_text = '\n'.join(csv_lines)

    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        result = []
        for row in reader:
            # 空キーを除去
            cleaned = {k.strip(): v.strip() for k, v in row.items() if k and k.strip()}
            result.append(cleaned)
        return result
    except Exception:
        return []
