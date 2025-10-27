#!/usr/bin/env python3
"""
Script para testar se a correção de autenticação está funcionando
"""

import requests
import json
import sys

def test_auth_endpoints():
    """Testa endpoints que estavam falhando com 401"""
    
    print("🔍 TESTANDO CORREÇÃO DE AUTENTICAÇÃO")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # Endpoints que estavam falhando
    test_endpoints = [
        {
            "name": "Quiz Stats Dashboard",
            "url": f"{base_url}/api/v1/monthly-quiz/stats/dashboard",
            "method": "GET"
        },
        {
            "name": "Active Quiz Links", 
            "url": f"{base_url}/api/v1/monthly-quiz/links/active",
            "method": "GET"
        },
        {
            "name": "Patient Quiz Status",
            "url": f"{base_url}/api/v1/monthly-quiz/patients/5d3b9370-d839-47b5-88d0-d8ff67b85452/status",
            "method": "GET"
        }
    ]
    
    # Testar sem token (deve retornar 401 mas sem erro interno)
    print("\n1. 🚫 Testando sem autenticação (esperado: 401 limpo)...")
    
    for endpoint in test_endpoints:
        try:
            response = requests.get(endpoint["url"], timeout=5)
            
            if response.status_code == 401:
                print(f"   ✅ {endpoint['name']}: 401 (correto)")
                
                # Verificar se a resposta tem estrutura JSON válida
                try:
                    error_data = response.json()
                    if "detail" in error_data:
                        print(f"      📝 Mensagem: {error_data['detail']}")
                    else:
                        print("      📝 Resposta JSON válida")
                except:
                    print("      ⚠️  Resposta não é JSON válido")
            else:
                print(f"   ⚠️  {endpoint['name']}: {response.status_code} (inesperado)")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ {endpoint['name']}: Servidor não está rodando")
        except Exception as e:
            print(f"   ❌ {endpoint['name']}: Erro - {e}")
    
    # Testar endpoint de saúde
    print("\n2. 💚 Testando endpoint de saúde...")
    
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Health check: OK")
            health_data = response.json()
            print(f"      📊 Status: {health_data.get('status', 'unknown')}")
        else:
            print(f"   ⚠️  Health check: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ❌ Servidor não está rodando")
        print("   💡 Execute: uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"   ❌ Erro no health check: {e}")
    
    # Testar WebSocket (apenas verificar se não há erro 500)
    print("\n3. 🔌 Testando WebSocket...")
    
    try:
        # Tentar conectar WebSocket (vai falhar com 403 mas não deve dar erro 500)
        import websockets
        import asyncio
        
        async def test_websocket():
            try:
                uri = "ws://localhost:8000/ws/connect"
                async with websockets.connect(uri, timeout=2) as websocket:
                    print("   ✅ WebSocket conectou (inesperado)")
            except websockets.exceptions.ConnectionClosedError as e:
                if e.code == 4001:  # Authentication required
                    print("   ✅ WebSocket: 4001 Authentication required (correto)")
                else:
                    print(f"   ⚠️  WebSocket: Código {e.code}")
            except Exception as e:
                print(f"   ⚠️  WebSocket: {e}")
        
        asyncio.run(test_websocket())
        
    except ImportError:
        print("   ⚠️  websockets não instalado, pulando teste")
    except Exception as e:
        print(f"   ❌ Erro no teste WebSocket: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Teste de correção concluído!")
    print("\n💡 Se todos os endpoints retornaram 401 (não 500), a correção funcionou!")
    
    return True


if __name__ == "__main__":
    test_auth_endpoints()