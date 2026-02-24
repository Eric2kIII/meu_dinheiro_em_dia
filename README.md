# Meu Dinheiro em Dia

Aplicacao web em Django para controle de financas pessoais com foco em simplicidade, responsividade e analise mensal.

## Funcionalidades

- Cadastro, login e logout de usuarios
- CRUD de categorias (receita/despesa) por usuario
- Importacao em massa de categorias via CSV/XLSX
- CRUD de lancamentos com validacoes de negocio
- Importacao em massa de lancamentos via CSV/XLSX
- Filtros por mes, ano, categoria e texto de busca
- Exportacao de lancamentos filtrados em CSV
- Dashboard com cards, graficos (Chart.js) e resumo de gastos por cartao
- Resumo mensal com totais por categoria (incluindo cartao) e percentual de despesas
- Gestao de cartao de credito:
  - cadastro de cartao
  - registro de despesas no cartao
  - registro de pagamentos do cartao
  - total por cartao no dashboard e no resumo mensal
- Paginacao nas listagens
- Campo inicial de lancamento recorrente (`is_recurring`)

## Stack

- Python 3.12+
- Django 6
- SQLite
- Django Templates + Bootstrap 5
- Chart.js
- openpyxl (leitura de arquivos XLSX)

## Como executar localmente

1. Criar e ativar ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Aplicar migrations:

```powershell
python manage.py makemigrations
python manage.py migrate
```

4. Criar usuario administrador (opcional):

```powershell
python manage.py createsuperuser
```

5. Rodar servidor:

```powershell
python manage.py runserver
```

6. Acessar no navegador:

- Aplicacao: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

## Uso rapido

1. Crie uma conta em `accounts/signup/`.
2. Cadastre categorias de receita e despesa.
3. Opcionalmente importe categorias em lote pela tela de categorias.
4. Cadastre lancamentos manuais ou importe em massa pela tela de lancamentos.
5. Gerencie cartoes de credito na aba `Cartoes`.
6. Acompanhe dashboard e resumo mensal.

## Formatos de importacao

### Categorias

- colunas: `name`, `type`
- `type`: `INCOME` ou `EXPENSE`

### Lancamentos

- colunas obrigatorias: `type`, `amount`, `date`, `category`
- colunas opcionais: `description`, `notes`, `is_recurring`
- `date`: `YYYY-MM-DD` ou `DD/MM/YYYY`

## Estrutura principal

- `core/`: configuracao do projeto e rotas globais
- `accounts/`: autenticacao e telas de acesso
- `finances/`: modelos, regras, CRUD, importacao em lote, cartoes, dashboard e resumo
- `templates/`: templates globais e por app
- `static/`: CSS customizado

## Testes

```powershell
python manage.py test
```
