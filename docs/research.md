# Fundamento Científico — Triagem SXF

> Base clínica e estatística sobre a qual o sistema toma decisões.
> Fonte: pesquisa do Prof. Roberto Hirochi Herai e Luz Maria Romero (PUCPR / Instituto Buko Kaesemodel — IBK).

---

## 1. O que é a Síndrome do X Frágil (SXF)

Principal causa **hereditária** de deficiência intelectual. Afeta ~1/5.000 meninos e ~1/4.000–8.000 meninas.

Causa: expansão de repetições **CGG** no gene **FMR1**, que silencia a produção da proteína **FMRP** — essencial para a plasticidade sináptica.

| Repetições CGG | Status |
|---|---|
| 5–44 | Normal |
| 45–54 | Zona cinzenta |
| 55–200 | Pré-mutação |
| **> 200** | **Mutação completa** (silenciamento do gene) |

---

## 2. Por que existe este sistema

- Não há dados epidemiológicos consolidados de SXF no Brasil → **subdiagnóstico generalizado**.
- Testes confirmatórios (PCR, Southern Blot) são caros e de acesso limitado no SUS.
- Manifestação clínica varia muito → difícil identificar sem protocolo padronizado.

**O sistema oferece um checklist de baixo custo** que aponta quem deve ser encaminhado para o teste genético — otimizando recursos e acelerando o diagnóstico precoce.

> **Triagem ≠ diagnóstico.** A saída do sistema é "encaminhar / não encaminhar para exame", nunca "tem / não tem SXF".

---

## 3. Como os pesos foram obtidos

| Grupo | Tamanho |
|---|---|
| Banco IBK (2018–2023) | 1.229 indivíduos |
| **Coorte SXF confirmada** (mutação completa/mosaico) | **419** (364 ♂ + 55 ♀) |
| **Grupo controle** (sem SXF, incluindo TEA e outras condições) | **201** |

Diagnósticos confirmados por PCR e Southern Blotting.

**Métodos aplicados:**
- Estatística descritiva + correlação de Pearson
- **Random Forest** → importância de cada sintoma na classificação (origem dos pesos)
- Clustering (K-means + PCA) → agrupamento de padrões
- Validação por curva ROC

**Desempenho validado:**
- **Sensibilidade: 95%**
- AUC: **0,73** (♂) e **0,76** (♀)

---

## 4. Os 12 sintomas e seus pesos

| # | Sintoma | Peso ♂ | Peso ♀ |
|---|---|---:|---:|
| 1 | Deficiência intelectual | **0,32** | 0,20 |
| 2 | Face alongada / orelhas proeminentes | **0,29** | 0,09 |
| 3 | Macroorquidismo | **0,26** | — |
| 4 | Hipermobilidade articular | 0,19 | 0,04 |
| 5 | Dificuldades de aprendizagem | 0,18 | **0,28** |
| 6 | Déficit de atenção | 0,17 | 0,12 |
| 7 | Movimentos repetitivos | 0,17 | 0,05 |
| 8 | Atraso na fala | 0,14 | 0,01 |
| 9 | Hiperatividade | 0,12 | 0,04 |
| 10 | Evita contato visual | 0,06 | 0,08 |
| 11 | Evita contato físico | 0,04 | 0,07 |
| 12 | Agressividade | 0,01 | 0,02 |

> Macroorquidismo é exclusivo do sexo masculino — não se aplica a pacientes femininos.

### Limiares de corte

| Sexo | Limiar | Decisão |
|---|---:|---|
| Masculino | **≥ 0,56** | Encaminhar para teste genético |
| Feminino | **≥ 0,55** | Encaminhar para teste genético |

---

## 5. Fórmula

```
Score = Σ ( Peso_j × X_j )
```

- `X_j` = 1 se o sintoma j está presente, 0 caso contrário
- `Peso_j` = peso do sintoma j para o sexo do paciente
- Se `Score ≥ limiar(sexo)` → **ENCAMINHAR**

Implementação em [src/controllers/scoring.py](../src/controllers/scoring.py); seed dos sintomas e descrições clínicas em [src/controllers/seed_data.py](../src/controllers/seed_data.py).

---

## 6. Por que os pesos vivem no banco (e versionados)

A pesquisa pode evoluir — novos dados, recalibração, inclusão de sintomas. O sistema trata os pesos como **valores científicos versionados**:

- A versão **ativa** dos pesos é o que o formulário usa para calcular novas avaliações.
- Toda avaliação salva aponta para a versão que a calculou (`id_versao_pesos`).
- Versões antigas ficam **imutáveis** — avaliações históricas continuam reproduzíveis.

Quem administra: apenas usuários com perfil `admin`, via tela de Sintomas.

---

## 7. Sintomas mais prevalentes (referência clínica)

Da coorte estudada:
- Dificuldades de aprendizagem: **94% ♂ / ~90% ♀**
- Déficit de atenção: **~90% ♂ / ~80% ♀**
- Deficiência intelectual: **~90% ♂ / ~55% ♀**
- Face alongada / orelhas proeminentes: **~55% ♂ / ~20% ♀**
- Macroorquidismo: **~45% ♂** (sinal pós-puberal, exclusivo)

Homens tendem a apresentar manifestações **mais severas** que mulheres.

Correlação forte: deficiência intelectual ↔ dificuldades de aprendizagem (**r = 0,59**); o núcleo cognitivo-comportamental co-ocorre em **>70%** dos casos.
