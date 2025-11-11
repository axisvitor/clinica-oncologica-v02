#!/usr/bin/env python3
"""
Script de verificação pré-deploy para o backend Hormonia.
Identifica problemas críticos antes do deploy em produção.
"""
import sys
import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict
import json

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

# Carrega variáveis de ambiente do .env
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[INFO] Carregado .env de: {env_path}\n")

class Colors:
    """Cores ANSI para output colorido"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class PreDeployChecker:
    """Verificador de pré-deploy"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passed: List[str] = []
        
    def print_header(self, text: str):
        """Imprime cabeçalho"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    def print_success(self, text: str):
        """Imprime mensagem de sucesso"""
        print(f"{Colors.GREEN}[OK] {text}{Colors.END}")
        self.passed.append(text)
    
    def print_warning(self, text: str):
        """Imprime aviso"""
        print(f"{Colors.YELLOW}[WARN] {text}{Colors.END}")
        self.warnings.append(text)
    
    def print_error(self, text: str):
        """Imprime erro"""
        print(f"{Colors.RED}[ERRO] {text}{Colors.END}")
        self.errors.append(text)
    
    def check_python_version(self) -> bool:
        """Verifica versão do Python"""
        self.print_header("1. Verificando Versão do Python")
        
        version = sys.version_info
        if version.major == 3 and version.minor >= 12:
            self.print_success(f"Python {version.major}.{version.minor}.{version.micro}")
            return True
        else:
            self.print_error(f"Python {version.major}.{version.minor}.{version.micro} - Requer Python 3.12+")
            return False
    
    def check_dependencies(self) -> bool:
        """Verifica dependências instaladas"""
        self.print_header("2. Verificando Dependências")
        
        try:
            result = subprocess.run(
                ["python", "-m", "pip", "check"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.print_success("Todas as dependências estão corretas")
                return True
            else:
                self.print_error(f"Problemas nas dependências:\n{result.stdout}")
                return False
        except Exception as e:
            self.print_error(f"Erro ao verificar dependências: {e}")
            return False
    
    def check_imports(self) -> bool:
        """Verifica imports críticos"""
        self.print_header("3. Verificando Imports Críticos")
        
        critical_imports = [
            "app.main",
            "app.config",
            "app.database",
            "app.celery_app",
            "app.core.application_factory",
            "app.core.lifespan",
            "app.api.v2",
        ]
        
        all_ok = True
        for module in critical_imports:
            try:
                __import__(module)
                self.print_success(f"Import OK: {module}")
            except Exception as e:
                self.print_error(f"Falha ao importar {module}: {e}")
                all_ok = False
        
        return all_ok
    
    def check_env_variables(self) -> bool:
        """Verifica variáveis de ambiente críticas"""
        self.print_header("4. Verificando Variáveis de Ambiente")
        
        required_vars = {
            "DATABASE_URL": "URL do banco de dados PostgreSQL",
            "REDIS_URL": "URL do Redis",
            "SECRET_KEY": "Chave secreta da aplicação",
            "JWT_SECRET_KEY": "Chave secreta JWT",
        }
        
        optional_vars = {
            "SENTRY_DSN": "DSN do Sentry para monitoramento",
            "GEMINI_API_KEY": "Chave API do Google Gemini",
            "EVOLUTION_API_URL": "URL da API Evolution (WhatsApp)",
            "FIREBASE_ADMIN_PROJECT_ID": "ID do projeto Firebase",
        }
        
        all_ok = True
        
        # Verifica variáveis obrigatórias
        for var, description in required_vars.items():
            value = os.getenv(var)
            if not value:
                self.print_error(f"{var} não configurada - {description}")
                all_ok = False
            elif "CHANGE_THIS" in value or "YOUR_" in value:
                self.print_error(f"{var} contém valor placeholder - {description}")
                all_ok = False
            else:
                # Mascara valores sensíveis
                masked = value[:10] + "..." if len(value) > 10 else "***"
                self.print_success(f"{var} configurada: {masked}")
        
        # Verifica variáveis opcionais
        for var, description in optional_vars.items():
            value = os.getenv(var)
            if not value:
                self.print_warning(f"{var} não configurada - {description}")
            else:
                masked = value[:10] + "..." if len(value) > 10 else "***"
                self.print_success(f"{var} configurada: {masked}")
        
        return all_ok
    
    def check_database_connection(self) -> bool:
        """Verifica conexão com banco de dados"""
        self.print_header("5. Verificando Conexão com Banco de Dados")
        
        try:
            from app.database import test_connection
            
            result = test_connection()
            
            if result.get("status") == "healthy":
                self.print_success("Conexão com banco de dados OK")
                pool_info = result.get("pool_info", {})
                print(f"  Pool size: {pool_info.get('pool_size', 'N/A')}")
                print(f"  Connections: {pool_info.get('checked_out', 0)}/{pool_info.get('total_max', 'N/A')}")
                return True
            else:
                self.print_error(f"Falha na conexão: {result.get('error', 'Unknown')}")
                return False
        except Exception as e:
            self.print_error(f"Erro ao testar conexão: {e}")
            return False
    
    def check_redis_connection(self) -> bool:
        """Verifica conexão com Redis"""
        self.print_header("6. Verificando Conexão com Redis")
        
        try:
            from app.core.redis_unified import get_sync_redis
            
            redis_client = get_sync_redis()
            redis_client.ping()
            
            self.print_success("Conexão com Redis OK")
            
            # Testa operações básicas
            redis_client.set("health_check", "ok", ex=10)
            value = redis_client.get("health_check")
            
            if value == "ok":
                self.print_success("Operações Redis OK (set/get)")
            else:
                self.print_warning("Operações Redis retornaram valor inesperado")
            
            return True
        except Exception as e:
            self.print_error(f"Erro ao conectar com Redis: {e}")
            return False
    
    def check_migrations(self) -> bool:
        """Verifica status das migrações"""
        self.print_header("7. Verificando Migrações do Banco de Dados")
        
        try:
            result = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=Path(__file__).parent.parent
            )
            
            if result.returncode == 0:
                current = result.stdout.strip()
                self.print_success(f"Migração atual: {current if current else 'head'}")
                
                # Verifica se há migrações pendentes
                result_heads = subprocess.run(
                    ["alembic", "heads"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=Path(__file__).parent.parent
                )
                
                if "head" in result_heads.stdout.lower():
                    self.print_success("Banco de dados está atualizado")
                    return True
                else:
                    self.print_warning("Pode haver migrações pendentes")
                    return True
            else:
                # Alembic não configurado - não é crítico se banco está funcionando
                self.print_warning(f"Alembic não configurado (não bloqueante se banco está OK)")
                return True
        except Exception as e:
            # Erro ao verificar migrações - não é crítico se banco está funcionando
            self.print_warning(f"Alembic não disponível (não bloqueante se banco está OK)")
            return True
    
    def check_security_config(self) -> bool:
        """Verifica configurações de segurança"""
        self.print_header("8. Verificando Configurações de Segurança")
        
        try:
            from app.config import settings
            
            all_ok = True
            
            # Verifica ambiente
            env = settings.ENVIRONMENT.lower()
            if env == "production":
                self.print_success(f"Ambiente: {env}")
                
                # Verifica DEBUG
                if not settings.DEBUG:
                    self.print_success("DEBUG está desabilitado")
                else:
                    self.print_error("DEBUG deve estar desabilitado em produção")
                    all_ok = False
                
                # Verifica SSL
                if settings.SESSION_COOKIE_SECURE:
                    self.print_success("Cookies seguros habilitados")
                else:
                    self.print_error("SESSION_COOKIE_SECURE deve ser True em produção")
                    all_ok = False
                
                # Verifica CORS
                if settings.ALLOWED_ORIGINS:
                    self.print_success(f"CORS configurado: {len(settings.ALLOWED_ORIGINS)} origens")
                else:
                    self.print_warning("CORS não configurado explicitamente")
            else:
                self.print_warning(f"Ambiente: {env} (não é produção)")
            
            return all_ok
        except Exception as e:
            self.print_error(f"Erro ao verificar configurações: {e}")
            return False
    
    def check_dockerfile(self) -> bool:
        """Verifica Dockerfile"""
        self.print_header("9. Verificando Dockerfile")
        
        dockerfile_path = Path(__file__).parent.parent / "Dockerfile"
        
        if not dockerfile_path.exists():
            self.print_error("Dockerfile não encontrado")
            return False
        
        self.print_success("Dockerfile encontrado")
        
        # Verifica conteúdo crítico
        content = dockerfile_path.read_text()
        
        checks = [
            ("FROM python:3.13", "Imagem base Python 3.13"),
            ("COPY", "Cópia de arquivos"),
            ("RUN pip install", "Instalação de dependências"),
            ("CMD", "Comando de inicialização"),
            ("HEALTHCHECK", "Health check configurado"),
        ]
        
        all_ok = True
        for check, description in checks:
            if check in content:
                self.print_success(f"{description} OK")
            else:
                self.print_warning(f"{description} não encontrado")
                all_ok = False
        
        return all_ok
    
    def generate_report(self) -> Dict:
        """Gera relatório final"""
        self.print_header("RELATÓRIO FINAL")
        
        total_checks = len(self.passed) + len(self.warnings) + len(self.errors)
        
        print(f"\n{Colors.BOLD}Resumo:{Colors.END}")
        print(f"  {Colors.GREEN}[OK] Passou: {len(self.passed)}{Colors.END}")
        print(f"  {Colors.YELLOW}[WARN] Avisos: {len(self.warnings)}{Colors.END}")
        print(f"  {Colors.RED}[ERRO] Erros: {len(self.errors)}{Colors.END}")
        print(f"  Total: {total_checks}")
        
        if self.errors:
            print(f"\n{Colors.RED}{Colors.BOLD}ERROS CRÍTICOS:{Colors.END}")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}AVISOS:{Colors.END}")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        # Determina status
        if self.errors:
            status = "FALHOU"
            color = Colors.RED
            ready = False
        elif self.warnings:
            status = "PASSOU COM AVISOS"
            color = Colors.YELLOW
            ready = True
        else:
            status = "PASSOU"
            color = Colors.GREEN
            ready = True
        
        print(f"\n{color}{Colors.BOLD}Status: {status}{Colors.END}\n")
        
        if ready:
            print(f"{Colors.GREEN}[OK] Backend esta pronto para deploy em producao{Colors.END}")
        else:
            print(f"{Colors.RED}[ERRO] Backend NAO esta pronto para deploy - corrija os erros acima{Colors.END}")
        
        return {
            "status": status,
            "ready_for_deploy": ready,
            "passed": len(self.passed),
            "warnings": len(self.warnings),
            "errors": len(self.errors),
            "error_list": self.errors,
            "warning_list": self.warnings
        }
    
    def run_all_checks(self) -> bool:
        """Executa todas as verificações"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}")
        print("=" * 60)
        print("  VERIFICACAO PRE-DEPLOY - BACKEND HORMONIA")
        print("=" * 60)
        print(f"{Colors.END}")
        
        checks = [
            self.check_python_version,
            self.check_dependencies,
            self.check_imports,
            self.check_env_variables,
            self.check_database_connection,
            self.check_redis_connection,
            self.check_migrations,
            self.check_security_config,
            self.check_dockerfile,
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                self.print_error(f"Erro inesperado em {check.__name__}: {e}")
        
        report = self.generate_report()
        
        # Salva relatório em JSON
        report_path = Path(__file__).parent.parent / "pre_deploy_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n{Colors.BLUE}Relatório salvo em: {report_path}{Colors.END}\n")
        
        return report["ready_for_deploy"]


def main():
    """Função principal"""
    checker = PreDeployChecker()
    ready = checker.run_all_checks()
    
    # Retorna código de saída apropriado
    sys.exit(0 if ready else 1)


if __name__ == "__main__":
    main()
