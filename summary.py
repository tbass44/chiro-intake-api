"""
summary.py

intake payload（dict）から
管理者向け summary を作成するロジック

ここは FastAPI の中でも
「ビジネスロジック担当」

👉 フロントの構造が変わっても
👉 DB構造を変えず
👉 ここだけ直せば吸収できるようにする
"""

from typing import Optional
from schemas import AdminIntakeSummary
import json
import os
import requests
from datetime import datetime

def build_admin_summary(payload: dict) -> AdminIntakeSummary:
    """
    intake payload から管理者向け summary を生成する

    payload:
      - JSON を dict にしたもの
      - フロントから送られてきた「生データ」

    戻り値:
      - AdminIntakeSummary（構造化された summary）
    """
    # まず代入する
    chief_complaints = _extract_main_complaints(payload)
    # その後なら使える
    print("DEBUG chief:", chief_complaints)

    # ここで文字列配列に変換する
    chief_complaints = _extract_main_complaints(payload)
    # 注意すべき所見（red flags）
    # 「評価」ではなく「存在チェック」だけ
    red_flags = _extract_red_flags(payload)
    # sleepHours（数値）から事実ベースで判定する
    sleep_hours = payload.get("sleepHours")
    # None の可能性があるので直接比較しない
    sleep_trouble = True if sleep_hours is not None and sleep_hours < 5 else None

    # --- summary オブジェクトを組み立てて返す ---
    return AdminIntakeSummary(
        chief_complaints=chief_complaints,
        symptom_duration=None,  # v2では未定義（将来用）
        red_flags=red_flags,
        sleep_trouble=sleep_trouble,
        stress_level=_normalize_stress_level(payload.get("stressLevel")),
        clinical_focus=_determine_clinical_focus(
            chief_complaints=chief_complaints,
            red_flags=red_flags,
            sleep_trouble=sleep_trouble,
        ),
    )

def _extract_main_complaints(payload: dict) -> list[str]:
    """
    主訴の抽出（v2対応）

    payload["symptoms"] は
    [
      { "symptom": "腰痛", ... },
      { "symptom": "首こり", ... }
    ]
    という構造

    → ["腰痛", "首こり"] に変換する
    """
    # payload から symptoms を取得。キーがなくてもエラーにならない
    symptoms = payload.get("symptoms", [])
     # まず型を守る
    if not isinstance(symptoms, list):
        return []
    # ここで list を作る
    result: list[str] = []

    for s in symptoms:
        if isinstance(s, dict):
            symptom = s.get("symptom")
            if symptom:
                result.append(symptom)

    return result

def _extract_red_flags(payload: dict) -> list[str]:
    """
    管理者が注意すべきフラグの抽出
    ・推測しない
    ・評価しない
    ・存在チェックのみ
    """
    flags: list[str] = []

    if payload.get("medicalHistory"):
        flags.append("既往歴あり")
    # 将来 symptoms[].severity が高い場合なども追加可能
    return flags

def _determine_clinical_focus(
    chief_complaints: list[str],
    red_flags: list[str],
    sleep_trouble: Optional[bool],
) -> Optional[str]:
    """
    施術者が一瞬で方針を立てるための補助ラベル

    ・文章生成ではない
    ・if 文によるルールベース
    ・CSV / 管理画面 / 将来AIの土台
    """

    # 危険サインがあれば最優先
    if red_flags:
        return "注意所見あり（評価優先）"

    # 自律神経系の影響が強そうな場合
    if sleep_trouble:
        return "自律神経アプローチ優先"

    # 主訴ベースの即判断
    if "腰痛" in chief_complaints:
        return "骨盤・下肢連動評価"

    if "首こり" in chief_complaints or "肩こり" in chief_complaints:
        return "頚肩部・姿勢評価"

    # どれにも当てはまらない場合
    return "全身バランス評価"

def _normalize_stress_level(value) -> str | None:
    """
    数値 or 文字列で来る stressLevel を
    low / middle / high に正規化する
    - 想定外の値は None
    """
    if value is None:
        return None

    # 数値で来た場合
    if isinstance(value, int):
        if value <= 2:
            return "low"
        if value == 3:
            return "middle"
        if value >= 4:
            return "high"

    # すでに文字列で来ている場合（将来変更に備える）
    if isinstance(value, str):
        return value

    return None


# ============================================================
# ユーザー向けAI要約用の入力データを作る
# ============================================================
def build_user_ai_input(admin: AdminIntakeSummary) -> dict:
    """
    【この関数の役割】

    管理者向けに作られた summary（AdminIntakeSummary）を受け取り、
    ユーザー向けAI要約に「安全に使える材料」だけを取り出す。

    ・診断しない
    ・評価しない
    ・文章は作らない
    ・AIに考えさせない

    あくまで「事実と特徴を並べるだけ」。

    【引数】
    admin:
        build_admin_summary() で作られた
        AdminIntakeSummary オブジェクト

    【戻り値】
    dict:
        AIにそのまま渡せる安全な入力データ
    """

    main_complaints = admin.chief_complaints[:]  # そのまま（入力事実）
    body_areas = _infer_body_areas(main_complaints)  # 上半身/下半身/広範囲
    context_factors = _build_user_context_factors(admin)  # 生活背景（睡眠/負担など）
    attention_points = _build_user_attention_points(admin)  # 注意観点（不安を煽らない）

    return {
        "main_complaints": main_complaints,
        "body_areas": body_areas,
        "context_factors": context_factors,
        "attention_points": attention_points,
        "notes": [
            "これは医療的な診断ではなく、入力内容を整理したものです。",
            "最終的な判断は来院時に状態を確認しながら行います。",
        ],
    }

def _infer_body_areas(complaints: list[str]) -> list[str]:
    """
    症状名から「部位の傾向」をざっくり推定（断定しない）
    返り値例: ["上半身中心"] / ["下半身中心"] / ["広い範囲"]
    """
    if not complaints:
        return []

    upper_keywords = ["首", "肩", "背中", "肩甲骨", "腕", "頭"]
    lower_keywords = ["腰", "骨盤", "股関節", "膝", "脚", "足"]

    has_upper = any(any(k in c for k in upper_keywords) for c in complaints)
    has_lower = any(any(k in c for k in lower_keywords) for c in complaints)

    if has_upper and has_lower:
        return ["広い範囲"]
    if has_upper:
        return ["上半身中心"]
    if has_lower:
        return ["下半身中心"]
    return ["全身・その他"]

# ============================================================
# 主訴をユーザー向けに「ぼかした表現」に変換する
# ============================================================
def _abstract_primary_complaint(chief_complaints: list[str]) -> str:
    """
    【この関数の役割】

    管理者向けに抽出された主訴（例: ["腰痛", "首こり"]）を、
    ユーザーに見せても不安を煽らない
    「大まかな表現」に変換する。

    ・診断名に見えない
    ・症状を断定しない
    ・部位レベルで止める

    【引数】
    chief_complaints:
        _extract_main_complaints() で作られた
        主訴の文字列リスト

    【戻り値】
    str:
        ユーザー向けの抽象化された主訴表現
    """

    if not chief_complaints:
        return "体の不調"

    # 上半身に関係しそうなキーワード
    upper_body = ["首", "肩", "背中", "肩甲骨"]

    # 下半身に関係しそうなキーワード
    lower_body = ["腰", "骨盤", "股関節", "脚"]

    # 全体にまたがる可能性
    has_upper = any(any(k in c for k in upper_body) for c in chief_complaints)
    has_lower = any(any(k in c for k in lower_body) for c in chief_complaints)

    if has_upper and has_lower:
        return "全身にかかわる不調"

    if has_upper:
        return "上半身を中心とした不調"

    if has_lower:
        return "下半身を中心とした不調"

    return "体の不調"

# ============================================================
# ユーザー向けに「症状の特徴」を整理する
# ============================================================
def _build_user_symptom_features(admin: AdminIntakeSummary) -> list[str]:
    """
    【この関数の役割】

    管理者向け summary に含まれる情報をもとに、
    ユーザーに伝えても問題ない
    「状態の特徴」だけを文章化する。

    ・症状名は使わない
    ・原因や評価はしない
    ・体の使われ方・広がり方に注目する

    【引数】
    admin:
        build_admin_summary() で作られた
        AdminIntakeSummary オブジェクト

    【戻り値】
    list[str]:
        ユーザー向けの特徴文のリスト
    """

    features: list[str] = []

    # ----------------------------------------
    # ① 複数の不調が同時にあるか
    # ----------------------------------------
    if len(admin.chief_complaints) >= 2:
        features.append("複数の不調が同時にみられる")

    # ----------------------------------------
    # ② 体の広い範囲にまたがっているか
    # ----------------------------------------
    # 主訴をエリア（上半身／下半身）で見て、
    # 両方に関係していそうなら追加する
    upper_body_keywords = ["首", "肩", "背中", "肩甲骨"]
    lower_body_keywords = ["腰", "骨盤", "股関節", "脚"]

    has_upper = any(
        any(k in c for k in upper_body_keywords)
        for c in admin.chief_complaints
    )
    has_lower = any(
        any(k in c for k in lower_body_keywords)
        for c in admin.chief_complaints
    )

    if has_upper and has_lower:
        features.append("体の広い範囲にまたがっている可能性")

    # ----------------------------------------
    # ③ 期間について（将来用）
    # ----------------------------------------
    # v2 では未実装だが、ここに足せる余地を残す
    if admin.symptom_duration:
        features.append("一定期間続いている")

    return features

    # ============================================================
# ユーザー向けに「生活背景」を整理する
# ============================================================
def _build_user_context_factors(admin: AdminIntakeSummary) -> list[str]:
    """
    【この関数の役割】

    管理者向け summary に含まれる
    stress_level などの情報をもとに、
    ユーザーに伝えても問題ない
    「生活背景の要素」に変換する。

    ・数値や評価は出さない
    ・断定しない
    ・やわらかい表現にする

    【引数】
    admin:
        build_admin_summary() で作られた
        AdminIntakeSummary オブジェクト

    【戻り値】
    list[str]:
        ユーザー向けの生活背景要素のリスト
    """

    contexts: list[str] = []

    # ----------------------------------------
    # ストレスレベルが入力されている場合
    # ----------------------------------------
    # high / middle / low のどれであっても、
    # ユーザー向けにはまとめて
    # 「日常生活の負荷」という表現にする
    if admin.stress_level:
        contexts.append("日常生活の負荷")

    return contexts

# ============================================================
# ユーザー向けに「注意して見ていきたい点」を整理する
# ============================================================
def _build_user_attention_points(admin: AdminIntakeSummary) -> list[str]:
    """
    【この関数の役割】

    管理者向け summary に含まれる
    注意情報（sleep_trouble など）を、
    ユーザーに伝えても不安を煽らない
    表現に変換する。

    ・危険・異常という言葉は使わない
    ・評価はしない
    ・「大切な視点」レベルにとどめる

    【引数】
    admin:
        build_admin_summary() で作られた
        AdminIntakeSummary オブジェクト

    【戻り値】
    list[str]:
        ユーザー向けの注意ポイントのリスト
    """

    points: list[str] = []

    # ----------------------------------------
    # 睡眠時間が短そうな場合
    # ----------------------------------------
    if admin.sleep_trouble:
        points.append("睡眠や休息の取りづらさ")

    return points

# ============================================================
# ユーザー向け「概要AI要約」を生成する
# ============================================================
def generate_overview_ai_text(user_ai_input: dict) -> str:
    """
    送信完了画面用の「概要」。
    ・症状/部位の傾向に触れる（必須）
    ・睡眠/日常負担などの観点に触れる（可能なら）
    ・診断/断定は禁止
    """

    system_prompt = """
あなたは医療判断をしない文章整理アシスタントです。
入力データから「見えている傾向」を短くまとめます。
診断・原因断定・改善予測は禁止。
不安を煽る表現や専門用語は避けてください。
"""

    user_prompt = f"""
【入力データ（安全に整理済み）】
{json.dumps(user_ai_input, ensure_ascii=False, indent=2)}

【出力条件（必ず守る）】
・200〜320字程度（短め〜中程度）
・必ず次の4要素を含める
  1) この画面までで入力は完了
  2) 主なつらさ（症状名または部位傾向）に触れる
  3) 影響しそうな観点（睡眠/日常負担など）を「可能性」で示す（断定禁止）
  4) 詳細の整理はLINEで受け取れる（任意）
・「診断」「治る」「原因は」等の断定ワードは禁止
"""

    text = call_llm(system_prompt, user_prompt)

    # 失敗時フォールバック（ここも“中身あり”に修正）
    if not isinstance(text, str) or len(text) < 120:
        return _dummy_overview_text(user_ai_input)

    return text


def _dummy_overview_text(user_ai_input: dict) -> str:
    """
    OpenAIが使えない時でも、概要として成立する固定文（中身あり）
    """
    complaints = user_ai_input.get("main_complaints", [])
    areas = user_ai_input.get("body_areas", [])
    contexts = user_ai_input.get("context_factors", [])

    # ざっくり文章化（断定しない）
    c_part = "・".join(complaints[:3]) if complaints else "お身体のつらさ"
    a_part = areas[0] if areas else "体の状態"
    ctx_part = "、".join(contexts[:2]) if contexts else "日常の負担"

    return (
        "ご入力ありがとうございました。この画面までで問診の入力は完了しています。\n"
        f"今回の入力では、{c_part}など（{a_part}）のつらさが中心となっている可能性がうかがえます。"
        f"また、{ctx_part}といった観点も関係している可能性があります。\n"
        "内容の整理をもう少し詳しく知りたい方には、LINEで補足をご案内できます（登録は任意です）。"
    )

# ============================================================
# AI呼び出しの実装
# ============================================================
def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    【この関数の役割】

    ・月額上限内なら OpenAI API を使う
    ・上限到達 / APIキーなし / エラー時はダミー文を返す
    """

    # ----------------------------
    # ① 上限チェック
    # ----------------------------
    if not can_use_openai_api():
        return _dummy_llm_text()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _dummy_llm_text()

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        # ★ ここで generated_text を定義している
        generated_text = data["choices"][0]["message"]["content"]

        # OpenAI を使ったので回数を記録
        record_openai_call()

        return generated_text

    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return _dummy_llm_text()


def _dummy_llm_text() -> str:
    """
    AIを使わない場合の安全な代替文
    """
    return (
        "ご入力いただいた内容を、すべて確認しました。\n"
        "現在の情報をもとに、状態の整理を行っています。\n"
        "詳しい内容は、来院時に一緒に確認していきましょう。"
    )

# ============================================================
# OpenAI API 使用量の簡易管理（超安全側）
# ============================================================

# 1リクエストあたりの仮コスト（円）
ESTIMATED_COST_PER_CALL = 5

# 今月の使用回数（メモリ上）
# ※ サーバー再起動でリセットされるが、事故防止には十分
_monthly_call_count = 0

def can_use_openai_api() -> bool:
    """
    【この関数の役割】

    ・今月の上限金額を超えていないかチェック
    ・超えていたら False を返す
    """

    global _monthly_call_count

    limit_yen = os.getenv("OPENAI_API_MONTHLY_LIMIT_YEN")
    if not limit_yen:
        # 上限未設定 → 念のため使わない
        return False

    try:
        limit_yen = int(limit_yen)
    except ValueError:
        return False

    estimated_total = _monthly_call_count * ESTIMATED_COST_PER_CALL

    return estimated_total < limit_yen


def record_openai_call():
    """
    OpenAI API を使った回数を記録する
    """
    global _monthly_call_count
    _monthly_call_count += 1

# ============================================================
# ユーザー向け：LINE送信用「詳細AI要約」を生成する
# ============================================================

def generate_line_detail_ai_text(user_ai_input: dict) -> str:
    """
    LINEで送る「詳細」。
    概要で触れた症状・観点について、
    なぜそう見えるのかを整理して説明する（断定しない）。
    """

    system_prompt = """
あなたは医療判断を行わない文章整理アシスタントです。
入力情報をもとに、状態の見方をやさしく整理します。
診断・原因断定・改善予測は禁止です。
不安を煽る表現や専門用語は避けてください。
"""

    user_prompt = f"""
【入力データ（安全に整理済み）】
{json.dumps(user_ai_input, ensure_ascii=False, indent=2)}

【出力条件（必ず守る）】
・400〜700字
・2〜4段落で構成
・概要で触れた症状や部位の傾向を、少し噛み砕いて説明する
・睡眠や日常負担などの観点は「可能性」「考えられる視点」で述べる
・断定語（原因は／治る／診断）は使わない
・最後に次の一文を必ず入れる：
  「※これは医療的な診断ではなく、来院時に状態を確認しながら整理していきます。」
"""

    text = call_llm(system_prompt, user_prompt)

    # フォールバック（ここも“詳細として成立”させる）
    if not isinstance(text, str) or len(text) < 300:
        return _dummy_line_detail_text(user_ai_input)

    return text


def _dummy_line_detail_text(user_ai_input: dict) -> str:
    """
    OpenAIが使えない時の詳細文（中身あり・断定なし）
    """
    complaints = user_ai_input.get("main_complaints", [])
    areas = user_ai_input.get("body_areas", [])
    contexts = user_ai_input.get("context_factors", [])

    c_part = "・".join(complaints[:3]) if complaints else "お身体のつらさ"
    a_part = areas[0] if areas else "体の状態"
    ctx_part = "、".join(contexts[:2]) if contexts else "日常の負担や休息の状況"

    return (
        "ご入力内容をもとに、状態の整理を行っています。\n\n"
        f"今回の入力では、{c_part}といったつらさが中心で、"
        f"{a_part}に負担がかかっている可能性が考えられます。"
        "こうしたつらさは、姿勢や動きの癖だけでなく、"
        f"{ctx_part}などが重なって感じやすくなることがあります。\n\n"
        "どの点を優先して見ていくかは、実際の状態を確認しながら整理していくことが大切です。"
        "※これは医療的な診断ではなく、来院時に状態を確認しながら整理していきます。"
    )

# ============================================================
# ユーザー向け：直接AIで生成する user-summary（NEW）
# ============================================================

def generate_user_summary_from_payload(payload: dict) -> str:
    """
    intakeの生payloadから、
    ユーザー向け整理サマリーをAIで生成する。

    ・医療診断しない
    ・不安を煽らない
    ・整理 → 可能性 → 来院時確認 の構造
    ・失敗時はルールベースへフォールバック
    """

    admin_summary = build_admin_summary(payload)
    user_ai_input = build_user_ai_input(admin_summary)

    print("=== user_ai_input ===")
    print(json.dumps(user_ai_input, ensure_ascii=False, indent=2))

    system_prompt = """
    あなたは整体院のサポートAIです。

    目的は、入力情報をもとに、
    安心感を与えながら整体視点で状態を整理することです。

    【絶対ルール】
    ・入力データに含まれていない情報を推測しない
    ・個人情報を出力しない
    ・医療診断をしない
    ・原因を断定しない
    ・改善を約束しない

    【表現方針】
    ・やさしく自然な日本語
    ・姿勢・筋肉の緊張・体のバランス・血流の視点を自然に含める
    ・「可能性」「考えられます」を使う
    ・箇条書き禁止

    【文字数】
    250〜350字
    """

    user_prompt = f"""
    【入力情報】
    {json.dumps(user_ai_input, ensure_ascii=False)}

    整理サマリーを作成してください。
    """

    text = call_llm(system_prompt, user_prompt)

    if not isinstance(text, str) or len(text) < 200:
        return (
            "ご入力内容を確認しました。\n"
            "現在のお身体の状態について、いくつかのつらさが重なっている可能性があります。\n"
            "来院時に状態を確認しながら整理していきます。"
        )

    return text

# ============================================================
# ユーザー向け：LINE送信用「詳細AI要約」を payload直 で生成（NEW）
# ============================================================

def generate_line_detail_ai_text_from_payload(payload: dict) -> str:
    """
    LINEで送る「詳細」。
    payload（生データ）から直接AIで整理して説明する（断定しない）。

    ・診断/原因断定/改善予測は禁止
    ・不安を煽らない
    ・400〜700字
    ・最後に注意書きを必ず入れる
    """

    safe_input = {
        "main_complaints": payload.get("main_complaints"),
        "body_areas": payload.get("body_areas"),
        "context_factors": payload.get("context_factors"),
        "attention_points": payload.get("attention_points"),
    }

    system_prompt = """
    あなたは医療判断をしない整体院の文章整理アシスタントです。

    目的は、入力内容をもとに、
    安心感を与えながら整体視点で丁寧に整理することです。

    【絶対ルール】
    ・入力データに含まれていない情報を推測しない
    ・個人情報を出力しない
    ・診断・原因断定・改善予測は禁止
    ・不安を煽らない

    【構成】
    1. 現在の状態の整理
    2. 体のバランスとして考えられる可能性
    3. 来院時に確認していく視点

    【表現方針】
    ・姿勢・筋肉の緊張・体の連動・血流の視点を含める
    ・やさしく落ち着いた文章
    ・断定語は禁止

    【文字数】
    400〜600字
    """

    user_prompt = f"""
    【入力情報】
    {json.dumps(safe_input, ensure_ascii=False)}

    整理 → 可能性 → 来院時確認 の順でまとめてください。

    最後に必ず以下を入れる：
    ※これは医療的な診断ではなく、来院時に状態を確認しながら整理していきます。
    """

    text = call_llm(system_prompt, user_prompt)

    if not isinstance(text, str) or len(text) < 300:
        return (
            "ご入力内容を確認しました。\n\n"
            "現在のつらさについては複数の要素が重なっている可能性があります。\n"
            "来院時に詳しく確認しながら整理していきます。\n\n"
            "※これは医療的な診断ではなく、来院時に状態を確認しながら整理していきます。"
        )

    return text
