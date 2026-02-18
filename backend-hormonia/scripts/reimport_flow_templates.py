"""
Script para reimportar os fluxos WhatsApp a partir dos arquivos Markdown.
Cria estrutura correta com múltiplas mensagens por dia e modos de envio.
"""

import sys
import os
import re
import json
from typing import List, Dict, Any

sys.path.append(os.getcwd())

from app.database import SessionLocal
from sqlalchemy import text


QUESTION_PHRASES = [
    "me conta",
    "me conte",
    "me responde",
    "me responda",
    "me responde com",
    "me responda com",
    "me diz",
    "me diga",
    "me fala",
    "me fale",
    "como voce",
    "como você",
    "como esta",
    "como está",
    "como ta",
    "como tá",
    "voce tem",
    "você tem",
    "voce ja",
    "você já",
    "tem algo",
    "tem alguma",
    "tem algum",
    "posso contar com voce",
    "posso contar com você",
    "pode me dizer",
    "pode me falar",
    "me avisa",
    "me avise",
    "responda com",
]


def message_expects_response(content: str) -> bool:
    """Infer whether a message expects a response based on content."""
    if not content:
        return False

    normalized = re.sub(r"\s+", " ", content).strip().lower()
    if "?" in normalized:
        return True
    if re.search(r"\(\s*\)", normalized):
        return True
    return any(phrase in normalized for phrase in QUESTION_PHRASES)

TRAILING_META_PATTERNS = [
    r"\n+Se quiser, posso seguir.*?Deseja.*?$",
    r"\n+Se estiver tudo certo, sigo.*?Deseja.*?$",
]

INSTRUCTION_LINE_PATTERNS = [
    r"\n\s*\(se responder.*?\)",
    r"\n\s*\(se a pessoa.*?\)",
    r"\n\s*\(.*?\u2192.*?\)",
]


def strip_trailing_meta(text: str) -> str:
    """Remove trailing authoring notes that should not reach patients."""
    for pattern in TRAILING_META_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)
    return text.strip()


def strip_instruction_lines(text: str) -> str:
    """Remove inline authoring instructions inside flow templates."""
    for pattern in INSTRUCTION_LINE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


def determine_send_mode(messages: List[Dict[str, Any]]) -> str:
    """Determine send mode based on how many responses are expected."""
    response_count = sum(
        1 for msg in messages if msg.get("expects_response") is True
    )

    if len(messages) <= 1:
        return "single"
    if response_count == 0:
        return "sequential_auto"
    if response_count == 1:
        if messages and messages[0].get("expects_response") is True:
            return "wait_response"
        return "wait_each"
    return "wait_each"


DAY_HEADING_RE = re.compile(
    r"^\s*#{2,4}\s*(?:\*\*)?(?:📍|📅|📆)?\s*Dia\s*(\d+)",
    re.IGNORECASE | re.MULTILINE,
)


def _iter_day_sections(content: str) -> List[Dict[str, Any]]:
    matches = list(DAY_HEADING_RE.finditer(content))
    sections: List[Dict[str, Any]] = []
    for idx, match in enumerate(matches):
        day_num = int(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        section = content[start:end].strip()
        sections.append({"day": day_num, "section": section})
    return sections


def _normalize_message_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(lines).strip()
    cleaned = clean_markdown(cleaned)
    cleaned = strip_instruction_lines(cleaned)
    cleaned = strip_trailing_meta(cleaned)
    return cleaned.strip()


def _parse_messages(section: str) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []

    # Prefer explicit "**Mensagem X**" blocks if present
    msg_matches = list(
        re.finditer(
            r"\*\*Mensagem\s*(\d+)\*\*\s*\n(.*?)(?=\*\*Mensagem|\Z|---)",
            section,
            re.DOTALL,
        )
    )
    if msg_matches:
        for match in msg_matches:
            msg_order = int(match.group(1))
            msg_content = _normalize_message_text(match.group(2))
            if msg_content:
                messages.append(
                    {
                        "order": msg_order,
                        "content": msg_content,
                        "expects_response": message_expects_response(msg_content),
                    }
                )
        return messages

    # Fallback: numbered list items (1. ... 2. ...)
    list_matches = list(
        re.finditer(
            r"^\s*(\d+)\.\s+(.*?)(?=^\s*\d+\.\s+|\Z)",
            section,
            re.DOTALL | re.MULTILINE,
        )
    )
    if list_matches:
        for match in list_matches:
            msg_order = int(match.group(1))
            msg_content = _normalize_message_text(match.group(2))
            if msg_content:
                messages.append(
                    {
                        "order": msg_order,
                        "content": msg_content,
                        "expects_response": message_expects_response(msg_content),
                    }
                )
        return messages

    # Final fallback: treat entire section as a single message
    msg_content = _normalize_message_text(section)
    if msg_content:
        messages.append(
            {
                "order": 1,
                "content": msg_content,
                "expects_response": message_expects_response(msg_content),
            }
        )

    return messages


def _parse_flow_generic(content: str) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    for entry in _iter_day_sections(content):
        day_num = entry["day"]
        section = entry["section"]
        messages = _parse_messages(section)
        if not messages:
            continue
        send_mode = determine_send_mode(messages)
        steps.append({"day": day_num, "messages": messages, "send_mode": send_mode})
    return steps


def parse_onboarding(content: str) -> List[Dict[str, Any]]:
    """Parse FLUXO HORMON[IA] - 1 A 15.md"""
    return _parse_flow_generic(content)


def parse_16_45_days(content: str) -> List[Dict[str, Any]]:
    """Parse Fluxo HORMON[IA] - 16 A 45.md"""
    return _parse_flow_generic(content)


def parse_monthly_flow(content: str) -> List[Dict[str, Any]]:
    """Parse Fluxo Hormon[IA] MENSAL PADRÃO .md"""
    return _parse_flow_generic(content)


def clean_markdown(text: str) -> str:
    """Remove markdown formatting e limpa texto"""
    # Remove escape characters
    text = text.replace('\\!', '!')
    text = text.replace('\\[', '[')
    text = text.replace('\\]', ']')
    
    # Remove bold markers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    
    # Remove italic markers
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    
    # Normaliza espaços
    text = re.sub(r'\n\s+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def update_database(steps: List[Dict], kind_key: str):
    """Atualiza flow_template_versions no banco"""
    db = SessionLocal()
    try:
        # Buscar flow_kind_id
        result = db.execute(text(
            "SELECT id FROM flow_kinds WHERE kind_key = :kind_key"
        ), {"kind_key": kind_key}).fetchone()
        
        if not result:
            print(f"❌ Flow kind '{kind_key}' não encontrado!")
            return False
        
        flow_kind_id = str(result[0])
        steps_json = json.dumps(steps, ensure_ascii=False)
        
        # Atualizar steps na versão ativa usando bindparam para JSONB
        db.execute(text("""
            UPDATE flow_template_versions 
            SET steps = cast(:steps_json as jsonb)
            WHERE flow_kind_id = :flow_kind_id AND is_active = true
        """), {"steps_json": steps_json, "flow_kind_id": flow_kind_id})
        
        db.commit()
        print(f"✅ Atualizado {kind_key}: {len(steps)} dias")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao atualizar {kind_key}: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def main():
    print("=== Reimportando Fluxos WhatsApp ===\n")
    
    base_path = "app/templates/arquivo"
    
    # 1. Parse e atualizar onboarding
    print("📂 Processando: FLUXO HORMON[IA] - 1 A 15.md")
    with open(f"{base_path}/FLUXO HORMON[IA] - 1 A 15.md", "r", encoding="utf-8") as f:
        content = f.read()
    steps_15 = parse_onboarding(content)
    print(f"   Dias encontrados: {[s['day'] for s in steps_15]}")
    for s in steps_15:
        print(f"   Dia {s['day']}: {len(s['messages'])} msgs, modo: {s['send_mode']}")
    
    # 2. Parse e atualizar daily_follow_up
    print("\n📂 Processando: Fluxo HORMON[IA] - 16 A 45.md")
    with open(f"{base_path}/Fluxo HORMON[IA] - 16 A 45.md", "r", encoding="utf-8") as f:
        content = f.read()
    steps_16_45 = parse_16_45_days(content)
    print(f"   Dias encontrados: {[s['day'] for s in steps_16_45]}")
    
    # 3. Parse e atualizar quiz_mensal
    print("\n📂 Processando: Fluxo Hormon[IA] MENSAL PADRÃO .md")
    with open(f"{base_path}/Fluxo Hormon[IA] MENSAL PADRÃO .md", "r", encoding="utf-8") as f:
        content = f.read()
    steps_monthly = parse_monthly_flow(content)
    print(f"   Dias encontrados: {[s['day'] for s in steps_monthly]}")
    
    # Confirmar antes de atualizar
    print("\n" + "="*50)
    print("RESUMO:")
    print(f"  onboarding: {len(steps_15)} dias")
    print(f"  daily_follow_up: {len(steps_16_45)} dias")
    print(f"  quiz_mensal: {len(steps_monthly)} dias")
    print("="*50)
    
    confirm = "s"  # Auto-confirm for script execution
    if confirm.lower() != 's':
        print("Operação cancelada.")
        return
    
    # Atualizar banco
    print("\n📤 Atualizando banco de dados...")
    update_database(steps_15, "onboarding")
    update_database(steps_16_45, "daily_follow_up")
    update_database(steps_monthly, "quiz_mensal")
    
    print("\n✅ Reimportação concluída!")


if __name__ == "__main__":
    main()
