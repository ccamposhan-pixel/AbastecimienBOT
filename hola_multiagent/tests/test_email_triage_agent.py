from __future__ import annotations

import pandas as pd
import sys

from hola_multiagent.agents.chief_agent import ChiefAgent
from hola_multiagent.agents.email_triage_agent import EmailTriageAgent
from hola_multiagent.data.email_loader import EmailLoader, MicrosoftGraphConfig
from hola_multiagent.reports.email_html_report import render_email_triage_html


def test_email_loader_normalizes_mock_csv():
    loader = EmailLoader(source="csv", csv_path="data/mock/emails.csv")
    emails = loader.load()

    assert not emails.empty
    assert "subject" in emails.columns
    assert emails["has_attachments"].dtype == bool
    assert emails.iloc[0]["date"] >= emails.iloc[-1]["date"]


def test_email_agent_extracts_tasks_priorities_deadlines_and_replies():
    emails = pd.DataFrame(
        [
            {
                "message_id": "1",
                "date": "2026-04-27 09:00:00",
                "from_name": "Carolina Silva",
                "from_email": "carolina@example.com",
                "to": "usuario@example.com",
                "cc": "",
                "subject": "Aprobacion urgente OC",
                "body": (
                    "Necesito aprobacion de la OC antes de manana. "
                    "Hay riesgo de quiebre de stock."
                ),
                "snippet": "",
                "is_read": False,
                "has_attachments": True,
                "labels": "pendiente",
                "source": "test",
            },
            {
                "message_id": "2",
                "date": "2026-04-27 08:00:00",
                "from_name": "Newsletter",
                "from_email": "news@example.com",
                "to": "usuario@example.com",
                "cc": "",
                "subject": "Boletin",
                "body": "Noticias generales.",
                "snippet": "",
                "is_read": True,
                "has_attachments": False,
                "labels": "",
                "source": "test",
            },
        ]
    )
    emails = EmailLoader().normalize_dataframe(emails, source="test")
    agent = EmailTriageAgent()

    response = agent.run(
        query="revisar correos pendientes",
        context={"analysis_date": "2026-04-27"},
        dataframes={"emails": emails},
    )

    tasks = response.tables[1]
    assert len(tasks) == 1
    assert tasks.iloc[0]["priority"] == "ALTA"
    assert tasks.iloc[0]["deadline"] == "2026-04-28"
    assert "aprobacion" in tasks.iloc[0]["category"]
    assert "Respuestas sugeridas" in response.output


def test_chief_routes_email_queries_to_email_triage():
    chief = ChiefAgent(agents={})
    route = chief._route_with_keywords("leer correos pendientes y sugerir respuestas")

    assert route["agents"] == ["email_triage"]


def test_email_loader_maps_microsoft_graph_messages(monkeypatch):
    loader = EmailLoader(source="graph", limit=5, unread_only=True)
    config = MicrosoftGraphConfig(client_id="client-id", tenant_id="consumers", folder="inbox")

    monkeypatch.setattr(loader, "_graph_access_token", lambda _: "token")

    captured = {}

    def fake_graph_get(url, token, headers=None):
        captured["url"] = url
        captured["token"] = token
        captured["headers"] = headers
        return {
            "value": [
                {
                    "id": "graph-1",
                    "conversationId": "thread-1",
                    "receivedDateTime": "2026-04-27T12:00:00Z",
                    "from": {
                        "emailAddress": {
                            "name": "Carolina Silva",
                            "address": "carolina@example.com",
                        }
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": "usuario@example.com"}},
                    ],
                    "ccRecipients": [],
                    "subject": "Aprobacion urgente",
                    "bodyPreview": "Necesito aprobacion",
                    "body": {"contentType": "text", "content": "Necesito aprobacion manana."},
                    "isRead": False,
                    "hasAttachments": True,
                    "categories": ["pendiente"],
                }
            ]
        }

    monkeypatch.setattr(loader, "_graph_get", fake_graph_get)

    emails = loader.load_graph(config)

    assert len(emails) == 1
    assert emails.iloc[0]["message_id"] == "graph-1"
    assert emails.iloc[0]["from_email"] == "carolina@example.com"
    assert emails.iloc[0]["has_attachments"] == True
    assert "isRead+eq+false" in captured["url"]
    assert captured["token"] == "token"


def test_graph_auth_invalid_tenant_has_actionable_error(monkeypatch):
    loader = EmailLoader(source="graph")
    config = MicrosoftGraphConfig(client_id="client-id", tenant_id="bad-tenant")

    class FakeCache:
        has_state_changed = False

        def deserialize(self, text):
            return None

    class FakeMsal:
        SerializableTokenCache = FakeCache

        class PublicClientApplication:
            def __init__(self, **kwargs):
                raise ValueError("invalid_tenant")

    monkeypatch.setitem(sys.modules, "msal", FakeMsal)

    try:
        loader._graph_access_token(config)
    except RuntimeError as exc:
        assert "MSGRAPH_TENANT_ID" in str(exc)
        assert "consumers" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_graph_scopes_filters_msal_reserved_values():
    loader = EmailLoader(source="graph")

    scopes = loader._graph_scopes(("Mail.Read", "User.Read", "offline_access", "openid"))

    assert scopes == ["Mail.Read", "User.Read"]


def test_graph_auth_error_detail_includes_microsoft_payload():
    loader = EmailLoader(source="graph")

    detail = loader._graph_auth_error_detail(
        {
            "error": "unauthorized_client",
            "error_description": "Public client flows are disabled.",
        }
    )

    assert "unauthorized_client" in detail
    assert "Public client flows are disabled" in detail
    assert "Allow public client flows" in detail


def test_email_html_report_renders_visual_sections():
    emails = EmailLoader(source="csv", csv_path="data/mock/emails.csv").load()
    response = EmailTriageAgent().run(
        query="revisar correos pendientes",
        context={"analysis_date": "2026-04-27"},
        dataframes={"emails": emails},
    )

    html = render_email_triage_html(response)

    assert "<!doctype html>" in html
    assert "Tareas Priorizadas" in html
    assert "priority-alta" in html
    assert "Aprobacion urgente OC proveedor" in html
