"""
pdf_builder.py
Jinja2テンプレートとPlaywrightを使って、
生徒データからA4サイズのPDFを一括生成し、ZIPにまとめるモジュール。
"""
import os
import io
import sys
import base64
import zipfile
import json
import math
import subprocess
import tempfile
import traceback
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


# レーダーチャートモジュール
from radar_chart import generate_radar_chart, generate_radar_chart_light

TEMPLATES_DIR = Path(__file__).parent / "templates"

# スコア関連の固定ラベル（デフォルト）
DEFAULT_SCORE_LABELS = ["自己管理", "思考力・探究心", "コミュニケーション", "主体性・行動力", "協働・共創力"]


# Playwright Chromiumの自動インストール（クラウド・ローカル共通）
_playwright_installed = False

def _ensure_playwright_browsers():
    """
    PlaywrightのBrowsers（Chromium）がなければ自動インストールする。
    --with-depsはsudo権限が必要なため、ブラウザバイナリのみをインストールする。
    """
    global _playwright_installed
    if _playwright_installed:
        return
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            timeout=300
        )
        if result.returncode == 0:
            _playwright_installed = True
        else:
            # エラー内容を無視して続行（次のlaunch()でエラーが出る）
            _playwright_installed = True  # 試みた事実だけ記録
    except Exception:
        _playwright_installed = True  # 試みた事実だけ記録


def _html_to_pdf(html_content: str) -> bytes:
    """
    HTML文字列をPDFバイト列に変換する。
    Playwright（Chromium）を使用。初回実行時にブラウザを自動インストールする。
    """
    _ensure_playwright_browsers()
    try:
        from playwright.sync_api import sync_playwright

        # 一時HTMLファイルに書き出してgoto()で読み込む（リソース読み込みのため）
        with tempfile.NamedTemporaryFile(
            suffix='.html', mode='w', encoding='utf-8', delete=False
        ) as tmp:
            tmp.write(html_content)
            tmp_path = tmp.name

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(f"file:///{tmp_path.replace(os.sep, '/')}", wait_until="networkidle")
                page.wait_for_timeout(1500)  # フォント・チャート描画待ち
                pdf_bytes = page.pdf(
                    format='A4',
                    print_background=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}
                )
                browser.close()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        return pdf_bytes
    except ImportError:
        raise RuntimeError("Playwrightがインストールされていません。requirements.txtにplaywrightを追加してください。")
    except Exception as e:
        # Chromiumが見つからない場合、もう一度インストールを試みる
        if "Executable doesn't exist" in str(e):
            try:
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    timeout=300
                )
                # 再試行
                from playwright.sync_api import sync_playwright
                with tempfile.NamedTemporaryFile(
                    suffix='.html', mode='w', encoding='utf-8', delete=False
                ) as tmp:
                    tmp.write(html_content)
                    tmp_path = tmp.name
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch()
                        page = browser.new_page()
                        page.goto(f"file:///{tmp_path.replace(os.sep, '/')}", wait_until="networkidle")
                        page.wait_for_timeout(1500)
                        pdf_bytes = page.pdf(
                            format='A4',
                            print_background=True,
                            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}
                        )
                        browser.close()
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                return pdf_bytes
            except Exception as e2:
                raise RuntimeError(f"PDF生成に失敗しました（Chromiumインストール後も失敗）: {e2}")
        raise RuntimeError(f"PDF生成に失敗しました: {e}")








def _get_score_columns(row: dict) -> tuple[list[str], list[float]]:
    """
    CSVの行データから「総合評価」「コメント」以外のスコア列を動的に抽出する。

    Returns:
        (labels, scores) のタプル
    """
    exclude_keys = {
        "生徒名", "総合評価", "総合コメント", "コメント", "",
        "おすすめ学部", "学部理由", "おすすめ職業", "職業理由",
        "隠れジョブ", "ジョブ理由",
        "ステータス1名", "ステータス1値",
        "ステータス2名", "ステータス2値",
        "ステータス3名", "ステータス3値",
        "ステータス4名", "ステータス4値",
        "ステータス5名", "ステータス5値",
        "スキル1名", "スキル1効果",
        "スキル2名", "スキル2効果",
        "鑑定書"
    }
    labels = []
    scores = []

    for k, v in row.items():
        if k in exclude_keys or k.endswith("_根拠"):
            continue
        try:
            score = float(v)
            labels.append(k)
            scores.append(score)
        except (ValueError, TypeError):
            continue

    return labels, scores


def _get_score_items_with_reasons(row: dict) -> list[dict]:
    """
    CSVの行から「スコア＋根拠コメント」のペアを取得する。
    戦略:
    1. 数値が入っていて"_根拠"が付いていない列 = スコア列
    2. 各スコア列に対し、「列名+_根拠」を環境構築して根拠テキストを取得
    3. 見つからなければ列順で次の非数値列を利用
    """
    exclude_keys = {
        "生徒名", "総合評価", "総合コメント", "コメント", "",
        "おすすめ学部", "学部理由", "おすすめ職業", "職業理由",
        "隠れジョブ", "ジョブ理由",
        "ステータス1名", "ステータス1値",
        "ステータス2名", "ステータス2値",
        "ステータス3名", "ステータス3値",
        "ステータス4名", "ステータス4値",
        "ステータス5名", "ステータス5値",
        "スキル1名", "スキル1効果",
        "スキル2名", "スキル2効果",
        "鑑定書"
    }

    import math
    # スコア列を特定（数値で"_根拠"が付いていない列）
    score_keys = []
    for k, v in row.items():
        if not k or k in exclude_keys or k.endswith("_根拠"):
            continue
        try:
            val = float(str(v).strip())
            if math.isnan(val):
                continue
            score_keys.append(k)
        except (ValueError, TypeError):
            pass

    all_keys_list = list(row.keys())
    items = []

    for sk in score_keys:
        score = float(str(row[sk]).strip())
        label = sk.strip()
        reason = ""

        # 戦略①: "スコアキー_根拠" で直接検索
        exact_key = sk + "_根拠"
        if exact_key in row and str(row[exact_key]).strip():
            reason = str(row[exact_key]).strip()

        # 戦略②: 見つからなければ列順で次の非数値列を探す
        if not reason:
            try:
                sk_idx = all_keys_list.index(sk)
                for next_idx in range(sk_idx + 1, min(sk_idx + 3, len(all_keys_list))):
                    nk = all_keys_list[next_idx]
                    if nk in exclude_keys:
                        continue
                    nv = str(row[nk]).strip()
                    if not nv:
                        continue
                    try:
                        float(nv)  # 数値なら根拠ではない
                    except (ValueError, TypeError):
                        reason = nv
                        break
            except (ValueError, IndexError):
                pass

        items.append({"label": label, "score": score, "reason": reason})

    return items



def _score_to_stars(score: float, max_score: float = 5.0) -> dict:
    """スコアを星（★）表示データに変換する。
    - full: 完全に塗られた星の数
    - partial_pct: 部分的に塗られた星の塗り割合(0-100)。0なら部分星なし
    - empty: 空の星の数
    - pct: 全体達成率%
    """
    pct = int(round((score / max_score) * 100))
    # 何個分のスコアか（0.0〜5.0）
    star_value = (score / max_score) * 5.0
    full_stars = int(star_value)                        # 完全な星の数
    remainder = star_value - full_stars                 # 端数（0.0〜0.999）
    partial_pct = int(round(remainder * 100))           # 部分星の塗り割合
    # partial_pctが10%未満は切り捨て（ほぼ0）、90%以上は繰り上げ
    if partial_pct < 10:
        partial_pct = 0
    elif partial_pct >= 90:
        full_stars += 1
        partial_pct = 0
    has_partial = partial_pct > 0
    empty_stars = 5 - full_stars - (1 if has_partial else 0)

    return {
        "full": full_stars,
        "partial_pct": partial_pct,
        "has_partial": has_partial,
        "empty": max(0, empty_stars),
        "pct": pct,
        "value": score
    }


def _encode_image_to_base64(image_bytes: bytes, mime: str = "image/png") -> str:
    """画像バイトをBase64データURIに変換"""
    b64 = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:{mime};base64,{b64}"


def _build_template_context(row: dict, template_type: str,
                             org_name: str = "",
                             logo_b64: str = "",
                             logo_position: str = "center",
                             target_grade: str = "中学生") -> dict:
    """
    テンプレートに渡すコンテキスト辞書を構築する。
    AIが出力するCSVの列名に依存せず、動的にスコアを抽出する。
    """
    from radar_chart import generate_rpg_chart
    
    student_name = row.get("生徒名", "")
    total_score_str = row.get("総合評価", "3.0")
    comment = row.get("総合コメント", row.get("コメント", ""))

    try:
        total_score = float(total_score_str)
        import math
        if math.isnan(total_score):
            total_score = 3.0
    except (ValueError, TypeError):
        total_score = 3.0

    # スコア列と根拠コメントを列順で一括抽出
    raw_items = _get_score_items_with_reasons(row)

    if not raw_items:
        raw_items = [{"label": lbl, "score": 3.0, "reason": ""} for lbl in DEFAULT_SCORE_LABELS]

    # 星・%変換
    total_stars = _score_to_stars(total_score)
    score_items = []
    labels = []
    scores = []
    
    for item in raw_items:
        lbl = item["label"]
        scr = item["score"]
        labels.append(lbl)
        scores.append(scr)
        
        score_items.append({
            "label": lbl,
            "score": scr,
            "stars": _score_to_stars(scr),
            "reason": item["reason"]
        })

    # レーダーチャート生成
    is_premium = "premium" in template_type.lower()
    if is_premium:
        chart_b64 = generate_radar_chart(labels, scores)
    else:
        chart_b64 = generate_radar_chart_light(labels, scores)

    # 総合評価ランク
    if total_score >= 4.5:
        rank = "S"
        rank_color = "#FFD700"
    elif total_score >= 3.5:
        rank = "A"
        rank_color = "#4FC3F7"
    elif total_score >= 2.5:
        rank = "B"
        rank_color = "#81C784"
    else:
        rank = "C"
        rank_color = "#FF8A65"
        
    # 学年別追加データのパース
    extra_data = {}
    rpg_chart_b64 = ""
    if target_grade == "小学生":
        extra_data = {
            "hidden_job": row.get("隠れジョブ", ""),
            "status1_name": row.get("ステータス1名", "ステータス1"),
            "status1_val": row.get("ステータス1値", "0"),
            "status2_name": row.get("ステータス2名", "ステータス2"),
            "status2_val": row.get("ステータス2値", "0"),
            "status3_name": row.get("ステータス3名", "ステータス3"),
            "status3_val": row.get("ステータス3値", "0"),
            "status4_name": row.get("ステータス4名", "ステータス4"),
            "status4_val": row.get("ステータス4値", "0"),
            "status5_name": row.get("ステータス5名", "ステータス5"),
            "status5_val": row.get("ステータス5値", "0"),
            "skill1_name": row.get("スキル1名", ""),
            "skill1_effect": row.get("スキル1効果", ""),
            "skill2_name": row.get("スキル2名", ""),
            "skill2_effect": row.get("スキル2効果", ""),
            "appraisal": row.get("鑑定書", ""),
        }
        # RPG専用レーダーチャート生成 (5角形に変更)
        rpg_labels = [
            extra_data["status1_name"], extra_data["status2_name"], 
            extra_data["status3_name"], extra_data["status4_name"], extra_data["status5_name"]
        ]
        rpg_scores = [
            extra_data["status1_val"], extra_data["status2_val"], 
            extra_data["status3_val"], extra_data["status4_val"], extra_data["status5_val"]
        ]
        # Premium C のようなダークテーマかどうか
        is_dark = "Premium C" in template_type or "Premium A" in template_type
        rpg_chart_b64 = generate_rpg_chart(rpg_labels, rpg_scores, is_dark=is_dark)
        
    elif target_grade == "高校生":
        import json
        career_json_str = row.get("hs_career_json", "")
        career_data = []
        if career_json_str:
            try:
                career_data = json.loads(career_json_str)
            except Exception as e:
                print(f"JSON Parse Error: {e}")
                career_data = []
        extra_data = {
            "career_ranking": career_data
        }
        
    elif target_grade == "中学生":
        import json
        career_json_str = row.get("jhs_career_json", "")
        career_data = {}
        if career_json_str:
            try:
                career_data = json.loads(career_json_str)
            except Exception as e:
                print(f"JHS JSON Parse Error: {e}")
                career_data = {}
        extra_data = {
            "jhs_career": career_data
        }

    return {
        "student_name": student_name,
        "total_score": total_score,
        "total_stars": total_stars,
        "score_items": score_items,
        "labels": labels,
        "scores": scores,
        "comment": comment,
        "chart_b64": chart_b64,
        "rpg_chart_b64": rpg_chart_b64,
        "target_grade": target_grade,
        "extra_data": extra_data,
        "rank": rank,
        "rank_color": rank_color,
        "org_name": org_name,
        "logo_b64": logo_b64,
        "logo_position": logo_position,
        "max_score": 5.0,
    }


def _get_template_filename(template_type: str) -> str:
    """テンプレートタイプ文字列からHTMLファイル名を返す"""
    mapping = {
        "A": "type_a.html",
        "Type A": "type_a.html",
        "B": "type_b.html",
        "Type B": "type_b.html",
        "C": "type_c.html",
        "Type C": "type_c.html",
        "Premium A": "premium_a.html",
        "Premium B": "premium_b.html",
        "Premium C": "premium_c.html",
        "D": "type_d.html",
        "Type D": "type_d.html",
    }
    return mapping.get(template_type, "type_a.html")


def _generate_one_pdf(args: tuple) -> tuple:
    """
    1名分のPDFを生成して返すヘルパー（並列処理用）。
    Returns: (index, student_name, pdf_bytes_or_None, error_msg_or_None)
    """
    idx, row, template_type, org_name, logo_b64, logo_position, custom_layout, target_grade = args
    student_name = row.get("生徒名", "不明")
    try:
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        template_file = _get_template_filename(template_type)
        template = env.get_template(template_file)

        ctx = _build_template_context(
            row=row,
            template_type=template_type,
            org_name=org_name,
            logo_b64=logo_b64,
            logo_position=logo_position,
            target_grade=target_grade
        )
        if custom_layout:
            ctx["custom_layout"] = custom_layout

        html_content = template.render(**ctx)
        pdf_bytes = _html_to_pdf(html_content)
        return (idx, student_name, pdf_bytes, None)
    except Exception:
        return (idx, student_name, None, traceback.format_exc())


def generate_pdfs_as_zip(students_data: list,
                         template_type: str = "A",
                         org_name: str = "",
                         logo_bytes: bytes = None,
                         logo_position: str = "center",
                         custom_layout: dict = None,
                         target_grade: str = "中学生",
                         progress_callback=None,
                         csv_bytes: bytes = None) -> bytes:
    """
    複数の生徒データからPDFを並列生成し、ZIPファイルのバイト列を返す。

    Args:
        students_data: CSVの行データのリスト（dictのリスト）
        template_type: テンプレートの種類（"A", "B", "C", "Premium A" 等）
        org_name: 法人名・学校名
        logo_bytes: ロゴ画像のバイト列（省略可）
        logo_position: ロゴ位置 "center" or "top_right"
        custom_layout: Type D用のカスタムレイアウト設定（dict）
        target_grade: 対象学年
        progress_callback: 進捗通知用コールバック関数 callback(done: int, total: int, name: str)
        csv_bytes: 一緒にZIPに含めるCSVデータのバイト列（省略可）

    Returns:
        ZIPファイルのバイト列
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    logo_b64 = ""
    if logo_bytes:
        logo_b64 = _encode_image_to_base64(logo_bytes)

    n_total = len(students_data)

    # 各生徒の引数タプルを組み立てる
    args_list = [
        (i, row, template_type, org_name, logo_b64, logo_position, custom_layout, target_grade)
        for i, row in enumerate(students_data)
    ]

    # 結果を元の順番で保持
    results = [None] * n_total
    done_count = [0]

    # Playwright（Chromium）はプロセス内で複数インスタンスを起動できるが
    # メモリ消費を抑えるため max_workers=2 に制限
    max_workers = min(2, n_total)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_generate_one_pdf, args): args[0] for args in args_list}
        for future in as_completed(future_map):
            idx, student_name, pdf_bytes, err_msg = future.result()
            results[idx] = (student_name, pdf_bytes, err_msg)
            done_count[0] += 1
            if progress_callback:
                progress_callback(done_count[0], n_total, student_name)

    # 元の順番でZIPに格納
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        if csv_bytes:
            zf.writestr("evaluation_results.csv", csv_bytes)
            
        for student_name, pdf_bytes, err_msg in results:
            if pdf_bytes:
                safe_name = "".join(c for c in student_name if c not in r'\/:*?"<>|')
                zf.writestr(f"{safe_name}_portfolio.pdf", pdf_bytes)
            else:
                zf.writestr(f"{student_name}_ERROR.txt",
                            f"ERROR generating PDF for {student_name}:\n{err_msg}")

    zip_buffer.seek(0)
    return zip_buffer.read()




def generate_single_pdf_bytes(row: dict,
                               template_type: str = "A",
                               org_name: str = "",
                               logo_bytes: bytes = None,
                               logo_position: str = "center",
                               target_grade: str = "中学生") -> bytes:
    """
    1名分のPDFバイト列を返す（プレビュー用）。
    """
    logo_b64 = ""
    if logo_bytes:
        logo_b64 = _encode_image_to_base64(logo_bytes)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template_file = _get_template_filename(template_type)
    template = env.get_template(template_file)

    ctx = _build_template_context(
        row=row,
        template_type=template_type,
        org_name=org_name,
        logo_b64=logo_b64,
        logo_position=logo_position,
        target_grade=target_grade
    )

    html_content = template.render(**ctx)
    return _html_to_pdf(html_content)

