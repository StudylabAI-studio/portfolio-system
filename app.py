"""
app.py - ポートフォリオ一括作成システム
Gemini APIを直接呼び出し、生徒ライフログxルーブリック -> AI評価 -> PDF一括生成
"""
import os
import streamlit as st
import pandas as pd
import traceback
from pathlib import Path
import pdfplumber
from dotenv import load_dotenv

from prompt_builder import parse_ai_csv_output, FIXED_LABELS
from pdf_builder import generate_pdfs_as_zip, generate_single_pdf_bytes
from ai_evaluator import (
    AVAILABLE_MODELS, DEFAULT_MODEL, DEFAULT_RUBRIC,
    group_logs_by_student, evaluate_students_with_gemini,
    evaluate_single_student, results_to_csv_bytes
)


# .env からAPIキーを自動読込（ローカル環境用）
load_dotenv(Path(__file__).parent / ".env")
API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Streamlit Cloud のSecretsからも取得（クラウド環境用）
if not API_KEY:
    try:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except Exception:
        API_KEY = ""


# ─── ページ設定 ───────────────────────────────────────────────
st.set_page_config(
    page_title="ポートフォリオ一括作成システム",
    page_icon="📚", layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS（ライトテーマ） ──────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');
.stApp { font-family:'Noto Sans JP',sans-serif; background:#F4F6FA; }
.stApp, .stApp * { color:#1A2340; }
[data-testid="stAppViewContainer"] { background:#F4F6FA; }
[data-testid="stHeader"] { background:#FFFFFF; border-bottom:1px solid #DDE3EE; }
[data-testid="stSidebar"] { background:#FFFFFF; border-right:1px solid #DDE3EE; }
[data-testid="stSidebar"] * { color:#1A2340 !important; }
[data-testid="stSidebar"] h3,[data-testid="stSidebar"] h4 { color:#1565C0 !important; font-weight:700; }
.main-title { font-size:2rem; font-weight:700; color:#1565C0; text-align:center; padding:1.2rem 0 0.3rem; }
.sub-title { font-size:0.92rem; color:#455A8A; text-align:center; margin-bottom:1.5rem; font-weight:500; }
[data-testid="stTabs"] button { color:#455A8A !important; font-weight:600; }
[data-testid="stTabs"] button[aria-selected="true"] { color:#1565C0 !important; border-bottom:3px solid #1565C0; }
h1,h2,h3,h4,h5 { color:#1A2340 !important; font-weight:700; }
p,span,label,div { color:#2C3E60; }
.info-box { background:#EBF3FF; border-left:4px solid #1565C0; border-radius:8px; padding:.8rem 1rem; margin:.7rem 0; color:#1A2340; font-size:.9rem; font-weight:500; }
.success-box { background:#EAF7ED; border-left:4px solid #2E7D32; border-radius:8px; padding:.8rem 1rem; margin:.7rem 0; color:#1A3A1A; font-size:.9rem; font-weight:500; }
.warn-box { background:#FFF8E1; border-left:4px solid #F9A825; border-radius:8px; padding:.8rem 1rem; margin:.7rem 0; color:#4A3000; font-size:.9rem; font-weight:500; }
.stat-card { background:#FFFFFF; border:1px solid #DDE3EE; border-radius:12px; padding:1rem; text-align:center; }
.stat-num { font-size:2rem; font-weight:700; color:#1565C0; }
.stat-label { font-size:.8rem; color:#78909C; margin-top:2px; }
.stButton>button { background:#1565C0; color:#FFFFFF !important; border:none; border-radius:10px; padding:.55rem 1.2rem; font-weight:700; font-size:.92rem; transition:all .25s; box-shadow:0 2px 8px rgba(21,101,192,.2); }
.stButton>button:hover { background:#1976D2; transform:translateY(-2px); box-shadow:0 6px 16px rgba(21,101,192,.3); }
[data-testid="stFileUploader"] { background:#FFFFFF; border:2px dashed #90B8E8; border-radius:10px; padding:.4rem; }
[data-testid="stFileUploader"] * { color:#1A2340 !important; }
textarea { background:#FFFFFF !important; color:#1A2340 !important; border:1px solid #C5D5EA !important; border-radius:8px !important; }
div[data-testid="stExpander"] { background:#FFFFFF; border:1px solid #DDE3EE; border-radius:10px; }
[data-testid="stRadio"] label { color:#1A2340 !important; font-weight:500; }
</style>
""", unsafe_allow_html=True)

# ─── ヘッダー ────────────────────────────────────────────────
st.markdown('<div class="main-title">📚 ポートフォリオ一括作成システム</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">ライフログ CSV × ルーブリック → Gemini AI 自動評価 → PDF 一括出力</div>', unsafe_allow_html=True)

# ─── セッション状態初期化 ─────────────────────────────────────
if "eval_results" not in st.session_state:
    st.session_state.eval_results = []
if "students_list" not in st.session_state:
    st.session_state.students_list = []
if "eval_running" not in st.session_state:
    st.session_state.eval_running = False
if "eval_queue" not in st.session_state:
    st.session_state.eval_queue = []
if "eval_errors" not in st.session_state:
    st.session_state.eval_errors = []
if "stop_eval" not in st.session_state:
    st.session_state.stop_eval = False


# ─── サイドバー ───────────────────────────────────────────────
with st.sidebar:
    # APIキー状態表示（キー自体は表示しない）
    _key_valid = bool(API_KEY) and len(API_KEY) > 20 and not API_KEY.startswith("ここ")
    if _key_valid:
        st.success("🔑 APIキー：設定済み")
    else:
        st.error("🔑 APIキー：未設定")
        st.caption(".env ファイルに GEMINI_API_KEY を記入してください")

    st.markdown("### 🤖 AIモデル設定")
    selected_model = st.selectbox(
        "使用モデル",
        options=list(AVAILABLE_MODELS.keys()),
        format_func=lambda x: AVAILABLE_MODELS[x],
        index=0,
        help="通常は推奨モデルのままで十分です"
    )

    st.markdown("---")
    st.markdown("### ⚙️ 共通設定")
    org_name = st.text_input("法人名・学校名", placeholder="例：〇〇学園")
    logo_file = st.file_uploader("ロゴ画像（任意）", type=["png","jpg","jpeg"])
    logo_position = st.radio("ロゴ位置", ["中央（透かし）","右上（ヘッダー）"], horizontal=True)
    logo_pos_key = "center" if "中央" in logo_position else "top_right"

    st.markdown("---")
    st.markdown("### 🎨 PDFテンプレート")
    template_type = st.selectbox(
        "デザイン選択",
        options=["A","B","C","Premium A","Premium B","Premium C"],
        format_func=lambda x: {
            "A":"Type A：分析・評価サポート型",
            "B":"Type B：ルーブリック評価型（賞状風）",
            "C":"Type C：モダンUI・ダッシュボード型",
            "Premium A":"✨ Premium A：ダークブルー×ゴールド",
            "Premium B":"✨ Premium B：ライトブルー×アクリル",
            "Premium C":"✨ Premium C：ディープネイビー×シルバー",
        }.get(x, x)
    )

    st.markdown("---")
    st.markdown("### 🎓 対象学年（分析レポート用）")
    target_grade = st.radio(
        "学年カテゴリ",
        ["小学生", "中学生", "高校生"],
        index=0,
        help="対象学年に応じた分析（職業提案やRPG風ステータス）が2ページ目に出力されます。"
    )

    st.markdown("---")
    st.markdown("### 📊 評価項目モード")
    use_rubric_items = st.radio(
        "評価軸",
        [False, True],
        format_func=lambda x: "ルーブリックの項目をそのまま使う" if x else f"固定5項目（{FIXED_LABELS[0]}等）"
    )


# ─── タブ ────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📂 Step 1：ライフログ読込",
    "🤖 Step 2：AI自動評価",
    "📄 Step 3：PDF一括生成"
])

# ════════════════════════════════════════════════════════════
# Step 1：ライフログ読込 & ルーブリック設定
# ════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Step 1：ライフログ & ルーブリックの読み込み")
    st.markdown("""
    <div class="info-box">
    📌 Feelnoteからエクスポートしたライフログ CSV をアップロードしてください。<br>
    生徒1人が複数のログを書いていても、<b>ユーザーIDで自動的に束ねて</b>AIに渡します。
    </div>
    """, unsafe_allow_html=True)

    col_log, col_rubric = st.columns(2)

    with col_log:
        st.markdown("#### 📖 ライフログ CSV")
        log_file = st.file_uploader(
            "ライフログCSVをアップロード",
            type=["csv"], key="log_file_upload",
            help="FeelnoteからエクスポートしたライフログのCSVファイル（ms932/Shift-JIS対応）"
        )

        if log_file:
            try:
                # エンコーディング自動判定
                raw = log_file.read()
                for enc in ["ms932", "utf-8-sig", "utf-8", "cp932"]:
                    try:
                        df_logs = pd.read_csv(pd.io.common.BytesIO(raw), encoding=enc)
                        break
                    except Exception:
                        continue

                # 生徒ごとにグループ化
                students_list = group_logs_by_student(df_logs)
                st.session_state.students_list = students_list

                total_logs = sum(s["log_count"] for s in students_list)

                st.markdown(f"""
                <div class="success-box">
                ✅ 読み込み完了！<br>
                👤 生徒数：<b>{len(students_list)}名</b>　／　
                📝 ライフログ総数：<b>{total_logs}件</b>
                </div>
                """, unsafe_allow_html=True)

                # 統計カード
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f'<div class="stat-card"><div class="stat-num">{len(students_list)}</div><div class="stat-label">生徒数</div></div>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f'<div class="stat-card"><div class="stat-num">{total_logs}</div><div class="stat-label">ライフログ総数</div></div>', unsafe_allow_html=True)
                with c3:
                    avg = round(total_logs / len(students_list), 1) if students_list else 0
                    st.markdown(f'<div class="stat-card"><div class="stat-num">{avg}</div><div class="stat-label">1人あたり平均件数</div></div>', unsafe_allow_html=True)

                # 生徒一覧プレビュー
                with st.expander("👥 生徒一覧を確認する", expanded=False):
                    preview_df = pd.DataFrame([
                        {"氏名": s["name"], "ライフログ件数": s["log_count"], "グループ": s["group"]}
                        for s in students_list
                    ])
                    st.dataframe(preview_df, use_container_width=True, height=300)

            except Exception as e:
                st.error(f"ファイル読み込みエラー: {traceback.format_exc()}")

    with col_rubric:
        st.markdown("#### 📋 ルーブリック")
        rubric_file = st.file_uploader(
            "ルーブリックをアップロード",
            type=["csv","xlsx","txt","pdf"], key="rubric_file_upload",
            help="学校・法人が定めた評価基準ファイル（CSV/Excel/PDF/TXT）"
        )

        rubric_text = ""
        if rubric_file:
            try:
                if rubric_file.name.endswith(".pdf"):
                    with pdfplumber.open(rubric_file) as pdf:
                        for page in pdf.pages:
                            rubric_text += page.extract_text() or ""
                elif rubric_file.name.endswith(".xlsx"):
                    import openpyxl
                    wb = openpyxl.load_workbook(rubric_file)
                    ws = wb.active
                    all_rows_xl = list(ws.iter_rows(values_only=True))
                    # 「観点」列（列C = index 2）からヘッダー行を除いた評価項目名を取得
                    rubric_labels = []
                    for ri, row in enumerate(all_rows_xl):
                        if ri == 0:
                            continue  # ヘッダー行はスキップ
                        if row and len(row) > 2 and row[2] is not None:
                            label = str(row[2]).strip()
                            if label:
                                rubric_labels.append(label)
                    st.session_state["rubric_item_labels"] = rubric_labels
                    # テキスト化（AIへの参照用）
                    df_r = pd.read_excel(rubric_file)
                    rubric_text = df_r.to_string(index=False)
                elif rubric_file.name.endswith(".csv"):
                    for enc in ["utf-8-sig","ms932","utf-8"]:
                        try:
                            df_r = pd.read_csv(rubric_file, encoding=enc)
                            rubric_text = df_r.to_string(index=False)
                            break
                        except Exception:
                            rubric_file.seek(0)
                else:
                    rubric_text = rubric_file.read().decode("utf-8", errors="ignore")

                st.session_state["rubric_text"] = rubric_text
                labels_found = st.session_state.get("rubric_item_labels", [])
                if labels_found:
                    st.success(f"✅ ルーブリック読み込み完了（評価項目{len(labels_found)}つ）")
                    st.info(f"📌 評価項目：{' ／ '.join(labels_found)}")
                else:
                    st.success(f"✅ ルーブリック読み込み完了（{len(rubric_text)}文字）")
                with st.expander("📄 ルーブリック内容を確認"):
                    st.text(rubric_text[:1500] + ("..." if len(rubric_text) > 1500 else ""))

            except Exception as e:
                st.error(f"ルーブリック読み込みエラー: {e}")

    # ルーブリックは任意なのでブロックしない
    if not st.session_state.students_list:
        st.markdown("""
        <div class="warn-box">
        ⬆️ まずライフログCSVをアップロードしてください。
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# Step 2：AI自動評価
# ════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Step 2：Gemini AIによる自動評価")

    students_list = st.session_state.get("students_list", [])
    rubric_text = st.session_state.get("rubric_text", "")
    
    # ルーブリック未アップロードの場合はデフォルトを使用
    effective_rubric = rubric_text if rubric_text.strip() else DEFAULT_RUBRIC
    using_default_rubric = not rubric_text.strip()

    if not students_list:
        st.markdown('<div class="warn-box">⚠️ Step 1でライフログCSVを読み込んでください。</div>', unsafe_allow_html=True)
    elif not (bool(API_KEY) and len(API_KEY) > 20 and not API_KEY.startswith("ここ")):
        st.markdown('<div class="warn-box">⚠️ .env ファイルに GEMINI_API_KEY を記入してアプリを再起動してください。</div>', unsafe_allow_html=True)
    else:
        if using_default_rubric:
            st.markdown('<div class="warn-box">📋 ルーブリック未読込 → 搭載されている「基本的な評価基準（5項目）」で評価します</div>', unsafe_allow_html=True)

        st.markdown(f"""
        <div class="info-box">
        🤖 <b>{AVAILABLE_MODELS[selected_model]}</b> で評価します。<br>
        対象：<b>{len(students_list)}名</b>　／　
        評価軸：<b>{"ルーブリック準拠" if use_rubric_items and not using_default_rubric else "固定5項目"}</b>
        </div>
        """, unsafe_allow_html=True)

        # 評価対象の絞り込み
        with st.expander("⚙️ 評価対象を絞り込む（任意）", expanded=False):

            # ── グループ一覧を取得 ──
            all_groups = sorted(set(
                g.strip()
                for s in students_list
                for g in (s.get("group") or "").split(",")
                if g.strip()
            ))

            col_grp, col_ind = st.columns([1, 1])

            with col_grp:
                st.markdown("**① グループで絞り込む**")
                selected_groups = st.multiselect(
                    "グループを選択（未選択 = 全グループ）",
                    options=all_groups,
                    default=[],
                    key="filter_groups"
                )

            # グループで絞った生徒リスト
            if selected_groups:
                group_filtered = [
                    s for s in students_list
                    if any(
                        g in selected_groups
                        for g in s.get("groups", s.get("group", "").split(","))
                    )
                ]
            else:
                group_filtered = students_list


            with col_ind:
                st.markdown("**② 個人で絞り込む（任意）**")
                filtered_names = [s["name"] for s in group_filtered]
                selected_names = st.multiselect(
                    "生徒を個別選択（未選択 = 上記全員）",
                    options=filtered_names,
                    default=[],
                    key="filter_names"
                )

            # 最終的な評価対象
            if selected_names:
                target_students = [s for s in group_filtered if s["name"] in selected_names]
            else:
                target_students = group_filtered

            # 対象人数の表示
            if selected_groups:
                grp_label = " ／ ".join(selected_groups)
                st.caption(f"📌 グループ：{grp_label}　→　評価対象：**{len(target_students)}名**")
            else:
                st.caption(f"評価対象：**{len(target_students)}名**（全員）")


        # ── 評価実行中 ─────────────────────────────────────────────
        if st.session_state.get("eval_running", False):
            import threading
            from concurrent.futures import ThreadPoolExecutor, as_completed

            target_all = st.session_state.get("eval_target", [])
            n_total = len(target_all)
            expected_headers = st.session_state.get("eval_headers", None)

            progress_bar = st.progress(0.0, text=f"⏳ 評価を開始しています…（{n_total}名）")
            status_text = st.empty()
            stop_col, _ = st.columns([1, 3])
            with stop_col:
                if st.button("⏹️ 評価をSTOPする", type="secondary", use_container_width=True, key="stop_btn"):
                    st.session_state.stop_eval = True
                    st.session_state.eval_running = False
                    st.warning("⏹️ 評価を中断しました")
                    st.rerun()

            completed_count = [0]
            lock = threading.Lock()
            results_ordered = [None] * n_total
            errors_list = []
            stop_event = threading.Event()

            def _eval_one(idx, student):
                import time
                if stop_event.is_set():
                    return idx, None, None
                time.sleep(0.3 * (idx % 3))
                result, err = evaluate_single_student(
                    student=student,
                    rubric_text=effective_rubric,
                    api_key=API_KEY,
                    model_name=selected_model,
                    use_rubric_items=use_rubric_items,
                    target_grade=target_grade,
                    expected_headers=expected_headers
                )
                with lock:
                    completed_count[0] += 1
                return idx, result, err

            max_workers = min(3, n_total) if n_total > 0 else 1
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_eval_one, i, s) for i, s in enumerate(target_all)]
                for future in as_completed(futures):
                    if st.session_state.get("stop_eval", False):
                        stop_event.set()
                        break
                    idx, result, err = future.result()
                    if result is not None:
                        results_ordered[idx] = result
                    if err:
                        errors_list.append(err)
                    done = completed_count[0]
                    pct = done / n_total if n_total > 0 else 1.0
                    progress_bar.progress(pct, text=f"⏳ {done}/{n_total}名完了")
                    names_done = [s["name"] for s in target_all[:done]]
                    status_text.caption(f"完了：{' / '.join(names_done[-3:])}{'...' if done > 3 else ''}")

            st.session_state.eval_results = [r for r in results_ordered if r is not None]
            st.session_state.eval_errors = errors_list
            st.session_state.eval_running = False
            st.session_state.eval_queue = []
            n_done = len(st.session_state.eval_results)
            if n_done > 0:
                st.success(f"🎉 評価完了！{n_done}名分の評価結果が生成されました。")
            if errors_list:
                with st.expander("⚠️ エラー詳細"):
                    for e in errors_list:
                        st.warning(e)
            st.rerun()

        # ── 評価待機中 ──────────────────────────────────────────────
        else:
            col_run, col_dl = st.columns([2, 1])
            with col_run:
                run_btn = st.button(
                    f"🚀 AI評価を開始する（{len(target_students)}名）",
                    use_container_width=True,
                    type="primary"
                )

            if run_btn:
                # 評価ターゲットの初期化
                st.session_state.eval_results = []
                st.session_state.eval_errors = []
                st.session_state.eval_target = list(target_students)  # 並列処理用：全対象を保存
                st.session_state.eval_queue = []  # 旧方式との互換性のため
                st.session_state.eval_running = True
                st.session_state.stop_eval = False

                # ── ルーブリック項目名から固定ヘッダーを事前に組み立てる ──
                rubric_labels = st.session_state.get("rubric_item_labels", [])
                if use_rubric_items and rubric_labels:
                    fixed_headers = ["生徒名", "総合評価", "総合コメント"]
                    for label in rubric_labels:
                        fixed_headers.append(label)
                        fixed_headers.append(f"{label}_根拠")
                    st.session_state.eval_headers = fixed_headers
                elif "eval_headers" in st.session_state:
                    del st.session_state["eval_headers"]

                st.rerun()


        # 結果表示・ダウンロード
        if st.session_state.eval_results:
            results = st.session_state.eval_results
            st.markdown("#### 📊 評価結果プレビュー")
            st.dataframe(pd.DataFrame(results), use_container_width=True, height=300)

            csv_bytes = results_to_csv_bytes(results)
            st.download_button(
                label="⬇️ 評価結果CSVをダウンロード",
                data=csv_bytes,
                file_name="evaluation_results.csv",
                mime="text/csv",
                use_container_width=True
            )

        # 手動貼り付けオプション
        st.markdown("---")
        with st.expander("📋 または：AI評価結果を手動で貼り付ける"):
            pasted = st.text_area(
                "AIが出力したCSVテキストを貼り付け",
                height=200,
                placeholder="生徒名,総合評価,自己管理,...,コメント\n山田太郎,4.2,...",
            )
            if st.button("解析する", key="parse_manual"):
                parsed = parse_ai_csv_output(pasted)
                if parsed:
                    st.session_state.eval_results = parsed
                    st.success(f"✅ {len(parsed)}名分を読み込みました")
                    st.dataframe(pd.DataFrame(parsed), use_container_width=True)
                else:
                    st.error("解析失敗。CSV形式を確認してください。")

# ════════════════════════════════════════════════════════════
# Step 3：PDF一括生成
# ════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Step 3：PDF一括生成")

    eval_results = st.session_state.get("eval_results", [])

    if not eval_results:
        st.markdown('<div class="warn-box">⚠️ Step 2でAI評価を実行するか、評価結果CSVをアップロードしてください。</div>', unsafe_allow_html=True)

        # 既存CSVからのアップロード
        st.markdown("#### または：評価済みCSVをアップロード")
        uploaded_eval = st.file_uploader("評価結果CSV", type=["csv"], key="eval_upload")
        if uploaded_eval:
            content = uploaded_eval.read().decode("utf-8-sig", errors="ignore")
            rows = parse_ai_csv_output(content)
            if rows:
                st.session_state.eval_results = rows
                st.success(f"✅ {len(rows)}名分を読み込みました")
                st.dataframe(pd.DataFrame(rows).head(5), use_container_width=True)
            else:
                st.error("CSVの解析に失敗しました")
    else:
        st.markdown(f"""
        <div class="success-box">
        ✅ <b>{len(eval_results)}名分</b>の評価結果が読み込まれています。
        テンプレートを選択してPDFを生成してください。
        </div>
        """, unsafe_allow_html=True)

        st.dataframe(pd.DataFrame(eval_results).head(5), use_container_width=True)

        st.markdown("---")
        col_preview, col_all = st.columns([1, 2])

        with col_preview:
            if st.button("👁️ 1名分プレビュー", use_container_width=True):
                with st.spinner("プレビュー生成中..."):
                    try:
                        logo_bytes = logo_file.read() if logo_file else None
                        pdf_bytes = generate_single_pdf_bytes(
                            row=eval_results[0],
                            template_type=template_type,
                            org_name=org_name,
                            logo_bytes=logo_bytes,
                            logo_position=logo_pos_key,
                            target_grade=target_grade
                        )
                        name = eval_results[0].get("生徒名", "preview")
                        st.download_button(
                            f"⬇️ {name} のPDF",
                            data=pdf_bytes,
                            file_name=f"{name}_preview.pdf",
                            mime="application/pdf"
                        )
                        st.success("プレビュー生成完了！")
                    except Exception as e:
                        st.error(f"エラー: {traceback.format_exc()}")

        with col_all:
            if st.button(f"🚀 全{len(eval_results)}名分のPDFを一括生成", use_container_width=True):
                try:
                    logo_bytes = logo_file.read() if logo_file else None
                    n_pdf = len(eval_results)

                    pdf_progress = st.progress(0.0, text=f"⏳ PDFを生成しています… 0/{n_pdf}名")
                    pdf_status = st.empty()

                    def _pdf_callback(done, total, name):
                        pct = done / total
                        pdf_progress.progress(pct, text=f"⏳ PDF生成中… {done}/{total}名完了")
                        pdf_status.caption(f"✅ 完了：{name}")

                    csv_bytes_for_zip = results_to_csv_bytes(eval_results)
                    
                    zip_bytes = generate_pdfs_as_zip(
                        students_data=eval_results,
                        template_type=template_type,
                        org_name=org_name,
                        logo_bytes=logo_bytes,
                        logo_position=logo_pos_key,
                        target_grade=target_grade,
                        progress_callback=_pdf_callback,
                        csv_bytes=csv_bytes_for_zip
                    )
                    pdf_progress.progress(1.0, text="✅ PDF生成完了！")
                    pdf_status.empty()

                    st.markdown('<div class="success-box">🎉 PDF一括生成完了！ZIPファイルをダウンロードしてください。</div>', unsafe_allow_html=True)
                    st.download_button(
                        f"⬇️ 全{len(eval_results)}名分 PDF（ZIP）",
                        data=zip_bytes,
                        file_name="portfolios.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                except Exception as e:
                    progress.empty()
                    st.error(f"PDF生成エラー: {traceback.format_exc()}")
