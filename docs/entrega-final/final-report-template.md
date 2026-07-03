# Relatório final — CloudTask AI SaaS

> **Template de entrega** (Aula 12). Copie este arquivo, preencha as seções e
> entregue conforme a orientação da disciplina. Substitua os `<...>`.

---

## 1. Identificação

- **Aluno(a):** Milena Pauli Batista
- **RU / matrícula:** 3371798
- **Disciplina:** Computação em Nuvem — UNINTER
- **Repositório:** https://github.com/milenapauli/Projeto-CloudTask-AI-SaaS
- **Data:** 02/07/2026

## 2. Resumo do projeto

O CloudTask AI SaaS é uma aplicação desenvolvida ao longo da disciplina de Computação em Nuvem para gerenciamento de tarefas. O projeto utiliza FastAPI, PostgreSQL, Docker e Kubernetes, além de serviços da AWS como Amazon S3, Amazon ECR, Amazon EKS, Amazon RDS, Amazon DynamoDB e AWS CDK, demonstrando conceitos de infraestrutura em nuvem, containerização, armazenamento e infraestrutura como código.

## 3. O que foi implementado (por semana)

| Semana | Entreguei | Evidência (print / comando / endpoint) |
| --- | --- | --- |
| 1 — FastAPI + Docker | API criada e containerizada com Docker | docs/screenshots/swagger-ui.png e docs/screenshots/docker-compose.png |
| 2 — PostgreSQL + config | Banco PostgreSQL e configuração via .env | docs/screenshots/rds-banco.png |
| 3 — S3 + Kind | Upload para S3 e Kubernetes local | docs/screenshots/s3-bucket.png e docs/screenshots/k8s-pods.png |
| 4 — ECR + EKS | Publicação da imagem no ECR e deploy no EKS | docs/screenshots/ecr-imagem.png, docs/screenshots/eks-loadbalancer.png |
| 5 — HPA + DynamoDB | Autoscaling e eventos em DynamoDB | docs/screenshots/hpa-scaling.png |
| 6 — CDK + entrega | Infraestrutura como código, documentação e limpeza dos recursos | docs/screenshots/limpeza-recursos_cloud.png e deployment-checklist.md |

## 4. Arquitetura
A aplicação foi desenvolvida utilizando FastAPI e Docker, sendo implantada no Amazon EKS. O PostgreSQL (Amazon RDS) é responsável pelo armazenamento das tarefas, o Amazon S3 armazena os arquivos enviados pelos usuários e o Amazon DynamoDB registra os eventos da aplicação. As imagens Docker foram publicadas no Amazon ECR e toda a infraestrutura foi criada utilizando AWS CDK.

                    Usuário
                      │
                      ▼
          Kubernetes (Amazon EKS)
                      │
               FastAPI (Docker)
                       │
        ┌──────────────┬───────────────┬──────────────┐
        ▼              ▼               ▼              ▼
  RDS PostgreSQL   Amazon S3      DynamoDB        ECR (imagem)
  (tarefas)        (uploads)      (eventos/logs)  (origem do deploy)


Infraestrutura provisionada utilizando AWS CDK.


## 5. Como executar (reprodutível)

```bash
# Clonar o repositório
git clone https://github.com/milenapauli/Projeto-CloudTask-AI-SaaS.git

# Entrar no projeto
cd Projeto-CloudTask-AI-SaaS

# Subir a aplicação
docker compose up --build

# Acessar o Swagger
http://localhost:8000/docs
```

## 6. Decisões e trade-offs

Durante o desenvolvimento foram utilizadas algumas decisões para reduzir custos e facilitar os testes.

- Utilização do PostgreSQL em RDS para persistência dos dados.
- Utilização do Amazon S3 para armazenamento de arquivos enviados pela aplicação.
- Utilização do DynamoDB para registro de eventos.
- Uso do AWS Academy Learner Lab, que possui limitações de permissões, como impossibilidade de configurar MFA e acessar informações de Billing.
- Todos os recursos criados na AWS foram removidos ao final da atividade para evitar consumo desnecessário dos créditos do Learner.

## 7. Custos

- Recursos que cobraram: Amazon EKS, Amazon RDS, Amazon S3, Amazon DynamoDB, Amazon ECR e AWS CloudFormation/CDK.
- Estimativa do período: Aproximadamente US$ 5,70 (AWS Academy Learner Lab).
- Confirmação de limpeza: Após a conclusão do projeto foi realizada a remoção de todos os recursos criados, conforme registrado no deployment-checklist.md, evitando custos adicionais no AWS Academy Learner Lab. Print da limpeza em docs/screenshots/limpeza-recursos_cloud.png

## 8. LGPD e segurança

Foram adotadas boas práticas de segurança durante o desenvolvimento do projeto, incluindo utilização de IAM, armazenamento de configurações em variáveis de ambiente, ausência de credenciais no código-fonte, utilização de criptografia oferecida pelos serviços da AWS e armazenamento privado no Amazon S3. O uso de autenticação multifator (MFA) também faz parte das boas práticas de segurança da AWS. Porém, essa configuração não pôde ser realizada por conta das limitações do AWS Academy Learner Lab.
O projeto também contempla aspectos introdutórios da LGPD, documentados no checklist de segurança entregue junto com o relatório.

## 9. Dificuldades e aprendizados
A principal dificuldade encontrada foi compreender o funcionamento dos serviços da AWS e as limitações do AWS Academy Learner Lab, especialmente em relação ao MFA e às permissões de acesso.
O mais importante que aprendi foi criar e remover corretamente recursos na nuvem, entendendo a importância de evitar cobranças desnecessárias. Durante o desenvolvimento compreendi melhor conceitos como Docker, Kubernetes, Amazon EKS, Amazon RDS, Amazon S3, DynamoDB e utilização do AWS CDK.

## 10. Anexos

- [X] `lgpd-checklist.md` preenchido
- [X] `deployment-checklist.md` (sweep de limpeza) preenchido
- [X] Prints / logs das evidências da seção 3
