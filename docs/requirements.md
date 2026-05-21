# Requisitos — Triagem SXF

> Escopo funcional do sistema: quem usa, o que cada um faz, e quais regras de negócio governam essas ações.

---

## 1. Atores

| Ator | Perfil | O que pode fazer |
|---|---|---|
| **Profissional de saúde** | `padrao` | Cadastrar e editar **seus** pacientes, registrar avaliações, ver histórico e relatórios **dos próprios** pacientes |
| **Administrador** | `admin` | Tudo do profissional **+** gerenciar usuários, gerenciar catálogo de sintomas e versões de pesos, ver auditoria, ver relatórios de **todos os usuários**, restaurar pacientes removidos |

---

## 2. Casos de uso principais

```
Login → Cadastrar Paciente → Nova Avaliação (12 sintomas) → Score + Recomendação
                                                                     ↓
                                                            Salva no histórico
                                                                     ↓
                                                          Relatório / Exportação
```

---

## 3. Requisitos Funcionais

### Autenticação e usuários

| ID | Descrição |
|---|---|
| RF01 | Login com e-mail e senha; bloqueio após 5 falhas em 15 minutos |
| RF02 | Reset de senha por token enviado (validade 1 hora) |
| RF03 | Política mínima de senha: ≥ 8 caracteres, ao menos 1 letra e 1 número |
| RF04 | Admin cadastra, edita e remove outros usuários; define o perfil (`admin` / `padrao`) |
| RF05 | Cada usuário escolhe seu tema (claro / escuro / auto) e a escolha é persistida |

### Pacientes

| ID | Descrição |
|---|---|
| RF06 | Cadastrar paciente: nome, CPF (único), sexo (M/F), data de nascimento, responsável |
| RF07 | Cadastro exige **termo de consentimento LGPD** explícito |
| RF08 | Editar dados do paciente já cadastrado |
| RF09 | Soft delete: paciente removido fica oculto mas pode ser **restaurado por admin** |
| RF10 | Profissional só enxerga os pacientes que ele mesmo cadastrou; admin enxerga todos |

### Avaliações

| ID | Descrição |
|---|---|
| RF11 | Formulário de avaliação lista os 12 sintomas com tooltip de descrição clínica |
| RF12 | Apenas sintomas com peso definido para o sexo do paciente são apresentados |
| RF13 | Sistema calcula o score automaticamente ao salvar a avaliação |
| RF14 | Sistema exibe a recomendação **ENCAMINHAR** ou **NÃO ENCAMINHAR** com base no limiar do sexo |
| RF15 | Cada avaliação fica vinculada à **versão de pesos** vigente no momento (reprodutibilidade) |
| RF16 | Consultar histórico de avaliações de um paciente |

### Relatórios

| ID | Descrição |
|---|---|
| RF17 | Filtros: data, paciente, profissional, sexo, faixa etária, recomendação, score, sintomas presentes |
| RF18 | 6 gráficos interativos: avaliações por mês, por recomendação, por sexo, histograma de score, sintomas mais frequentes, por profissional |
| RF19 | Exportação em **PDF** (com gráficos) |
| RF20 | Exportação em **Excel** (com gráficos) |
| RF21 | Modo LGPD nas exportações: nome e CPF mascarados |

### Administração

| ID | Descrição |
|---|---|
| RF22 | Admin gerencia o catálogo de sintomas (label, descrição clínica, pesos M/F) |
| RF23 | Admin publica uma nova versão de pesos; versão anterior fica imutável |
| RF24 | Admin consulta a tabela de auditoria com filtros por usuário, ação e entidade |

---

## 4. Requisitos Não Funcionais

| ID | Categoria | Descrição |
|---|---|---|
| RNF01 | Segurança | Senhas armazenadas com hash (werkzeug); nunca em texto plano |
| RNF02 | Segurança | Proteção CSRF global em formulários |
| RNF03 | Segurança | Controle de acesso por perfil aplicado nos controllers (não só no template) |
| RNF04 | Conformidade | Auditoria explícita das ações sensíveis (CREATE, UPDATE, DELETE, LOGIN, LOGIN_FALHO, LOGOUT) |
| RNF05 | Conformidade | LGPD: consentimento explícito no cadastro de paciente; mascaramento nas exportações |
| RNF06 | Compatibilidade | Funcionar em Chrome, Firefox e Edge atualizados |
| RNF07 | Operação | Subir com um único comando (`docker compose up -d`) |
| RNF08 | Manutenibilidade | Pesos científicos versionados — avaliações antigas reproduzíveis após atualização do modelo |

---

## 5. Regras de Negócio

| ID | Regra |
|---|---|
| RN01 | Pesos e limiares são **valores científicos validados** (Herai/PUCPR). Não devem ser alterados sem nova publicação de versão por admin. |
| RN02 | Macroorquidismo só se aplica a pacientes do **sexo masculino**. |
| RN03 | Existe **apenas uma versão de pesos ativa** por vez; ao publicar uma nova, a anterior é desativada (não excluída). |
| RN04 | CPF do paciente é **único** no sistema. |
| RN05 | Paciente "removido" não aparece em listas comuns, mas seu histórico de avaliações é preservado para auditoria. |
| RN06 | Profissional padrão **nunca** vê dados de pacientes de outro profissional. |
| RN07 | Login bloqueado após **5 falhas em 15 minutos** para o mesmo e-mail. |
| RN08 | Token de reset de senha expira em **1 hora** e é de uso único. |
| RN09 | A recomendação é **sempre** derivada do score e do limiar do sexo — nunca editada manualmente. |

---

## 6. Fora de escopo

- Diagnóstico definitivo (o sistema **não** substitui PCR / Southern Blot).
- Prescrição médica, prontuário eletrônico completo, integração com sistemas hospitalares.
- Versão mobile nativa (planejada — ver [TODO.md](../TODO.md)).
- Notificação por e-mail/SMS para pacientes.
