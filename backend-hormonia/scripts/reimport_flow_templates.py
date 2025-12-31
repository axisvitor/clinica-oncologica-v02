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

from app.core.database import SessionLocal
from sqlalchemy import text


def parse_initial_15_days(content: str) -> List[Dict[str, Any]]:
    """Parse FLUXO HORMON[IA] - 1 A 15.md"""
    steps = []
    
    # Patterns para identificar dias e mensagens
    day_pattern = r'###\s*\*\*📍DIA\s*(\d+)'
    msg_pattern = r'\*\*Mensagem\s*(\d+)\*\*'
    
    # Split por dias
    day_sections = re.split(r'---\s*\n\s*###', content)
    
    for section in day_sections:
        day_match = re.search(r'\*\*📍DIA\s*(\d+)', section)
        if not day_match:
            continue
            
        day_num = int(day_match.group(1))
        
        # Encontrar todas as mensagens no dia
        messages = []
        
        # Primeira mensagem (antes de "Mensagem 2")
        first_msg_end = section.find('**Mensagem 2**')
        if first_msg_end == -1:
            first_msg_end = len(section)
        
        # Extrair conteúdo após o título do dia
        title_end = section.find('\n', section.find('DIA'))
        if title_end != -1:
            first_content = section[title_end:first_msg_end].strip()
            first_content = clean_markdown(first_content)
            if first_content:
                messages.append({
                    "order": 1,
                    "content": first_content,
                    "expects_response": False  # Será ajustado depois
                })
        
        # Mensagens subsequentes
        msg_matches = list(re.finditer(r'\*\*Mensagem\s*(\d+)\*\*\s*\n(.*?)(?=\*\*Mensagem|\Z|---)', section, re.DOTALL))
        for match in msg_matches:
            msg_order = int(match.group(1))
            msg_content = clean_markdown(match.group(2).strip())
            if msg_content:
                messages.append({
                    "order": msg_order,
                    "content": msg_content,
                    "expects_response": False
                })
        
        # Definir modo de envio e expects_response baseado no dia
        send_mode = determine_send_mode_15(day_num, messages)
        
        steps.append({
            "day": day_num,
            "messages": messages,
            "send_mode": send_mode
        })
    
    return steps


def parse_16_45_days(content: str) -> List[Dict[str, Any]]:
    """Parse Fluxo HORMON[IA] - 16 A 45.md"""
    steps = []
    
    # Split por dias (cada dia começa com **📅 Dia XX)
    day_sections = re.split(r'\n---\s*\n', content)
    
    for section in day_sections:
        day_match = re.search(r'\*\*📅\s*Dia\s*(\d+)', section)
        if not day_match:
            continue
            
        day_num = int(day_match.group(1))
        
        # Extrair conteúdo (tudo após o título)
        title_end = section.find('\n\n', section.find('Dia'))
        if title_end != -1:
            msg_content = section[title_end:].strip()
            msg_content = clean_markdown(msg_content)
            
            # Remover notas entre parênteses no final (instruções do fluxo)
            msg_content = re.sub(r'\n\s*\(se responder.*?\)', '', msg_content, flags=re.DOTALL)
            msg_content = re.sub(r'\n\s*\(Se a pessoa.*?\)', '', msg_content, flags=re.DOTALL)
            
            if msg_content:
                # Dias 16-45 são todos single message
                expects_response = day_num in [18, 20, 22, 26, 30, 32, 34, 40]  # Dias com perguntas
                
                steps.append({
                    "day": day_num,
                    "messages": [{
                        "order": 1,
                        "content": msg_content.strip(),
                        "expects_response": expects_response
                    }],
                    "send_mode": "single"
                })
    
    return steps


def parse_monthly_flow(content: str) -> List[Dict[str, Any]]:
    """Parse Fluxo Hormon[IA] MENSAL PADRÃO .md"""
    steps = []
    
    # Split por dias
    day_sections = re.split(r'\n---\s*\n', content)
    
    for section in day_sections:
        day_match = re.search(r'####\s*\*\*📆\s*Dia\s*(\d+)', section)
        if not day_match:
            continue
            
        day_num = int(day_match.group(1))
        
        # Procurar por **Mensagem:** e extrair conteúdo
        msg_start = section.find('**Mensagem:**')
        if msg_start == -1:
            continue
        
        msg_content = section[msg_start + len('**Mensagem:**'):].strip()
        msg_content = clean_markdown(msg_content)
        
        if msg_content:
            # Mensal: todos são single, alguns esperam resposta
            expects_response = day_num in [1, 4, 8, 11, 15, 22, 26]
            
            steps.append({
                "day": day_num,
                "messages": [{
                    "order": 1,
                    "content": msg_content,
                    "expects_response": expects_response
                }],
                "send_mode": "single"
            })
    
    return steps


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


def determine_send_mode_15(day: int, messages: List[Dict]) -> str:
    """Determina modo de envio para dias 1-15"""
    if day in [1, 2]:
        # Dias de apresentação/educação: envia tudo sequencial
        return "sequential_auto"
    elif day in [3, 5]:
        # Primeira msg é check-in, espera resposta, depois info
        if messages:
            messages[0]["expects_response"] = True
        return "wait_response"
    elif day == 9:
        # Check-in depois info sequencial
        if messages:
            messages[0]["expects_response"] = True
        return "wait_response"
    elif day == 15:
        # Série de perguntas, cada uma espera resposta
        for i, msg in enumerate(messages):
            # Msgs 2, 3, 4 são perguntas
            if i in [1, 2, 3]:
                msg["expects_response"] = True
        return "wait_each"
    else:
        # Single message days
        if messages:
            messages[0]["expects_response"] = True
        return "single"


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
    
    # 1. Parse e atualizar initial_15_days
    print("📂 Processando: FLUXO HORMON[IA] - 1 A 15.md")
    with open(f"{base_path}/FLUXO HORMON[IA] - 1 A 15.md", "r", encoding="utf-8") as f:
        content = f.read()
    steps_15 = parse_initial_15_days(content)
    print(f"   Dias encontrados: {[s['day'] for s in steps_15]}")
    for s in steps_15:
        print(f"   Dia {s['day']}: {len(s['messages'])} msgs, modo: {s['send_mode']}")
    
    # 2. Parse e atualizar days_16_45
    print("\n📂 Processando: Fluxo HORMON[IA] - 16 A 45.md")
    with open(f"{base_path}/Fluxo HORMON[IA] - 16 A 45.md", "r", encoding="utf-8") as f:
        content = f.read()
    steps_16_45 = parse_16_45_days(content)
    print(f"   Dias encontrados: {[s['day'] for s in steps_16_45]}")
    
    # 3. Parse e atualizar monthly_recurring
    print("\n📂 Processando: Fluxo Hormon[IA] MENSAL PADRÃO .md")
    with open(f"{base_path}/Fluxo Hormon[IA] MENSAL PADRÃO .md", "r", encoding="utf-8") as f:
        content = f.read()
    steps_monthly = parse_monthly_flow(content)
    print(f"   Dias encontrados: {[s['day'] for s in steps_monthly]}")
    
    # Confirmar antes de atualizar
    print("\n" + "="*50)
    print("RESUMO:")
    print(f"  initial_15_days: {len(steps_15)} dias")
    print(f"  days_16_45: {len(steps_16_45)} dias")
    print(f"  monthly_recurring: {len(steps_monthly)} dias")
    print("="*50)
    
    confirm = "s"  # Auto-confirm for script execution
    if confirm.lower() != 's':
        print("Operação cancelada.")
        return
    
    # Atualizar banco
    print("\n📤 Atualizando banco de dados...")
    update_database(steps_15, "initial_15_days")
    update_database(steps_16_45, "days_16_45")
    update_database(steps_monthly, "monthly_recurring")
    
    print("\n✅ Reimportação concluída!")


if __name__ == "__main__":
    main()
