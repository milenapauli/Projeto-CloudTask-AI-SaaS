# Checklist LGPD + segurança — CloudTask AI SaaS

Lista de verificação para a entrega final. Marque cada item. É um material
**didático e introdutório** — não substitui assessoria jurídica real.

> Base conceitual: [`../conceitos/security-model.md`](../conceitos/security-model.md).

---

## 1. Dados pessoais — mapeamento

- [X] Sei **quais** dados pessoais a aplicação coleta (no CloudTask: praticamente
      nenhum — tarefas são texto livre; cuidado se o usuário digitar dados
      pessoais no título/descrição).
- [X] Sei **onde** cada dado é armazenado (PostgreSQL/RDS, S3, DynamoDB).
- [X] Sei **por quanto tempo** os dados ficam (retenção) e **como** são apagados.

## 2. Bases legais e finalidade (LGPD art. 6–11)

- [X] A coleta tem **finalidade específica** e informada.
- [X] Há **base legal** (consentimento, execução de contrato, etc.) — em projeto
      didático, documentar a finalidade já cumpre o exercício.

## 3. Segurança técnica (LGPD art. 46 — medidas de segurança)

- [X] **Em trânsito:** TLS/HTTPS na borda (ALB + ACM). Sem dado em HTTP aberto.
- [X] **Em repouso:** criptografia ativa — S3 (`S3_MANAGED`), RDS (encryption),
      DynamoDB (padrão). Confirme nos recursos criados.
- [X] **Segredos** não estão no código nem no git: `.env` e `secret.yaml` no
      `.gitignore`; em produção, Secrets Manager / SSM.
- [X] **Bucket S3 privado** (Block Public Access), acesso só por URL pré-assinada.
- [X] **Credenciais temporárias** (roles) em vez de chaves fixas no deploy.
- [X] **Menor privilégio**: a app/role acessa só o que precisa.

## 4. Direitos do titular (LGPD art. 18)

- [X] Existe caminho para **acessar** os dados de um titular (ex.: consultar/
      exportar suas tarefas).
- [X] Existe caminho para **excluir** (DELETE de tarefas + remoção de uploads).
- [X] Logs de eventos (DynamoDB) **não** guardam dado sensível desnecessário.

## 5. Operação e incidentes

- [X] **Backups** definidos (RDS tem snapshot automático; S3 versionado).
- [X] Sei **como reagir** a um vazamento (revogar credencial, rotacionar segredo).
- [ ] **Cost/uso** monitorado (Budgets) — evita surpresa e uso indevido.
      Obs.: o AWS Academy Learner Lab não permite acesso ao Billing/AWS Budgets.

## 6. Higiene de projeto

- [X] Nenhuma **conta AWS real** ou **segredo** commitado (revisar histórico).
- [X] Recursos de teste **destruídos** após cada aula (sem dado órfão na nuvem).
- [X] `README` e docs **não** expõem endpoints/credenciais internos.

---

> ✅ **Entrega:** anexe este checklist preenchido ao
> [`final-report-template.md`](final-report-template.md).
