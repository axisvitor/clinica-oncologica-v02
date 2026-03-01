# Revisao de Perguntas de Fluxo (Banco Real)

- Gerado em: 2026-02-09T18:24:27.428035+00:00
- Fonte: `flow_template_versions.steps` ativos + `flow_kinds` ativos
- Criterio de pergunta canonica: `expects_response = true`

## Resumo

- Templates ativos: 3
- Mensagens totais: 50
- Perguntas canonicas (`expects_response=true`): 30
- Mensagens com "?" mas `expects_response=false`: 0
- Perguntas canonicas sem "?": 2
- Mensagens vazias: 0
- Grupos de perguntas duplicadas (texto normalizado): 0

## Cobertura por Flow

| Flow | Dias | Mensagens | Perguntas | `?` com expects=false | expects=true sem `?` |
|---|---:|---:|---:|---:|---:|
| daily_follow_up | 16 | 17 | 11 | 0 | 0 |
| onboarding | 9 | 24 | 11 | 0 | 0 |
| quiz_mensal | 9 | 9 | 8 | 0 | 2 |

## Todas as Perguntas Canonicas (expects_response=true)

- `daily_follow_up` dia `16` ordem `1` (send_mode: `wait_each`): Oi [nome], espero que esteja tudo certo por aí.
Quero registrar como você está hoje. Como você tem se sentido?
- `daily_follow_up` dia `16` ordem `2` (send_mode: `wait_each`): Tem alguma dúvida ou algo importante que você gostaria de registrar agora?
- `daily_follow_up` dia `18` ordem `1` (send_mode: `single`): Oi [nome], já ouviu falar que alguns chás podem interferir no tratamento?
Tipo hibisco ou prímula…
Se tiver dúvidas sobre algum alimento, bebida ou suplemento, pode perguntar!
Posso te responder com base no seu protocolo 😉
- `daily_follow_up` dia `20` ordem `1` (send_mode: `single`): [nome], bora de desafio rápido?
Responda com: ✅ sim | ❌ não | 🤔 às vezes
➤ Conseguiu manter alguma rotina de movimento nas últimas semanas?
- `daily_follow_up` dia `22` ordem `1` (send_mode: `single`): Muita gente pergunta se pode começar alguma atividade física leve.
[nome], seu médico indicou alguma limitação ou recomendou algo específico?
Se quiser compartilhar, posso ajudar com sugestões seguras e adaptadas à sua realidade.
- `daily_follow_up` dia `26` ordem `1` (send_mode: `single`): Me conta uma coisa: tem algo que você sempre quis perguntar, mas ficou com vergonha ou achou que era bobeira?
Tipo: “Será que posso usar óleo de prímula?”
Aqui é espaço livre — pode perguntar mesmo. 😉
- `daily_follow_up` dia `30` ordem `1` (send_mode: `single`): Estamos chegando na marca de 1 mês de acompanhamento!
Você já tem próxima consulta marcada? Se sim, pra quando?
Se ainda não, posso te lembrar mais pra frente, combinado?
- `daily_follow_up` dia `32` ordem `1` (send_mode: `single`): Oi [nome], você recebeu alguma orientação alimentar do profissional que te acompanha?
Se sim, como tem sido seguir? Se não recebeu nenhuma indicação, tudo bem também — só quero conhecer seu momento atual 😉
- `daily_follow_up` dia `34` ordem `1` (send_mode: `single`): Me conta uma coisa: mudou algo na sua rotina física nas últimas semanas?
Qualquer mudança já importa — desde levantar mais vezes até uma caminhada leve.
Isso ajuda bastante no acompanhamento.
- `daily_follow_up` dia `40` ordem `1` (send_mode: `single`): Vamos fazer um termômetro rapidinho?
De 1 a 5, como está sua motivação com o tratamento nesses últimos dias?
(1 = tá difícil | 5 = tô firme no foco)
Me responde com o número!
- `daily_follow_up` dia `45` ordem `1` (send_mode: `single`): Chegou o momento do nosso checkup mensal 🩺
Vou te fazer algumas perguntas — elas são confidenciais, automáticas, e vão direto pra equipe médica.
Assim a consulta rende mais e seu cuidado fica muito mais eficaz.
Podemos começar?
- `onboarding` dia `3` ordem `1` (send_mode: `wait_response`): Oi [NOME], passando aqui só pra saber como você tá se sentindo nesse início?
Se tiver tudo tranquilo, ótimo! Se quiser comentar algo diferente, já posso anotar.
- `onboarding` dia `5` ordem `1` (send_mode: `wait_response`): Opa, [NOME], bom dia!
Você tá conseguindo seguir certinho o esquema que o médico passou? Tipo:
• Aplicação
• Medicação oral
• Orientações gerais
- `onboarding` dia `7` ordem `1` (send_mode: `single`): Bom dia, [NOME]!
Tem algo que você gostaria que eu te lembrasse?
• Data da aplicação
• Consulta ou exame
• Remédio em horário específico
Me responde o que quiser que eu já programo aqui pra você.
- `onboarding` dia `9` ordem `1` (send_mode: `wait_response`): Ei, [NOME], tudo certo por aí?
Se em algum momento quiser compartilhar como anda a rotina, mesmo que pareça algo pequeno, pode mandar por aqui.
- `onboarding` dia `11` ordem `1` (send_mode: `single`): Oi, [NOME]!
Tem algo que você queira anotar hoje? Algum comentário, dúvida ou mudança de rotina?
Pode compartilhar por aqui, mesmo que pareça simples. Isso também entra no relatório e ajuda bastante no acompanhamento.
- `onboarding` dia `13` ordem `1` (send_mode: `single`): Oi [NOME], tudo certo?
Lembrando que você pode me escrever a qualquer momento — dúvidas sobre o tratamento, orientações, ou até uma nota pessoal que quiser guardar pro médico.
Se quiser, é só digitar por aqui 📩
- `onboarding` dia `15` ordem `1` (send_mode: `wait_each`): [NOME], hoje completamos 15 dias da sua jornada com a Hormon[IA] 🎉
Quero aproveitar pra registrar algumas informações importantes. Vou te fazer algumas perguntas rapidinho.
Você tem alguma consulta ou exame marcado nas próximas semanas que gostaria que eu lembrasse?
- `onboarding` dia `15` ordem `2` (send_mode: `wait_each`): Seu médico indicou alguma mudança na alimentação?
- `onboarding` dia `15` ordem `3` (send_mode: `wait_each`): Se sim, como tá sendo manter essa parte da rotina?
- `onboarding` dia `15` ordem `4` (send_mode: `wait_each`): E sobre atividade física — teve alguma recomendação?
- `onboarding` dia `15` ordem `5` (send_mode: `wait_each`): Tá conseguindo se movimentar de alguma forma no dia a dia?
- `quiz_mensal` dia `1` ordem `1` (send_mode: `single`): Oi [NOME], tudo bem por aí? ✨
Começamos mais um ciclo juntinhos! 😌
A cada mês, nosso objetivo é acompanhar sua jornada com leveza, respeito e inteligência — tudo no seu ritmo.
E no fim do mês, vamos fazer um Checkup completo que ajuda você e seu médico a enxergarem o todo com mais clareza.
Mas por enquanto, só queria mesmo saber:
Como foi o último mês pra você?
Pode responder com uma palavra ou contar um pouquinho, se quiser 💬
- `quiz_mensal` dia `4` ordem `1` (send_mode: `single`): [NOME], sabia que alguns estudos mostram que caminhar 15 minutos por dia pode reduzir sintomas de ansiedade, melhorar o humor e até auxiliar no sono?
Claro, cada corpo é único e nada substitui as orientações do seu médico 🩺
Me conta uma coisa:
Você tem conseguido se movimentar um pouco durante a semana?
( ) Sim, tenho praticado algum exercício
( ) Só pequenas caminhadas ou alongamentos
( ) Não, ainda não consegui encaixar isso na rotina
- `quiz_mensal` dia `8` ordem `1` (send_mode: `single`): Oi [NOME], hoje passei só pra perguntar:
Como você está se sentindo consigo mesmo(a)?
Pode ser sincero(a), sem pressão…
Ah, e queria te lembrar de uma coisa importante:
Cada vez que você interage comigo, conseguimos manter um histórico valioso que vira um relatório completo pro seu médico. Isso pode antecipar decisões, evitar esquecimentos e melhorar sua consulta.
- `quiz_mensal` dia `11` ordem `1` (send_mode: `single`): Se você pudesse descrever sua rotina hoje com uma imagem, seria:
🧘 Um mar calmo
🌀 Um redemoinho
☀️ Um dia ensolarado
☁️ Um tempo nublado
🔥 Um vulcão em erupção
Ou... outro cenário? Me conta. Quero te ouvir. 😄
- `quiz_mensal` dia `15` ordem `1` (send_mode: `single`): Já ouviu falar do “autodiálogo positivo”?
É quando a gente treina a mente pra se tratar com mais carinho.
Exemplos simples como:
“Hoje eu fiz o meu melhor”
“Meu corpo está fazendo o possível”
“É normal ter dias bons e dias difíceis”
Experimente repetir um desses em voz alta. Pode parecer bobo, mas isso muda muita coisa por dentro.
Se quiser criar o seu próprio mantra do mês, me conta que eu guardo aqui com carinho 💬
- `quiz_mensal` dia `22` ordem `1` (send_mode: `single`): [NOME], bora de enquete rápida:
📱 Na sua rotina, você prefere:
( ) Que eu apareça mais com lembretes, dicas e curiosidades
( ) Que eu só fale quando for algo essencial
( ) Um equilíbrio entre os dois
Isso me ajuda a te respeitar e te acompanhar da melhor forma 💬
- `quiz_mensal` dia `26` ordem `1` (send_mode: `single`): Tá chegando a hora…
📊 O Checkup mensal abre em breve!
É um questionário simples, dividido por áreas como alimentação, sono, sintomas, memória, rotina, etc.
Você só precisa de 10 minutinhos e vai se surpreender com a clareza que ele traz — pra você e pro seu médico.
Posso contar com você pra responder assim que abrir?
- `quiz_mensal` dia `30` ordem `1` (send_mode: `single`): [NOME], chegou o momento mais importante do mês!
🎯 Clique abaixo para responder seu Checkup Mensal.
É rápido, seguro e vai fazer toda diferença no acompanhamento médico.
[LINK DO QUIZ]
Quando terminar, me avisa! Vou te parabenizar como merece 👏

## Inconsistencias Funcionais

### `expects_response=false` com texto interrogativo (`?`)
- Nenhuma

### `expects_response=true` sem `?`
- `quiz_mensal` dia `22` ordem `1`: [NOME], bora de enquete rápida:
📱 Na sua rotina, você prefere:
( ) Que eu apareça mais com lembretes, dicas e curiosidades
( ) Que eu só fale quando for algo essencial
( ) Um equilíbrio entre os dois
Isso me ajuda a te respeitar e te acompanhar da melhor forma 💬
- `quiz_mensal` dia `30` ordem `1`: [NOME], chegou o momento mais importante do mês!
🎯 Clique abaixo para responder seu Checkup Mensal.
É rápido, seguro e vai fazer toda diferença no acompanhamento médico.
[LINK DO QUIZ]
Quando terminar, me avisa! Vou te parabenizar como merece 👏

### Perguntas Duplicadas (texto normalizado)
- Nenhuma
