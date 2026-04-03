from __future__ import absolute_import

import json


def build_plain_translation_user_prompt(payload, extra_prompt):
    sections = []
    extra_instruction = str(extra_prompt or "").strip()
    if extra_instruction:
        sections.append(
            "High-priority additional instruction from user: {}. Follow it unless it conflicts with source_text meaning, placeholders, or locked_terms.".format(
                extra_instruction
            )
        )
    sections.append("Task payload JSON:")
    sections.append(json.dumps(dict(payload or {}), ensure_ascii=False, indent=2, sort_keys=True))
    return "\n".join(sections)


def build_plain_translation_system_prompt(role_description, candidate_requirement):
    return (
        "You are a professional translator and reviewer for {}.\n".format(str(role_description or "").strip())
        + "Return JSON only with keys: verdict, candidate_translation, reason.\n"
        + "verdict must be either accurate or needs_update.\n"
        + "{}\n".format(str(candidate_requirement or "").strip())
        + "candidate_translation must be natural English and must not directly copy the Chinese source text.\n"
        + "candidate_translation must not include Chinese explanations, SQL, JSON, or multiple lines.\n"
        + "Use standard half-width English punctuation. Do not keep Chinese-style punctuation such as “ ” ‘ ’ ， 。 ： ； （ ） 【 】 ！ ？ 、 or …… in English output.\n"
        + "reason must be written in Simplified Chinese.\n"
        + "Do not output English in reason unless it is a required technical term quoted from the source or target text.\n"
        + "Preserve placeholders exactly, including {0}, {}, %s, ${name} and similar forms.\n"
        + "If locked_terms are provided, candidate_translation must use the glossary wording but adjust capitalization to fit English grammar.\n"
        + "When a locked term appears at the start of a sentence, capitalize only the first ordinary word as needed.\n"
        + "When a locked term appears mid-sentence, use normal lowercase for ordinary words instead of copying title case from the glossary. Preserve acronyms such as IP, ECS, or CPU.\n"
        + "If extra_prompt is provided, treat it as a high-priority additional instruction and apply it unless it conflicts with source_text meaning, placeholders, or locked_terms.\n"
        + "If target_text is already accurate, set verdict=accurate and candidate_translation to the unchanged target_text."
    )


def build_plain_translation_review_user_prompt(payload, extra_prompt):
    sections = []
    extra_instruction = str(extra_prompt or "").strip()
    if extra_instruction:
        sections.append(
            "High-priority additional instruction from user: {}. Review whether candidate_text follows it unless the instruction conflicts with source_text meaning, placeholders, or locked_terms.".format(
                extra_instruction
            )
        )
    sections.append("Review payload JSON:")
    sections.append(json.dumps(dict(payload or {}), ensure_ascii=False, indent=2, sort_keys=True))
    return "\n".join(sections)


def build_plain_translation_review_system_prompt(review_description):
    return (
        "You are a strict QA reviewer for {}.\n".format(str(review_description or "").strip())
        + "Return JSON only with keys: decision, issues.\n"
        + "decision must be either pass or fail.\n"
        + "issues must be either an array of short Simplified Chinese strings or an array of objects with keys code, message, severity, evidence, and expected_term.\n"
        + "For object issues, message and evidence must be written in Simplified Chinese. expected_term may contain English terminology.\n"
        + "Ignore any previous English wording. Review candidate_text on its own merits against source_text.\n"
        + "Judge candidate_text against source_text, placeholders, locked_terms, and extra_prompt when extra_prompt is provided.\n"
        + "Do not fail solely because a locked term uses different capitalization. Treat locked_terms matching as case-insensitive.\n"
        + "Do not report that a term should be X if candidate_text already contains X.\n"
        + "Do not treat style-only suggestions such as 'could be more natural' as hard failures.\n"
        + "extra_prompt is a high-priority additional instruction unless it conflicts with source_text meaning, placeholders, or locked_terms.\n"
        + "Do not output English in message or evidence unless it is a required technical term quoted from source_text, candidate_text, or locked_terms.\n"
        + "Only report spelling or wording problems that actually appear in candidate_text.\n"
        + "Fail when the candidate is not natural English, still contains untranslated Chinese, keeps Chinese-style punctuation in otherwise English text, omits source meaning, or breaks placeholders.\n"
        + "Pass only when the candidate is a complete and accurate English translation of the source text."
    )
