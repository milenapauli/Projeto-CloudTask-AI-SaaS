# Prática 99 — Troubleshooting

> **Catálogo de erros conhecidos** + diagnóstico + fix. Não é uma prática
> sequencial — consulte quando bater algum erro.
>
> Está organizado por **sintoma**.

---

## Índice rápido

- [Docker / Compose](#docker--compose)
- [Devcontainer](#devcontainer)
- [Banco PostgreSQL](#banco-postgresql)
- [API / Swagger](#api--swagger)
- [Testes (pytest)](#testes-pytest)
- [Uploads (S3 ou local)](#uploads-s3-ou-local)
- [AWS / credenciais](#aws--credenciais)
- [Git / branches](#git--branches)
- [Windows / WSL específico](#windows--wsl-específico)

---

## Docker / Compose

### `Cannot connect to the Docker daemon`

**Causa:** Docker Desktop não está rodando.
**Fix:** abra Docker Desktop, espere o ícone ficar verde, tente de novo.

### `port is already allocated` (8000 ou 5432)

**Causa:** outro serviço usa a porta.
**Fix opções:**

```bash
# 1. Descobrir quem está usando:
# Windows:
netstat -ano | findstr :5432
# Linux/Mac:
lsof -i :5432

# 2. Parar o conflitante OU mudar a porta do projeto no .env:
echo "POSTGRES_PORT=5433" >> .env
docker compose down && docker compose up -d
```

### `docker compose ps` vazio dentro do devcontainer

**Causa:** dentro do container, `pwd` é `/app`, project name vira `app`.
**Fix:**

```bash
docker compose -p cloudtaskaisaas ps
# ou:
docker ps --filter "label=com.docker.compose.project=cloudtaskaisaas"
```

---

## Devcontainer

### Build falha com `moby-cli not found`

**Causa:** feature `docker-outside-of-docker` tentou instalar moby-cli em
Debian trixie (não tem).
**Fix:** já corrigido — `"moby": false` no `devcontainer.json`. Se reapareceu,
confirme o JSON.

### Build falha em `nvm` / `source: not found`

**Causa:** feature de Node usa `source` (não existe em dash).
**Fix:** já corrigido — Node vem via `apt install nodejs npm` no Dockerfile
dev. Confirme o `Dockerfile`.

### `chown: invalid group: 'appuser:appuser'`

**Causa:** grupo se chamava `appgroup`.
**Fix:** já corrigido — `Dockerfile` cria `appuser:appuser`.

### Mount com path estranho (`HOME` + `USERPROFILE` concatenados)

**Causa:** `${localEnv:HOME}${localEnv:USERPROFILE}` se as duas variáveis
existem.
**Fix:** use **apenas uma** (`USERPROFILE` no Windows, `HOME` no
mac/Linux). Já corrigido em `devcontainer.json`.

### Prompt aparece sem cores / sem timestamp

**Causa:** `.zshrc` não foi copiado pra `~/`.
**Fix:**

```bash
cp /app/.devcontainer/.zshrc ~/.zshrc
exec zsh
```

### Sticky scroll não funciona

**Causa:** `terminal.integrated.shellIntegration.enabled` está `false`.
**Fix:** confira `devcontainer.json → customizations.vscode.settings`:

```json
"terminal.integrated.shellIntegration.enabled": true,
"terminal.integrated.stickyScroll.enabled": true,
"terminal.integrated.shellIntegration.decorationsEnabled": "both"
```

E o `.zshrc` precisa ter os marcadores OSC 633.

---

## Banco PostgreSQL

### `could not connect to server: Connection refused`

**Causa:** container `db` ainda subindo, ou parado.
**Fix:**

```bash
docker compose ps db                 # State deve ser "Up (healthy)"
docker compose up -d db              # se estiver parado
docker compose logs -f db            # ver logs
```

### `FATAL: password authentication failed`

**Causa:** `.env` divergente do esperado pelo container.
**Fix:** confira `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` no `.env`
batem com `DATABASE_URL`.

### `relation "tasks" does not exist`

**Causa:** banco vazio e API não subiu antes (não rodou `create_all`).
**Fix:** suba a API uma vez:

```bash
docker compose up -d api
curl http://localhost:8000/health    # força o startup
```

### Teste de pytest "vê" dados do dev (não isolado)

**Causa:** fixture sem TRUNCATE ou sem rollback.
**Fix:** já tratado em `tests/conftest.py` (TRUNCATE + savepoint + rollback no
finally). Se acontecer, reveja se `db_session` está usando essa fixture.

---

## API / Swagger

### `ModuleNotFoundError: No module named 'boto3'` (ou outro)

**Causa:** trocou de branch e não fez rebuild — imagem antiga não tem a lib
nova.
**Fix:**

```bash
# Sair do devcontainer (Reopen Folder Locally)
# F1 → Dev Containers: Rebuild Container
```

### Swagger não abre — só "Invalid HTTP request"

**Causa:** acessou `https://localhost:8000` em vez de `http://`. Dev é
**HTTP**, não HTTPS.
**Fix:** use `http://localhost:8000/docs`.

### `307 Temporary Redirect` infinito

**Causa:** `force_https=True` + `behind_proxy=False` no `.env` rodando local
sem proxy.
**Fix:** desligue `FORCE_HTTPS=false` em dev.

### Endpoint nunca aparece no Swagger

**Causa:** router não foi registrado.
**Fix:** confira `app/main.py` → `app.include_router(routes_XXX.router)`.

---

## Testes (pytest)

### Mudei o código/teste mas o resultado do container isolado não muda

**Causa:** você rodou o container isolado **sem `--build`**:
```bash
docker compose -p cloudtask-test -f docker-compose.yml -f docker-compose.test.yml run --rm api
```
O target `test` faz `COPY` do código para **dentro** da imagem (sem bind mount).
Sem `--build`, o Compose reaproveita a imagem em cache com o código **antigo** →
você testa uma versão **fóssil** (a correção "não faz efeito"; um teste que você
quebrou continua passando).

**Fix:** sempre acrescente `--build` nesse caminho:
```bash
docker compose -p cloudtask-test -f docker-compose.yml -f docker-compose.test.yml run --build --rm api
```
> O caminho rápido (`pytest`/`tv` **dentro** do devcontainer) NÃO sofre disso —
> ele usa o código por **volume** (target `dev`), enxergando suas edições na hora.

### `41 passed`, mas dados do dev sumiram

**Causa:** TRUNCATE rodou FORA de transação (`begin` faltando).
**Fix:** já tratado. Confira `tests/conftest.py` se replicou em outra branch.

### Warnings de Starlette (deprecation)

**Causa:** lib futura.
**Fix:** já tratado por `addopts = "-ra -q -p no:warnings"` em
`pyproject.toml`. Se persistir, **rebuild** o devcontainer (imagem cacheada).

### Pytest não acha `tests/`

**Causa:** rodando de pasta errada.
**Fix:** rode na raiz do projeto. Ou:

```bash
pytest --rootdir=/app /app/tests/
```

---

## Uploads (S3 ou local)

### `413 Request Entity Too Large` com arquivo pequeno

**Causa:** proxy intermediário.
**Fix:** em dev local não tem proxy. Confira `ls -la arquivo` — tamanho real.

### `storage_mode` ainda diz `"local"` após mudar `.env`

**Causa:** `restart` não recarrega `.env`; só `create`.
**Fix:**

```bash
docker compose down && docker compose up -d
```

### `404 Arquivo não encontrado` ao baixar do S3

**Causa:** prefixo gerado é único, você usou nome errado.
**Fix:** use o `filename` da resposta do POST. Liste no bucket:

```bash
aws s3 ls s3://$BUCKET/
```

---

## AWS / credenciais

### `Unable to locate credentials`

**Causa:** `~/.aws/credentials` vazio ou não montado.
**Fix:**

1. Cole credenciais do Learner Lab em `~/.aws/credentials` no **host**.
2. Confirme mount no `devcontainer.json`:
   ```json
   "source=${localEnv:USERPROFILE}/.aws,target=/home/appuser/.aws,..."
   ```
3. Dentro do container: `cat ~/.aws/credentials` deve mostrar conteúdo.

### `The security token included in the request is expired`

**Causa:** sessão do Learner Lab passou de 4h.
**Fix:** abra Learner Lab novo, cole credenciais frescas em `~/.aws/credentials`.

### `Could not connect to the endpoint URL`

**Causa:** `AWS_REGION` errada ou rede do container sem internet.
**Fix:**

```bash
docker compose exec api ping -c 2 s3.amazonaws.com
# se falhar: docker network ls, docker compose down && up
```

---

## Git / branches

### 70 arquivos aparecem como modificados após mudar de branch

**Causa:** CRLF (Windows) ↔ LF (Linux container) + `fileMode` ativo.
**Fix:**

```bash
# Já tratado: .gitattributes + git config core.fileMode false + autocrlf
# Se persistir:
git rm --cached -rf .
git reset --hard
```

### Branch trocada mas Swagger quebrado (`ModuleNotFoundError`)

**Causa:** imagem do devcontainer congelada na branch antiga.
**Fix:** **Rebuild Container** sempre que trocar de semana.

---

## Windows / WSL específico

### `mount: permission denied` ao iniciar devcontainer

**Causa:** pasta `~/.aws` ou `~/.kube` do host não existe.
**Fix:** crie no host:

```powershell
mkdir $env:USERPROFILE\.aws -Force
mkdir $env:USERPROFILE\.kube -Force
```

### Editor mostra `^M` no final das linhas

**Causa:** arquivos checados com CRLF.
**Fix:** `.gitattributes` já força LF. Re-clone ou:

```bash
git rm --cached -rf .
git reset --hard
```

### Docker Desktop não inicia (WSL2)

**Causa:** WSL2 desativado ou kernel antigo.
**Fix:**

```powershell
wsl --update
wsl --set-default-version 2
```

---

## Quando nada funciona

1. **Salve seu trabalho** (`git add . && git commit -m "WIP"`).
2. **Rebuild completo:**
   ```bash
   docker compose down -v
   docker system prune -af --volumes
   ```
   ⚠️ Apaga **tudo** do Docker (imagens, volumes, redes). Recria do zero.
3. **Reabrir devcontainer** → `F1 → Rebuild Container`.

Se ainda não funcionou, abra issue no GitHub com:

- Aula / branch.
- Comando exato que rodou.
- Saída completa do erro.
- SO (Windows 11? macOS? Linux?).
- Versões: `docker --version`, `git --version`, `code --version`.
