import logging
import asyncio
from email.message import EmailMessage
import smtplib
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    async def enviar_correo(destinatarios_str: str, asunto: str, cuerpo_html: str,
                            is_intern: bool = False, es_reenvio: bool = False,
                            correos_cc: list = None) -> tuple:
        if not destinatarios_str:
            return False, "No se especificaron destinatarios."

        def _send():
            lista_destinatarios = [e.strip() for e in destinatarios_str.split(",") if e.strip()]
            msg = EmailMessage()
            msg['Subject'] = asunto
            msg['From'] = settings.smtp_user

            if es_reenvio:
                msg['To'] = settings.smtp_user
            elif is_intern:
                msg['To'] = ", ".join(lista_destinatarios)
            else:
                msg['To'] = settings.smtp_user

            if not es_reenvio and not is_intern and correos_cc:
                msg['Bcc'] = ", ".join(correos_cc)

            msg.set_content(cuerpo_html, subtype='html')

            server = smtplib.SMTP(settings.smtp_server, settings.smtp_port)
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)

            destinatarios_totales = lista_destinatarios[:]
            if not is_intern and not es_reenvio and correos_cc:
                destinatarios_totales = list(set(destinatarios_totales + correos_cc))
            if not destinatarios_totales:
                destinatarios_totales = [settings.smtp_user]

            server.send_message(msg, from_addr=settings.smtp_user, to_addrs=destinatarios_totales)
            server.quit()
            return True, f"Correo enviado a {len(destinatarios_totales)} destinatario(s)."

        try:
            return await asyncio.to_thread(_send)
        except Exception as e:
            logger.error(f"Error enviando correo: {e}")
            return False, str(e)
