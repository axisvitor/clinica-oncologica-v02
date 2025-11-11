# Perguntas dos Primeiros 15 Dias - Sistema de Acompanhamento

**Data de Extração:** 11/11/2025

## Status dos Templates de Fluxo

### Templates Ativos Encontrados:
1. **Initial 15 Days Onboarding Flow** (initial_15_days) - Version 2
2. **Days 16-45 Engagement Flow** (days_16_45) - Version 2  
3. **Monthly Recurring Maintenance Flow** (monthly_recurring) - Version 2

⚠️ **IMPORTANTE:** Nenhum desses templates possui mensagens cadastradas na tabela `flow_messages`.

## Quiz Templates Ativos

### 1. Check-in Diário
**Categoria:** daily_checkin  
**Descrição:** Questionário diário para acompanhamento do paciente

#### Perguntas:

**Pergunta 1:** Como você está se sentindo hoje?
- Opções:
  - 😊 Muito bem
  - 🙂 Bem
  - 😐 Normal
  - 😔 Não muito bem
  - 😞 Mal

**Pergunta 2:** Como está seu nível de energia?

**Pergunta 3:** Você tomou sua medicação hoje?

---

### 2. Avaliação Mensal Abrangente (monthly_comprehensive)
**Categoria:** general_health  
**Descrição:** Comprehensive monthly health assessment for hormone therapy patients

#### Perguntas:

**Pergunta 1:** Como você avaliaria seu bem-estar geral neste último mês?

**Pergunta 2:** Como têm estado seus níveis de energia?
- Opções:
  - Muito baixos - sinto-me constantemente cansada (valor: 1)
  - Baixos - tenho pouca disposição (valor: 2)
  - Moderados - alguns dias melhor que outros (valor: 3)
  - Bons - sinto-me disposta na maior parte do tempo (valor: 4)
  - Excelentes - tenho muita energia e disposição (valor: 5)

**Pergunta 3:** Como você descreveria suas mudanças de humor no último mês?
- Opções:
  - Muito instáveis - mudanças bruscas e frequentes (valor: 1)
  - Um pouco instáveis - algumas oscilações (valor: 2)
  - Estáveis - humor consistente (valor: 3)
  - Muito estáveis - me sinto equilibrada (valor: 4)

**Pergunta 4:** Como tem sido a qualidade do seu sono?
- Opções:
  - Muito ruim - acordo várias vezes, não me sinto descansada (valor: 1)
  - Ruim - tenho dificuldades para dormir ou manter o sono (valor: 2)
  - Regular - durmo, mas não sempre bem (valor: 3)
  - Bom - durmo bem na maioria das noites (valor: 4)
  - Excelente - durmo profundamente e acordo descansada (valor: 5)

**Pergunta 5:** Quais sintomas físicos você tem sentido mais?
- Opções (múltipla escolha):
  - Ondas de calor
  - Dores de cabeça
  - Dores nas articulações
  - Sensibilidade nos seios
  - Inchaço/retenção de líquidos
  - Nenhum sintoma significativo

**Pergunta 6:** Como tem sido sua adesão ao tratamento hormonal?
- Opções:
  - Perfeita - tomo sempre no horário correto (valor: 5)
  - Muito boa - raramente esqueço (valor: 4)
  - Boa - às vezes esqueço, mas recupero rapidamente (valor: 3)
  - Regular - esqueço com alguma frequência (valor: 2)
  - Ruim - esqueço frequentemente (valor: 1)

**Pergunta 7:** Você tem sentido algum efeito colateral que gostaria de relatar?
- Resposta aberta

**Pergunta 8:** Houve alguma mudança importante na sua rotina ou estilo de vida neste mês?
- Resposta aberta

**Pergunta 9:** Há alguma preocupação ou pergunta que você gostaria de compartilhar com sua equipe médica?
- Resposta aberta

**Pergunta 10:** O quanto você está satisfeita com seu tratamento atual?
- Escala de satisfação

---

## Observações

1. **Templates de Fluxo Vazios:** Os templates de fluxo (initial_15_days, days_16_45, monthly_recurring) estão criados mas não possuem mensagens cadastradas. Isso sugere que:
   - As mensagens podem estar sendo geradas dinamicamente pelo código
   - As mensagens podem estar em outro formato/tabela
   - O sistema pode estar em fase de configuração

2. **Quiz Templates Ativos:** Existem 2 quiz templates funcionais que podem ser usados para acompanhamento diário e mensal dos pacientes.

3. **Próximos Passos Recomendados:**
   - Verificar se há mensagens hardcoded no código da aplicação
   - Verificar se o sistema usa outro mecanismo para enviar mensagens dos primeiros 15 dias
   - Popular a tabela `flow_messages` com as mensagens do fluxo de onboarding
