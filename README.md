# Meu Dinheiro em Dia

Aplicacao web em Django para controle de financas pessoais com foco em simplicidade, responsividade e analise mensal.

## Funcionalidades

- Cadastro, login e logout de usuarios
- CRUD de categorias (receita/despesa) por usuario
- CRUD de lancamentos com validacoes de negocio
- Filtros por mes, ano, categoria e texto de busca
- Dashboard com cards e graficos (Chart.js)
- Resumo mensal com totais por categoria e percentual de despesas
- Exportacao de lancamentos filtrados em CSV
- Paginacao nas listagens
- Campo inicial de lancamento recorrente (`is_recurring`)

## Stack

- Python 3.12+
- Django 6
- SQLite
- Django Templates + Bootstrap 5
- Chart.js

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
3. Lance movimentacoes financeiras.
4. Acompanhe o dashboard e o resumo mensal.
5. Exporte CSV quando precisar.

## Estrutura principal

- `core/`: configuracao do projeto e rotas globais
- `accounts/`: autenticacao e telas de acesso
- `finances/`: modelos, regras, CRUD, dashboard e resumo
- `templates/`: templates globais e por app
- `static/`: CSS customizado

## Testes

```powershell
python manage.py test
```
