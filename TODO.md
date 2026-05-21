# TODO

## Geral
- [ ] Implementar versão mobile
- [ ] Realizar testes de usabilidade
- [ ] Review avançada de UX (comportamento das telas, fields, botões, autocompletes, etc)
- [ ] Disparo de e-mail para recuperação de senha
- [ ] Exibir dados do responsável quando existir
- [ ] Nos relatórios, incluir filtros relacionados às versões
- [ ] Garantir que sempre exista ao menos um admin no sistema (o último admin não pode ser deletado, desativado, nem ter o cargo alterado)
- [ ] Remover botões redundantes (mais de um botão na mesma tela executando a mesma ação)
- [ ] Corrigir problemas de responsividade com valores grandes em certos fields

## Histórico Familiar

### Heredograma (árvore genealógica clínica)
- [ ] Heredograma interativo no padrão de genética médica (símbolos: quadrado/círculo, preenchido = afetado)
- [ ] Montagem por drag-and-drop com cálculo automático do grau de parentesco
- [ ] Cada nó clicável exibindo condições, idade de diagnóstico, idade e causa do óbito
- [ ] Exportar heredograma como imagem para anexar ao prontuário

### Análise de risco hereditário
- [ ] Cálculo automático de risco a partir dos parentes afetados (critérios tipo Bethesda/Amsterdam, Gail/Tyrer-Cuzick)
- [ ] Alerta visual quando o padrão familiar sugere doença genética (ex.: 3 parentes de 1º grau com a mesma condição)
- [ ] Sugestão de exames de rastreio com base no histórico (ex.: histórico de Lynch → colonoscopia precoce)
- [ ] Score de "carga familiar" para condições comuns (DM, HAS, cardiopatia)

### Padrões de herança
- [ ] Identificação automática do padrão (autossômico dominante/recessivo, ligado ao X) a partir da árvore
- [ ] Cálculo da probabilidade do paciente carregar o alelo
- [ ] Sinalização de consanguinidade

### Compartilhamento entre pacientes da mesma família
- [ ] Vincular pacientes que são parentes; o histórico de um alimenta o do outro automaticamente
- [ ] Alerta para parentes quando um membro da família recebe um diagnóstico novo ("atualize seu histórico familiar")
- [ ] Privacidade granular: paciente escolhe o que compartilha e com quem

### Coleta inteligente
- [ ] Questionário guiado em árvore ("seu pai teve X? e os irmãos do seu pai?") em vez de campo livre
- [ ] Importar histórico de outro paciente já cadastrado (irmão preenche, paciente novo herda a base)
- [ ] Detecção de inconsistência entre membros da família (datas/idades divergentes para o mesmo parente)

### Visualização e insights
- [ ] Timeline da família mostrando em que idade cada parente desenvolveu cada condição (janela de risco)
- [ ] Heatmap geográfico com a origem dos parentes (doenças com prevalência regional)
- [ ] Comparativo: "pacientes com perfil familiar parecido tiveram qual evolução?"

### Diferenciais clínicos
- [ ] Integração com bases de doenças genéticas (OMIM, Orphanet) com auto-sugestão de hipóteses
- [ ] Geração de carta de encaminhamento para geneticista já com o resumo do heredograma
- [ ] Versionamento do histórico familiar (novos diagnósticos, óbitos — manter histórico do histórico)
