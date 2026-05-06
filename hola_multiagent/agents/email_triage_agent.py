from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
import unicodedata
from typing import Mapping

import pandas as pd

from .base_agent import AgentResponse, BaseAgent
from ..config.settings import Settings, settings as default_settings


ACTION_TERMS = (
    "aprobar",
    "aprobacion",
    "autorizar",
    "confirmar",
    "responder",
    "enviar",
    "revisar",
    "validar",
    "preparar",
    "coordinar",
    "agendar",
    "cotizar",
    "comprar",
    "pagar",
    "resolver",
    "actualizar",
    "firmar",
    "entregar",
    "compartir",
)

URGENT_TERMS = (
    "urgente",
    "critico",
    "critica",
    "alta prioridad",
    "asap",
    "hoy",
    "ahora",
    "vencido",
    "atrasado",
    "bloqueado",
    "bloqueante",
)

RISK_TERMS = (
    "legal",
    "multa",
    "auditoria",
    "contrato",
    "incumplimiento",
    "paciente",
    "quiebre",
    "stock",
    "factura vencida",
    "pago vencido",
    "reclamo",
    "escalamiento",
    "gerencia",
)

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "aprobacion": ("aprobar", "aprobacion", "autorizar", "firma", "firmar", "ok"),
    "reunion": ("reunion", "agenda", "agendar", "coordinar", "calendario", "meet", "teams"),
    "informacion": ("informacion", "datos", "documento", "antecedentes", "detalle", "reporte"),
    "riesgo": ("urgente", "critico", "bloqueado", "incumplimiento", "reclamo", "quiebre"),
    "pago_factura": ("factura", "pago", "cobranza", "oc", "orden de compra"),
    "abastecimiento": ("proveedor", "cotizacion", "stock", "material", "insumo", "compra"),
}

WEEKDAYS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}


@dataclass(frozen=True)
class EmailAssessment:
    email_id: str
    sender: str
    subject: str
    category: str
    priority: str
    deadline: date | None
    task: str
    critical_points: list[str]
    reply_suggestion: str
    score: int


class EmailTriageAgent(BaseAgent):
    name = "EmailTriageAgent"
    role_description = "Asistente de correo ejecutivo"
    system_prompt = (
        "Lee correos, identifica pendientes, resume criticidad, extrae tareas con "
        "prioridad y deadlines, y propone respuestas en espanol profesional."
    )

    def __init__(self, app_settings: Settings = default_settings) -> None:
        self.settings = app_settings

    def run(
        self,
        query: str,
        context: dict,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> AgentResponse:
        emails = self._get_dataframe(dataframes, "emails")
        if emails.empty:
            return self._empty_response(
                "No hay correos cargados. Usa interface.email_cli con --source csv o --source imap.",
                confidence=0.0,
                alerts=["Sin dataset emails"],
                assumptions=["El agente espera un DataFrame llamado emails."],
            )

        analysis_date = self._analysis_date(context, emails)
        pending = self.pending_emails(emails)
        assessments = [
            self.assess_email(row, analysis_date)
            for _, row in pending.head(int(context.get("limit", 25))).iterrows()
        ]
        assessments.sort(key=lambda item: (-item.score, item.deadline or date.max, item.subject))

        tasks_table = self._tasks_table(assessments)
        overview = self._overview_table(emails, pending, assessments)
        output = self._format_output(emails, pending, assessments, tasks_table, analysis_date)

        alerts = []
        high_count = sum(1 for item in assessments if item.priority == "ALTA")
        overdue_count = sum(
            1 for item in assessments if item.deadline is not None and item.deadline < analysis_date
        )
        if high_count:
            alerts.append(f"{high_count} correo(s) de prioridad ALTA")
        if overdue_count:
            alerts.append(f"{overdue_count} tarea(s) vencida(s)")

        return AgentResponse(
            agent_name=self.name,
            output=output,
            confidence=0.79,
            alerts=alerts,
            tables=[overview, tasks_table],
            sources=sorted(set(str(value) for value in emails["source"].dropna().unique())),
            assumptions=[
                "La lectura semantica usa reglas deterministicas de prioridad, fecha y accion.",
                "Los borradores son sugerencias; no se envia ningun correo automaticamente.",
            ],
        )

    def pending_emails(self, emails: pd.DataFrame) -> pd.DataFrame:
        if emails.empty:
            return emails

        pending = emails.copy()
        text = (
            pending["subject"].fillna("").astype(str)
            + " "
            + pending["body"].fillna("").astype(str)
            + " "
            + pending["labels"].fillna("").astype(str)
        ).map(self._normalize)

        labels = pending["labels"].fillna("").astype(str).map(self._normalize)
        unread = ~pending["is_read"].fillna(False).astype(bool)
        explicit_pending = labels.str.contains(r"\b(?:pendiente|follow_up|to_do|accion)\b", regex=True)
        action_needed = text.map(lambda value: any(term in value for term in ACTION_TERMS))
        question = pending["subject"].fillna("").astype(str).str.contains(r"\?", regex=True) | pending[
            "body"
        ].fillna("").astype(str).str.contains(r"\?", regex=True)

        result = pending[unread | explicit_pending | action_needed | question].copy()
        return result.sort_values("date", ascending=False, na_position="last").reset_index(drop=True)

    def assess_email(self, row: pd.Series, analysis_date: date) -> EmailAssessment:
        subject = self._clean(row.get("subject", "Sin asunto")) or "Sin asunto"
        body = self._clean(row.get("body", ""))
        normalized = self._normalize(f"{subject} {body}")
        deadline = self.extract_deadline(normalized, analysis_date)
        category = self.classify_category(normalized)
        task = self.extract_task(subject, body)
        score = self.priority_score(row, normalized, deadline, analysis_date)
        priority = self.priority_label(score)
        critical_points = self.critical_points(row, normalized, deadline, analysis_date)
        reply = self.suggest_reply(row, category, priority, deadline, task)

        sender = self._sender(row)
        email_id = str(row.get("message_id") or "").strip()
        if not email_id:
            email_id = f"{sender}|{subject}"[:80]

        return EmailAssessment(
            email_id=email_id,
            sender=sender,
            subject=subject,
            category=category,
            priority=priority,
            deadline=deadline,
            task=task,
            critical_points=critical_points,
            reply_suggestion=reply,
            score=score,
        )

    def extract_deadline(self, normalized_text: str, analysis_date: date) -> date | None:
        if "pasado manana" in normalized_text:
            return analysis_date + timedelta(days=2)
        if "manana" in normalized_text:
            return analysis_date + timedelta(days=1)
        if "hoy" in normalized_text:
            return analysis_date
        if "esta semana" in normalized_text:
            return self._next_weekday(analysis_date, 4)
        if "proxima semana" in normalized_text or "siguiente semana" in normalized_text:
            return analysis_date + timedelta(days=7)

        iso_match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", normalized_text)
        if iso_match:
            year, month, day = (int(part) for part in iso_match.groups())
            return self._safe_date(year, month, day)

        date_match = re.search(r"\b(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2,4}))?\b", normalized_text)
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            raw_year = date_match.group(3)
            year = analysis_date.year if raw_year is None else int(raw_year)
            if year < 100:
                year += 2000
            candidate = self._safe_date(year, month, day)
            if candidate and raw_year is None and candidate < analysis_date - timedelta(days=30):
                candidate = self._safe_date(year + 1, month, day)
            return candidate

        for name, weekday in WEEKDAYS.items():
            if re.search(rf"\b{name}\b", normalized_text):
                return self._next_weekday(analysis_date, weekday)
        return None

    def classify_category(self, normalized_text: str) -> str:
        scores = {
            category: sum(1 for keyword in keywords if self._contains_term(normalized_text, keyword))
            for category, keywords in CATEGORY_KEYWORDS.items()
        }
        specific_categories = [
            "aprobacion",
            "pago_factura",
            "reunion",
            "informacion",
            "abastecimiento",
        ]
        for category in specific_categories:
            if scores[category]:
                return category
        return "riesgo" if scores["riesgo"] else "general"

    def extract_task(self, subject: str, body: str) -> str:
        sentences = self._sentences(body)
        for sentence in sentences:
            normalized = self._normalize(sentence)
            if any(term in normalized for term in ACTION_TERMS):
                return self._shorten(sentence, 180)
        return self._shorten(f"Revisar y responder correo: {subject}", 180)

    def priority_score(
        self,
        row: pd.Series,
        normalized_text: str,
        deadline: date | None,
        analysis_date: date,
    ) -> int:
        score = 0
        if deadline:
            days = (deadline - analysis_date).days
            if days < 0:
                score += 4
            elif days <= 1:
                score += 3
            elif days <= 3:
                score += 2
            elif days <= 7:
                score += 1

        if any(term in normalized_text for term in URGENT_TERMS):
            score += 3
        if any(term in normalized_text for term in RISK_TERMS):
            score += 2
        if any(term in normalized_text for term in ACTION_TERMS):
            score += 2
        if bool(row.get("has_attachments", False)):
            score += 1
        if not bool(row.get("is_read", False)):
            score += 1
        return score

    def priority_label(self, score: int) -> str:
        if score >= 6:
            return "ALTA"
        if score >= 3:
            return "MEDIA"
        return "BAJA"

    def critical_points(
        self,
        row: pd.Series,
        normalized_text: str,
        deadline: date | None,
        analysis_date: date,
    ) -> list[str]:
        points: list[str] = []
        if deadline:
            days = (deadline - analysis_date).days
            if days < 0:
                points.append(f"Deadline vencido: {deadline.isoformat()}")
            elif days <= 1:
                points.append(f"Deadline inmediato: {deadline.isoformat()}")
            else:
                points.append(f"Deadline detectado: {deadline.isoformat()}")
        if any(term in normalized_text for term in URGENT_TERMS):
            points.append("Lenguaje de urgencia")
        risk_hits = [term for term in RISK_TERMS if term in normalized_text]
        if risk_hits:
            points.append("Riesgo: " + ", ".join(risk_hits[:3]))
        if bool(row.get("has_attachments", False)):
            points.append("Incluye adjuntos para revisar")
        if not bool(row.get("is_read", False)):
            points.append("Correo no leido")
        return points or ["Sin criticidad explicita; mantener seguimiento"]

    def suggest_reply(
        self,
        row: pd.Series,
        category: str,
        priority: str,
        deadline: date | None,
        task: str,
    ) -> str:
        greeting = self._greeting(row)
        deadline_text = f" antes del {deadline.isoformat()}" if deadline else ""
        urgency_text = "Lo tomo con prioridad alta. " if priority == "ALTA" else ""

        templates = {
            "aprobacion": (
                f"{greeting}, recibido. {urgency_text}Reviso los antecedentes y te confirmo "
                f"aprobacion u observaciones{deadline_text}. Si falta algun documento de respaldo, "
                "te lo pido por este mismo hilo."
            ),
            "reunion": (
                f"{greeting}, gracias. {urgency_text}Puedo coordinar agenda y confirmar disponibilidad"
                f"{deadline_text}. Si hay temas especificos a preparar, enviamelos para llegar con contexto."
            ),
            "informacion": (
                f"{greeting}, recibido. {urgency_text}Levanto la informacion solicitada y vuelvo con "
                f"respuesta{deadline_text}. Si necesitas un formato especifico, avisame."
            ),
            "riesgo": (
                f"{greeting}, recibido. {urgency_text}Voy a revisar el punto critico, validar impacto "
                f"y responder con acciones concretas{deadline_text}."
            ),
            "pago_factura": (
                f"{greeting}, recibido. {urgency_text}Reviso OC, factura y estado de pago, y te confirmo "
                f"si corresponde gestion interna o regularizacion{deadline_text}."
            ),
            "abastecimiento": (
                f"{greeting}, recibido. {urgency_text}Valido proveedor, stock/compra y antecedentes "
                f"operacionales para responder con recomendacion{deadline_text}."
            ),
        }
        return templates.get(
            category,
            f"{greeting}, recibido. {urgency_text}Lo reviso y vuelvo con respuesta{deadline_text}.",
        )

    def _format_output(
        self,
        emails: pd.DataFrame,
        pending: pd.DataFrame,
        assessments: list[EmailAssessment],
        tasks_table: pd.DataFrame,
        analysis_date: date,
    ) -> str:
        high = sum(1 for item in assessments if item.priority == "ALTA")
        with_deadline = sum(1 for item in assessments if item.deadline is not None)
        output_parts = [
            f"Se revisaron {len(emails)} correo(s); {len(pending)} quedan como pendientes accionables.",
            f"Fecha de analisis: {analysis_date.isoformat()}.",
            f"**Resumen:** {high} prioridad ALTA y {with_deadline} con deadline detectado.",
        ]

        if assessments:
            critical = []
            for item in assessments:
                if item.priority == "ALTA":
                    critical.append(f"{item.subject}: {'; '.join(item.critical_points[:3])}")
            if critical:
                output_parts.extend(["\n**Puntos criticos:**", "\n".join(f"- {item}" for item in critical[:8])])

        if not tasks_table.empty:
            output_parts.extend(
                [
                    "\n**Tareas priorizadas:**",
                    tasks_table[
                        ["priority", "deadline", "sender", "subject", "task"]
                    ].head(15).to_markdown(index=False),
                ]
            )

        if assessments:
            reply_lines = []
            for index, item in enumerate(assessments[:8], start=1):
                reply_lines.append(
                    f"{index}. **{item.subject}** ({item.priority})\n"
                    f"   {item.reply_suggestion}"
                )
            output_parts.extend(["\n**Respuestas sugeridas:**", "\n".join(reply_lines)])
        else:
            output_parts.append("No se detectaron correos que requieran accion inmediata.")

        return "\n\n".join(output_parts)

    def _tasks_table(self, assessments: list[EmailAssessment]) -> pd.DataFrame:
        rows = [
            {
                "email_id": item.email_id,
                "priority": item.priority,
                "deadline": item.deadline.isoformat() if item.deadline else "",
                "sender": item.sender,
                "subject": item.subject,
                "category": item.category,
                "task": item.task,
                "critical_points": "; ".join(item.critical_points),
                "reply_suggestion": item.reply_suggestion,
                "score": item.score,
            }
            for item in assessments
        ]
        return pd.DataFrame(
            rows,
            columns=[
                "email_id",
                "priority",
                "deadline",
                "sender",
                "subject",
                "category",
                "task",
                "critical_points",
                "reply_suggestion",
                "score",
            ],
        )

    def _overview_table(
        self,
        emails: pd.DataFrame,
        pending: pd.DataFrame,
        assessments: list[EmailAssessment],
    ) -> pd.DataFrame:
        by_priority = {
            priority: sum(1 for item in assessments if item.priority == priority)
            for priority in ("ALTA", "MEDIA", "BAJA")
        }
        return pd.DataFrame(
            [
                {
                    "metric": "correos_revisados",
                    "value": len(emails),
                },
                {
                    "metric": "correos_pendientes",
                    "value": len(pending),
                },
                {
                    "metric": "prioridad_alta",
                    "value": by_priority["ALTA"],
                },
                {
                    "metric": "prioridad_media",
                    "value": by_priority["MEDIA"],
                },
                {
                    "metric": "prioridad_baja",
                    "value": by_priority["BAJA"],
                },
            ]
        )

    def _analysis_date(self, context: dict, emails: pd.DataFrame) -> date:
        configured = context.get("analysis_date")
        if isinstance(configured, date):
            return configured
        if isinstance(configured, str) and configured.strip():
            return pd.to_datetime(configured, errors="coerce").date()
        if "date" in emails.columns and not emails["date"].dropna().empty:
            return pd.to_datetime(emails["date"].dropna().max()).date()
        return datetime.now().date()

    def _next_weekday(self, reference: date, weekday: int) -> date:
        days = (weekday - reference.weekday()) % 7
        return reference + timedelta(days=days)

    def _safe_date(self, year: int, month: int, day: int) -> date | None:
        try:
            return date(year, month, day)
        except ValueError:
            return None

    def _sentences(self, text: str) -> list[str]:
        return [
            self._clean(sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", text)
            if self._clean(sentence)
        ]

    def _sender(self, row: pd.Series) -> str:
        name = self._clean(row.get("from_name", ""))
        email = self._clean(row.get("from_email", ""))
        if name and email:
            return f"{name} <{email}>"
        return name or email or "Remitente no identificado"

    def _greeting(self, row: pd.Series) -> str:
        name = self._clean(row.get("from_name", ""))
        first = name.split()[0] if name else ""
        return f"Hola {first}" if first else "Hola"

    def _clean(self, value: object) -> str:
        if pd.isna(value):
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    def _shorten(self, value: str, limit: int) -> str:
        clean = self._clean(value)
        if len(clean) <= limit:
            return clean
        return clean[: limit - 3].rstrip() + "..."

    def _normalize(self, text: str) -> str:
        lowered = str(text).lower()
        lowered = lowered.replace("ñ", "n")
        lowered = unicodedata.normalize("NFKD", lowered)
        lowered = "".join(char for char in lowered if not unicodedata.combining(char))
        lowered = re.sub(r"[^\w\s/.-]", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()

    def _contains_term(self, text: str, term: str) -> bool:
        if " " in term:
            return term in text
        return re.search(rf"\b{re.escape(term)}\b", text) is not None
