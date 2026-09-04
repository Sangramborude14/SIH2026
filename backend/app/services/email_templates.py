import html
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.core.config import settings


class EmailTemplateRenderer:
    """
    Operational Email Template Renderer.
    Produces clean, professional, high-contrast HTML and plain text email payloads.
    Guarantees strict HTML entity escaping for user-supplied strings and zero marketing fluff.
    """

    @staticmethod
    def render_expert_alert(
        location_name: str,
        district: str,
        state: str,
        risk_score: float,
        risk_level: str,
        confidence: float,
        trajectory: str,
        primary_drivers: List[Dict[str, Any]],
        data_quality_score: float = 1.0,
        event_id: Optional[str] = None,
        app_base_url: Optional[str] = None,
    ) -> Dict[str, str]:
        base_url = (app_base_url or settings.APP_BASE_URL).rstrip("/")
        event_link = f"{base_url}/analytics" if not event_id else f"{base_url}/analytics?event_id={event_id}"
        
        safe_loc = html.escape(location_name)
        safe_dist = html.escape(district)
        safe_state = html.escape(state)
        safe_level = html.escape(risk_level)
        safe_traj = html.escape(trajectory)

        drivers_html = "".join([
            f"<li><strong>{html.escape(str(d.get('name', 'Hazard Factor')).replace('_', ' ').title())}:</strong> "
            f"Raw {html.escape(str(d.get('raw_value', 'N/A')))} (Contrib: {float(d.get('contribution', 0.0)):.1f} pts)</li>"
            for d in primary_drivers[:4]
        ]) or "<li>Baseline environmental parameters within threshold.</li>"

        drivers_text = "\n".join([
            f"- {str(d.get('name', '')).replace('_', ' ').title()}: Raw {d.get('raw_value')} (Contrib: {float(d.get('contribution', 0.0)):.1f} pts)"
            for d in primary_drivers[:4]
        ]) or "- Baseline parameters within nominal bounds."

        subject = f"[{safe_level}] Landslide Risk Assessment — {safe_loc}"

        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.5; color: #111827; background-color: #f9fafb; margin: 0; padding: 24px;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; padding: 24px;">
    <div style="border-bottom: 2px solid #111827; padding-bottom: 12px; margin-bottom: 16px;">
      <h2 style="margin: 0; font-size: 18px; color: #111827; text-transform: uppercase;">NDMA / SDMA Landslide Early Warning Bulletin</h2>
      <p style="margin: 4px 0 0 0; font-size: 12px; color: #6b7280;">Issued by DISASTRA Disaster Intelligence Engine ({settings.DATA_MODE} Mode)</p>
    </div>

    <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
      <tr>
        <td style="padding: 6px 0; color: #4b5563; font-size: 14px;"><strong>Location / Sector:</strong></td>
        <td style="padding: 6px 0; font-size: 14px;">{safe_loc}, {safe_dist} ({safe_state})</td>
      </tr>
      <tr>
        <td style="padding: 6px 0; color: #4b5563; font-size: 14px;"><strong>Assessed Risk Level:</strong></td>
        <td style="padding: 6px 0; font-size: 14px;"><strong style="color: #b91c1c;">{safe_level} ({risk_score:.1f}/100)</strong></td>
      </tr>
      <tr>
        <td style="padding: 6px 0; color: #4b5563; font-size: 14px;"><strong>Confidence Score:</strong></td>
        <td style="padding: 6px 0; font-size: 14px;">{confidence * 100.0:.0f}% (Completeness: {data_quality_score * 100.0:.0f}%)</td>
      </tr>
      <tr>
        <td style="padding: 6px 0; color: #4b5563; font-size: 14px;"><strong>Trajectory:</strong></td>
        <td style="padding: 6px 0; font-size: 14px;">{safe_traj}</td>
      </tr>
    </table>

    <h3 style="font-size: 14px; margin: 16px 0 8px 0; color: #111827; text-transform: uppercase;">Primary Risk Drivers:</h3>
    <ul style="margin: 0 0 16px 0; padding-left: 20px; font-size: 13px; color: #374151;">
      {drivers_html}
    </ul>

    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
      <a href="{event_link}" style="display: inline-block; background-color: #111827; color: #ffffff; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 13px; font-weight: bold;">
        View Assessment in Expert Command Portal &rarr;
      </a>
    </div>

    <p style="margin-top: 24px; font-size: 11px; color: #9ca3af;">
      Confidential operational transmission intended solely for authorized disaster response personnel.
    </p>
  </div>
</body>
</html>"""

        text_body = f"""NDMA / SDMA LANDSLIDE EARLY WARNING BULLETIN
Location: {location_name}, {district} ({state})
Risk Level: {risk_level} ({risk_score:.1f}/100)
Confidence: {confidence * 100.0:.0f}%
Trajectory: {trajectory}

PRIMARY RISK DRIVERS:
{drivers_text}

View in Command Portal: {event_link}
Issued by DISASTRA Disaster Intelligence Engine ({settings.DATA_MODE} Mode)
"""
        return {"subject": subject, "html": html_body, "text": text_body}

    @staticmethod
    def render_broadcast(
        title: str,
        message: str,
        priority: str = "URGENT",
        sender_id: Optional[str] = None,
        event_id: Optional[str] = None,
        app_base_url: Optional[str] = None,
    ) -> Dict[str, str]:
        base_url = (app_base_url or settings.APP_BASE_URL).rstrip("/")
        safe_title = html.escape(title)
        safe_msg = html.escape(message)
        safe_priority = html.escape(priority)
        safe_sender = html.escape(sender_id or "Central Command Duty Officer")

        subject = f"[{safe_priority}] Emergency Command Directive — {safe_title}"

        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: Arial, sans-serif; line-height: 1.5; color: #111827; background-color: #f9fafb; margin: 0; padding: 24px;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; padding: 24px;">
    <div style="border-bottom: 2px solid #b91c1c; padding-bottom: 12px; margin-bottom: 16px;">
      <h2 style="margin: 0; font-size: 18px; color: #b91c1c; text-transform: uppercase;">[{safe_priority}] Emergency Broadcast Directive</h2>
      <p style="margin: 4px 0 0 0; font-size: 12px; color: #6b7280;">Originator: {safe_sender} | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
    </div>

    <h3 style="font-size: 16px; margin: 0 0 12px 0; color: #111827;">{safe_title}</h3>
    <div style="background-color: #f3f4f6; border-left: 4px solid #111827; padding: 12px 16px; font-size: 14px; color: #1f2937; margin-bottom: 20px;">
      {safe_msg}
    </div>

    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
      <a href="{base_url}/field/messages" style="display: inline-block; background-color: #111827; color: #ffffff; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 13px; font-weight: bold;">
        Open Tactical Field Terminal &rarr;
      </a>
    </div>
  </div>
</body>
</html>"""

        text_body = f"""[{priority}] EMERGENCY BROADCAST DIRECTIVE
Originator: {sender_id or 'Central Command Duty Officer'}
Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

TITLE: {title}

DIRECTIVE:
{message}

Field Terminal: {base_url}/field/messages
"""
        return {"subject": subject, "html": html_body, "text": text_body}

    @staticmethod
    def render_public_safety(
        district: str,
        state: str,
        severity: str,
        guidance: str,
        app_base_url: Optional[str] = None,
    ) -> Dict[str, str]:
        base_url = (app_base_url or settings.APP_BASE_URL).rstrip("/")
        safe_dist = html.escape(district)
        safe_state = html.escape(state)
        safe_sev = html.escape(severity)
        safe_guide = html.escape(guidance)

        subject = f"URGENT Landslide Safety Warning — {safe_dist}"

        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: Arial, sans-serif; line-height: 1.5; color: #111827; background-color: #f9fafb; margin: 0; padding: 24px;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; padding: 24px;">
    <div style="border-bottom: 2px solid #b91c1c; padding-bottom: 12px; margin-bottom: 16px;">
      <h2 style="margin: 0; font-size: 18px; color: #b91c1c;">DISASTER EARLY WARNING: {safe_dist.upper()}</h2>
      <p style="margin: 4px 0 0 0; font-size: 12px; color: #6b7280;">State Disaster Management Authority ({safe_state})</p>
    </div>

    <p style="font-size: 14px; margin-bottom: 12px;"><strong>Severity:</strong> {safe_sev} Landslide Hazard Potential</p>
    <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 4px; padding: 12px 16px; font-size: 14px; color: #991b1b; margin-bottom: 16px;">
      {safe_guide}
    </div>

    <p style="font-size: 13px; color: #4b5563; margin-bottom: 16px;">
      Emergency Contacts: <strong>1070</strong> (Disaster Helpline) | <strong>112</strong> (Police/Emergency Services)
    </p>

    <div>
      <a href="{base_url}/public" style="display: inline-block; background-color: #b91c1c; color: #ffffff; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 13px; font-weight: bold;">
        View Nearest Safe Shelters & Guidance &rarr;
      </a>
    </div>
  </div>
</body>
</html>"""

        text_body = f"""DISASTER EARLY WARNING: {district.upper()}
Severity: {severity} Landslide Hazard Potential

SAFETY GUIDANCE:
{guidance}

Emergency Contacts: 1070 (Disaster Helpline) | 112 (Emergency)
View Shelters: {base_url}/public
"""
        return {"subject": subject, "html": html_body, "text": text_body}

    @staticmethod
    def render_system_alert(
        component_name: str,
        status: str,
        details: str,
        app_base_url: Optional[str] = None,
    ) -> Dict[str, str]:
        base_url = (app_base_url or settings.APP_BASE_URL).rstrip("/")
        safe_comp = html.escape(component_name)
        safe_status = html.escape(status)
        safe_det = html.escape(details)

        subject = f"[SYSTEM ADVISORY] {safe_comp} Telemetry Status: {safe_status}"

        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: Arial, sans-serif; line-height: 1.5; color: #111827; background-color: #f9fafb; margin: 0; padding: 24px;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; padding: 24px;">
    <h3 style="margin: 0 0 12px 0; color: #111827;">System Component Diagnostic Notice</h3>
    <p style="font-size: 14px; margin: 4px 0;"><strong>Component:</strong> {safe_comp}</p>
    <p style="font-size: 14px; margin: 4px 0;"><strong>Status:</strong> {safe_status}</p>
    <div style="background-color: #f3f4f6; padding: 12px; font-family: monospace; font-size: 12px; margin: 12px 0;">
      {safe_det}
    </div>
    <a href="{base_url}/dashboard" style="font-size: 13px; color: #2563eb;">Open Command Center &rarr;</a>
  </div>
</body>
</html>"""

        text_body = f"""SYSTEM COMPONENT DIAGNOSTIC NOTICE
Component: {component_name}
Status: {status}
Details: {details}

Command Center: {base_url}/dashboard
"""
        return {"subject": subject, "html": html_body, "text": text_body}


email_template_renderer = EmailTemplateRenderer()
