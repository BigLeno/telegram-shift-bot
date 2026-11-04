"""Leitura da planilha de escala no Google Sheets."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


class SheetsError(Exception):
    """Falha ao acessar a planilha."""


class ScheduleSheet:
    def __init__(self, spreadsheet_id: str, client_secret: Path, token: Path) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.client_secret = client_secret
        self.token = token
        self._service = None

    def values(self, cell_range: str) -> list[list[str]]:
        try:
            response = (
                self._get_service()
                .spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=cell_range)
                .execute()
            )
        except Exception as error:  # a API do Google lança vários tipos de erro
            logger.exception("Erro ao ler o intervalo %s da planilha", cell_range)
            raise SheetsError("Não foi possível acessar a planilha. Tente novamente mais tarde.") from error
        return response.get("values", [])

    def _get_service(self):
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build("sheets", "v4", credentials=self._credentials(), cache_discovery=False)
        return self._service

    def _credentials(self):
        # Importações locais: o restante do bot (e os testes) não depende das bibliotecas do Google.
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        credentials = None
        if self.token.exists():
            credentials = Credentials.from_authorized_user_file(str(self.token), SCOPES)

        if credentials and credentials.valid:
            return credentials

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            # Primeira execução: abre o navegador para autorizar o acesso à planilha.
            flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret), SCOPES)
            credentials = flow.run_local_server(port=0)

        self.token.parent.mkdir(parents=True, exist_ok=True)
        self.token.write_text(credentials.to_json(), encoding="utf-8")
        return credentials
