"""
radar_chart.py
レーダーチャートをBase64エンコードされたPNG画像として生成するモジュール。
青基調・クモの巣状の多角形グリッドを採用したプロフェッショナルなデザイン。
"""
import io
import base64
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.font_manager as fm


def _get_jp_font():
    """Windows/Mac/Linuxで利用可能な日本語フォントを取得する。"""
    candidates = [
        'Yu Gothic', 'YuGothic', 'Meiryo', 'MS Gothic',
        'Hiragino Sans', 'Noto Sans CJK JP', 'Noto Sans JP',
        'IPAexGothic', 'TakaoGothic', 'VL Gothic'
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            return name
    return None


JP_FONT = _get_jp_font()


def generate_radar_chart(labels: list, scores: list, max_score: float = 5.0, bg_color: str = "#0d1b2a") -> str:
    """
    レーダーチャートを生成し、Base64エンコードされたPNG文字列を返す。

    Args:
        labels: 評価項目名のリスト
        scores: 評価スコアのリスト（labelsと同じ順序）
        max_score: 最大スコア（デフォルト5.0）
        bg_color: 背景色（16進数カラーコード）

    Returns:
        Base64エンコードされたPNG画像文字列（data:image/png;base64,... 形式）
    """
    if not labels or not scores:
        return ""

    N = len(labels)
    if N < 3:
        while len(labels) < 3:
            labels.append("")
            scores.append(0)
        N = 3

    # スコアを正規化
    scores_norm = [min(float(s), max_score) / max_score for s in scores]

    # 角度計算（12時方向から開始、時計回り）
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles_plot = angles + [angles[0]]
    scores_plot = scores_norm + [scores_norm[0]]

    # --- 描画 ---
    fig = plt.figure(figsize=(5.5, 5.5), facecolor=bg_color)
    ax = fig.add_subplot(111, polar=True, facecolor=bg_color)

    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)

    # グリッド（クモの巣状） - 目盛りが見えるように濃くする
    levels = [0.2, 0.4, 0.6, 0.8, 1.0]
    for level in levels:
        ax.plot(angles + [angles[0]], [level] * (N + 1),
                color='#2a5fa0', linewidth=1.0, alpha=0.9, linestyle='-')
        # 目盛り数値を表示
        ax.text(angles[0], level, f'{level * max_score:.0f}',
                ha='center', va='bottom', color='#7ab0e0', fontsize=6,
                **({'fontfamily': JP_FONT} if JP_FONT else {}))

    # スポークライン（中心から各頂点へ）
    for angle in angles:
        ax.plot([angle, angle], [0, 1],
                color='#2a5fa0', linewidth=0.8, alpha=0.8)

    # データエリア塗りつぶし - 透過性を上げて目盛りが見えるように
    ax.fill(angles_plot[:-1], scores_plot[:-1],
            alpha=0.15, color='#2196F3')  # ← 0.35→0.15 に変更

    # データライン
    ax.plot(angles_plot, scores_plot,
            color='#42A5F5', linewidth=2.5, linestyle='solid',
            path_effects=[pe.withStroke(linewidth=4, foreground='#1565C0')])

    # 頂点マーカー
    ax.scatter(angles, scores_norm,
               s=60, color='#BBDEFB', zorder=5,
               edgecolors='#42A5F5', linewidth=1.5)

    # ラベルと数値 - 日本語フォント指定
    ax.set_xticks(angles)
    label_texts = [f"{label}\n{float(score):.1f}" for label, score in zip(labels, scores)]

    font_props = {}
    if JP_FONT:
        font_props['fontfamily'] = JP_FONT

    ax.set_xticklabels(label_texts,
                       color='#E3F2FD', fontsize=8.5,
                       fontweight='bold',
                       **font_props)

    # Y軸非表示
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.yaxis.set_visible(False)

    ax.spines['polar'].set_visible(False)
    ax.grid(False)
    ax.set_frame_on(False)

    plt.tight_layout(pad=0.5)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150,
                bbox_inches='tight',
                facecolor=bg_color,
                transparent=False)
    plt.close(fig)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    return f"data:image/png;base64,{img_b64}"


def generate_radar_chart_light(labels: list, scores: list, max_score: float = 5.0) -> str:
    """
    白背景版のレーダーチャート（Type A, B, C 向け）。
    """
    if not labels or not scores:
        return ""

    N = len(labels)
    if N < 3:
        while len(labels) < 3:
            labels.append("")
            scores.append(0)
        N = 3

    scores_norm = [min(float(s), max_score) / max_score for s in scores]
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles_plot = angles + [angles[0]]
    scores_plot = scores_norm + [scores_norm[0]]

    fig = plt.figure(figsize=(5, 5), facecolor='white')
    ax = fig.add_subplot(111, polar=True, facecolor='#F8FAFF')
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)

    # グリッド - 目盛りが見えるように濃くする
    levels = [0.2, 0.4, 0.6, 0.8, 1.0]
    for level in levels:
        ax.plot(angles + [angles[0]], [level] * (N + 1),
                color='#90CAF9', linewidth=1.0, linestyle='-', alpha=1.0)
        ax.text(angles[0], level, f'{level * max_score:.0f}',
                ha='center', va='bottom', color='#5090C0', fontsize=6,
                **({'fontfamily': JP_FONT} if JP_FONT else {}))

    for angle in angles:
        ax.plot([angle, angle], [0, 1], color='#BBDEFB', linewidth=0.8)

    # 透過性を上げる
    ax.fill(angles_plot[:-1], scores_plot[:-1], alpha=0.15, color='#1976D2')  # ← 0.25→0.15
    ax.plot(angles_plot, scores_plot, color='#1976D2', linewidth=2.2)
    ax.scatter(angles, scores_norm, s=50, color='#1976D2', zorder=5)

    label_texts = [f"{l}\n{float(s):.1f}" for l, s in zip(labels, scores)]
    ax.set_xticks(angles)

    font_props = {}
    if JP_FONT:
        font_props['fontfamily'] = JP_FONT

    ax.set_xticklabels(label_texts, color='#1A237E', fontsize=8,
                       fontweight='bold', **font_props)

    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.yaxis.set_visible(False)
    ax.spines['polar'].set_visible(False)
    ax.grid(False)
    ax.set_frame_on(False)

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', transparent=False)
    plt.close(fig)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    return f"data:image/png;base64,{img_b64}"


def generate_rpg_chart(labels: list, scores: list, is_dark: bool = False) -> str:
    """
    小学生向けRPG風ステータス（5項目）のレーダーチャートを生成する。
    MAX100を前提とし、ゲーム風のポップなデザインで描画。
    """
    if not labels or not scores or len(labels) < 5:
        return ""
    
    # 最初の5項目だけ使用
    labels = labels[:5]
    scores = [min(100.0, max(0.0, float(s))) for s in scores[:5]]
    max_score = 100.0
    N = 5

    scores_norm = [s / max_score for s in scores]
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles_plot = angles + [angles[0]]
    scores_plot = scores_norm + [scores_norm[0]]

    bg_color = '#1A1A24' if is_dark else '#F0F4F8'
    grid_color = '#4A4A6A' if is_dark else '#B0BEC5'
    fill_color = '#FF4081'  # ポップなピンク系
    line_color = '#FF80AB'
    text_color = '#FFFFFF' if is_dark else '#37474F'

    fig = plt.figure(figsize=(4.5, 4.5), facecolor=bg_color)
    ax = fig.add_subplot(111, polar=True, facecolor=bg_color)
    
    # 頂点を上に（三角形が上を向くように）
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)

    # グリッド（25, 50, 75, 100）
    levels = [0.25, 0.5, 0.75, 1.0]
    for level in levels:
        ax.plot(angles + [angles[0]], [level] * (N + 1),
                color=grid_color, linewidth=1.5, linestyle='--', alpha=0.7)

    # スポークライン
    for angle in angles:
        ax.plot([angle, angle], [0, 1], color=grid_color, linewidth=1.5, alpha=0.7)

    # データ描画
    ax.fill(angles_plot[:-1], scores_plot[:-1], alpha=0.3, color=fill_color)
    ax.plot(angles_plot, scores_plot, color=line_color, linewidth=3)
    
    # 頂点マーカー（星型など）
    ax.scatter(angles, scores_norm, s=150, marker='*', color='#FFD54F', zorder=5, edgecolors='#FF6F00', linewidth=1.5)

    # ラベルと数値
    ax.set_xticks(angles)
    label_texts = [f"{l}\n{int(s)}" for l, s in zip(labels, scores)]
    
    font_props = {}
    if JP_FONT:
        font_props['fontfamily'] = JP_FONT

    ax.set_xticklabels(label_texts, color=text_color, fontsize=10, fontweight='bold', **font_props)

    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.yaxis.set_visible(False)
    ax.spines['polar'].set_visible(False)
    ax.grid(False)
    ax.set_frame_on(False)

    plt.tight_layout(pad=1.0)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor=bg_color, transparent=False)
    plt.close(fig)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    return f"data:image/png;base64,{img_b64}"

