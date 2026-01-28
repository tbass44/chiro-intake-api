"""
summary.py

intake payload（dict）から
管理者向け summary を作成するロジック
"""

from typing import Optional
from schemas import AdminIntakeSummary


def build_admin_summary(payload: dict) -> AdminIntakeSummary:
    """
    intake payload から管理者向け summary を生成する

    ・ルールベース
    ・文章生成しない
    ・フロント構造の変更をここで吸収する
    """

    chief_complaints = payload.get("symptoms", [])
    red_flags = _extract_red_flags(payload)
    sleep_trouble = payload.get("sleep", {}).get("trouble")

    return AdminIntakeSummary(
        chief_complaints=chief_complaints,
        symptom_duration=payload.get("symptomDuration"),
        red_flags=red_flags,
        sleep_trouble=payload.get("sleep", {}).get("trouble"),
        stress_level=payload.get("stressLevel"),
        clinical_focus=_determine_clinical_focus(
            chief_complaints=chief_complaints,
            red_flags=red_flags,
            sleep_trouble=payload.get("sleep", {}).get("trouble"),
        ),
    )


def _extract_main_complaints(payload: dict) -> list[str]:
    """
    主訴の抽出

    ※ フロント側のキー名変更があっても
       この関数を直せば影響を局所化できる
    """
    return payload.get("symptoms", [])


def _extract_red_flags(payload: dict) -> list[str]:
    """
    管理者が注意すべきフラグの抽出
    """
    flags: list[str] = []

    if payload.get("numbness"):
        flags.append("しびれあり")

    if payload.get("nightPain"):
        flags.append("夜間痛あり")

    if payload.get("medicalHistory"):
        flags.append("既往歴あり")

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

