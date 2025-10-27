#!/usr/bin/env python3
"""
Script para testar o endpoint treatment-distribution e diagnosticar o erro 500
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.patient import Patient
from app.models.user import User, UserRole

def test_treatment_distribution_query():
    """Testa a query do treatment-distribution para identificar o problema"""
    
    print("🧪 Testando query do treatment-distribution...")
    
    # Obter sessão do banco
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        # Testar query básica
        print("\n1. Testando query básica de contagem de pacientes...")
        total_patients = db.query(Patient).count()
        print(f"   Total de pacientes: {total_patients}")
        
        # Testar query de treatment_type
        print("\n2. Testando query de treatment_type...")
        treatment_types = db.query(Patient.treatment_type).distinct().all()
        print(f"   Tipos de tratamento encontrados: {[t[0] for t in treatment_types]}")
        
        # Testar query de distribuição
        print("\n3. Testando query de distribuição...")
        distribution_query = db.query(
            Patient.treatment_type,
            func.count(Patient.id).label("count"),
        )
        
        distribution_results = (
            distribution_query
            .group_by(Patient.treatment_type)
            .order_by(func.count(Patient.id).desc())
            .all()
        )
        
        print(f"   Resultados da distribuição:")
        for treatment_type, count in distribution_results:
            print(f"     - {treatment_type or 'Não informado'}: {count}")
        
        # Testar query de trend
        print("\n4. Testando query de trend...")
        now = datetime.utcnow()
        start_date = now - timedelta(days=30)
        
        trend_query = db.query(
            func.date_trunc('week', Patient.created_at).label('week_start'),
            func.count(Patient.id).label('count'),
        ).filter(Patient.created_at >= start_date)
        
        trend_results = (
            trend_query
            .group_by(func.date_trunc('week', Patient.created_at))
            .order_by(func.date_trunc('week', Patient.created_at))
            .limit(12)
            .all()
        )
        
        print(f"   Resultados do trend:")
        for week_start, count in trend_results:
            print(f"     - {week_start}: {count}")
        
        # Testar construção do resultado final
        print("\n5. Testando construção do resultado...")
        
        COLOR_PALETTE = [
            "#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed",
            "#db2777", "#0891b2", "#65a30d", "#dc2626", "#7c2d12"
        ]
        
        total_patients = sum(count for _, count in distribution_results)
        distribution = []
        
        for index, (treatment_type, count) in enumerate(distribution_results):
            label = treatment_type or "Não informado"
            percentage = (count / total_patients * 100) if total_patients else 0
            distribution.append({
                "treatment_type": label,
                "count": count,
                "percentage": round(percentage, 2),
                "color": COLOR_PALETTE[index % len(COLOR_PALETTE)],
            })
        
        trend_data = []
        for week_start, count in trend_results:
            if week_start is not None:
                if hasattr(week_start, "date"):
                    week_value = week_start.date().isoformat()
                else:
                    week_value = str(week_start)
                trend_data.append({"week": week_value, "count": count})
        
        result = {
            "period": "30d",
            "total_patients": total_patients,
            "distribution": distribution,
            "trend_data": trend_data,
            "last_updated": now.isoformat(),
        }
        
        print(f"   Resultado final construído com sucesso!")
        print(f"   Total de pacientes: {result['total_patients']}")
        print(f"   Itens na distribuição: {len(result['distribution'])}")
        print(f"   Itens no trend: {len(result['trend_data'])}")
        
        return result
        
    except Exception as e:
        print(f"❌ Erro durante o teste: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        db.close()

def test_user_permissions():
    """Testa se há usuários válidos para testar permissões"""
    
    print("\n🔐 Testando usuários e permissões...")
    
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        # Contar usuários por role
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
        doctor_count = db.query(User).filter(User.role == UserRole.DOCTOR).count()
        
        print(f"   Usuários ADMIN: {admin_count}")
        print(f"   Usuários DOCTOR: {doctor_count}")
        
        # Listar alguns usuários
        users = db.query(User).limit(5).all()
        print(f"   Primeiros usuários:")
        for user in users:
            print(f"     - {user.email} ({user.role})")
            
    except Exception as e:
        print(f"❌ Erro ao testar usuários: {e}")
        
    finally:
        db.close()

if __name__ == "__main__":
    print("🔍 Diagnóstico do endpoint treatment-distribution")
    print("=" * 50)
    
    # Testar conexão com banco
    try:
        from sqlalchemy import text
        db_gen = get_db()
        db = next(db_gen)
        db.execute(text("SELECT 1"))
        db.close()
        print("✅ Conexão com banco OK")
    except Exception as e:
        print(f"❌ Erro de conexão com banco: {e}")
        sys.exit(1)
    
    # Executar testes
    test_user_permissions()
    result = test_treatment_distribution_query()
    
    if result:
        print("\n✅ Todos os testes passaram!")
        print("   O endpoint deveria funcionar corretamente.")
        print("\n💡 Possíveis causas do erro 500:")
        print("   1. Problema de autenticação/sessão")
        print("   2. Erro de cache (Redis)")
        print("   3. Problema de serialização JSON")
        print("   4. Timeout de query")
    else:
        print("\n❌ Testes falharam!")
        print("   Verifique os erros acima para identificar o problema.")