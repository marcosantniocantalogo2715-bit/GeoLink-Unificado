# GeoLink Unificado

Projeto unificado do GeoCheckIn com login Google e API de geolocalização/check-in.

## Estrutura

- `app.py` — único arquivo principal do projeto.
- `web/index.html` — tela de eventos, localização, geofence e check-in.
- `data/geocheckin.db` — banco SQLite.
- `.env` — credenciais/configuração do Google OAuth.
- `requirements.txt` — dependências.

## Executar

1. Abra a pasta no VS Code.
2. Abra o terminal.
3. Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

4. Execute:

```powershell
python app.py
```

5. Acesse:

```text
http://127.0.0.1:5000
```

## Google OAuth

O login usa as variáveis `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` e `FLASK_SECRET_KEY` do `.env`.

O endereço de retorno usado pelo projeto é gerado automaticamente pelo Flask. Para execução local na porta 5000, o Google OAuth precisa permitir:

```text
http://127.0.0.1:5000/authorize
```

## Próximas etapas

1. Validar e restringir e-mail ao domínio institucional.
2. Implementar/verificar proteção contra VPN/proxy.
3. Testar o fluxo completo de login → localização → geofence → check-in.
