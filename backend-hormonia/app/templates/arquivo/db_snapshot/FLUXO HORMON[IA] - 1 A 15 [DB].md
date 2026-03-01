# Snapshot DB - onboarding

- Template: Initial 15 Days Onboarding Flow | Versão: 1
- Gerado em: 2026-01-27T20:09:36.765352-03:00

## Dia 1
- send_mode: `sequential_auto`
- mensagens: 3

**Mensagem 1**
- expects_response: `False`

Oi [NOME], espero que esteja tudo bem por aí.
Sou a Hormon[IA], sua assistente pessoal no acompanhamento com bloqueio hormonal.

**Mensagem 2**
- expects_response: `False`

Vou te lembrar das datas importantes, registrar tudo que você quiser compartilhar e te ajudar a manter o controle da rotina.
Você vai poder compartilhar sobre alimentação, sono, dúvidas… e tudo isso vira um relatório que será enviado pro seu médico antes da consulta.

**Mensagem 3**
- expects_response: `False`

Fica tranquilo(a): a gente só vai se falar algumas vezes por semana e sempre com um propósito.
Essa é uma ferramenta pensada pra tornar sua jornada mais leve e organizada — sem pressão nenhuma.

## Dia 2
- send_mode: `sequential_auto`
- mensagens: 5

**Mensagem 1**
- expects_response: `False`

[NOME], deixa eu te explicar direitinho como essa assistente pode facilitar (e muito) o seu tratamento:

**Mensagem 2**
- expects_response: `False`

🧾 Tudo que você responder aqui vira um relatório automático que vai direto para o seu médico. Isso evita que você esqueça detalhes na consulta e ajuda ele a tomar decisões melhores com base na sua vivência real.

**Mensagem 3**
- expects_response: `False`

⏱️ Se quiser, posso te lembrar de datas de medicação, exames ou qualquer coisa da sua rotina.

**Mensagem 4**
- expects_response: `False`

📊 Além disso, conforme você responde por aqui, eu consigo te mostrar gráficos com sua evolução. Isso ajuda tanto você quanto o médico a verem tudo com mais clareza.

**Mensagem 5**
- expects_response: `False`

💙 E o mais importante: tudo isso foi criado pra te acompanhar de um jeito leve, sem invadir sua privacidade.
As interações são rápidas, sem cobrança. Mas quanto mais você participa, mais eficiente isso tudo fica.

## Dia 3
- send_mode: `wait_response`
- mensagens: 2

**Mensagem 1**
- expects_response: `True`

Oi [NOME], passando aqui só pra saber como você tá se sentindo nesse início?
Se tiver tudo tranquilo, ótimo! Se quiser comentar algo diferente, já posso anotar.

**Mensagem 2**
- expects_response: `False`

Lembrando que tudo que você compartilha comigo é automaticamente enviado no relatório pro seu médico — então mesmo detalhes simples podem fazer diferença na hora da consulta.

## Dia 5
- send_mode: `wait_response`
- mensagens: 2

**Mensagem 1**
- expects_response: `True`

Opa, [NOME], bom dia!
Você tá conseguindo seguir certinho o esquema que o médico passou? Tipo:
• Aplicação
• Medicação oral
• Orientações gerais

**Mensagem 2**
- expects_response: `False`

Se tiver tudo sob controle, excelente!
Se tiver algum ponto fora do ritmo, posso te ajudar com lembretes ou com o que for útil pra você.

## Dia 7
- send_mode: `single`
- mensagens: 1

**Mensagem 1**
- expects_response: `True`

Bom dia, [NOME]!
Tem algo que você gostaria que eu te lembrasse?
• Data da aplicação
• Consulta ou exame
• Remédio em horário específico
Me responde o que quiser que eu já programo aqui pra você.

## Dia 9
- send_mode: `wait_response`
- mensagens: 3

**Mensagem 1**
- expects_response: `True`

Ei, [NOME], tudo certo por aí?
Se em algum momento quiser compartilhar como anda a rotina, mesmo que pareça algo pequeno, pode mandar por aqui.

**Mensagem 2**
- expects_response: `False`

Tudo que você compartilha comigo já entra no seu relatório automático. Isso facilita demais pro seu médico e evita que alguma coisa passe batida na consulta.

**Mensagem 3**
- expects_response: `False`

Você não precisa lembrar de tudo sozinho(a). Eu cuido disso por aqui 💡

## Dia 11
- send_mode: `single`
- mensagens: 1

**Mensagem 1**
- expects_response: `True`

Oi, [NOME]!
Tem algo que você queira anotar hoje? Algum comentário, dúvida ou mudança de rotina?
Pode compartilhar por aqui, mesmo que pareça simples. Isso também entra no relatório e ajuda bastante no acompanhamento.

## Dia 13
- send_mode: `single`
- mensagens: 1

**Mensagem 1**
- expects_response: `True`

Oi [NOME], tudo certo?
Lembrando que você pode me escrever a qualquer momento — dúvidas sobre o tratamento, orientações, ou até uma nota pessoal que quiser guardar pro médico.
Se quiser, é só digitar por aqui 📩

## Dia 15
- send_mode: `wait_each`
- mensagens: 5

**Mensagem 1**
- expects_response: `False`

[NOME], hoje completamos 15 dias da sua jornada com a Hormon[IA] 🎉
Quero aproveitar pra registrar algumas informações importantes. Vou te fazer algumas perguntas rapidinho.

**Mensagem 2**
- expects_response: `True`

Você tem alguma consulta ou exame marcado nas próximas semanas que gostaria que eu lembrasse?

**Mensagem 3**
- expects_response: `True`

Seu médico indicou alguma mudança na alimentação?
Se sim, como tá sendo manter essa parte da rotina?

**Mensagem 4**
- expects_response: `True`

E sobre atividade física — teve alguma recomendação?
Tá conseguindo se movimentar de alguma forma no dia a dia?

**Mensagem 5**
- expects_response: `False`

Tudo que você respondeu aqui já foi registrado no relatório pro seu médico.
Isso vai deixar a próxima consulta muito mais clara — e você ainda ganha mais controle da sua própria evolução 💙
