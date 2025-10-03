"""
PDF generation utilities for reports and documents.
Provides advanced PDF generation with medical formatting and compliance features.
"""
import io
import base64
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, date
from pathlib import Path

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from app.utils.logging import get_logger

logger = get_logger(__name__)


class PDFGeneratorError(Exception):
    """PDF generation error."""
    pass


class PDFGenerator:
    """Advanced PDF generator with medical document features."""

    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise PDFGeneratorError("ReportLab is not installed. Install with: pip install reportlab")

        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom styles for medical documents."""
        # Header style
        self.styles.add(ParagraphStyle(
            name='CustomHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#2E7D32'),
            spaceAfter=20,
            alignment=TA_CENTER
        ))

        # Subheader style
        self.styles.add(ParagraphStyle(
            name='CustomSubHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1976D2'),
            spaceAfter=12,
            spaceBefore=16
        ))

        # Medical data style
        self.styles.add(ParagraphStyle(
            name='MedicalData',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica',
            leftIndent=20,
            spaceAfter=6
        ))

        # Warning style
        self.styles.add(ParagraphStyle(
            name='Warning',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.red,
            backColor=colors.HexColor('#FFEBEE'),
            borderColor=colors.red,
            borderWidth=1,
            borderPadding=8,
            spaceAfter=10
        ))

        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        ))

    def _get_patient_status(self, patient_data: Dict[str, Any]) -> str:
        """
        Get patient status from patient data.

        Args:
            patient_data: Patient information dictionary

        Returns:
            Human-readable status string
        """
        # Check for flow_state first (new format)
        flow_state = patient_data.get('flow_state')
        if flow_state:
            if flow_state == 'active':
                return 'Active'
            elif flow_state == 'onboarding':
                return 'Onboarding'
            elif flow_state == 'paused':
                return 'Paused'
            elif flow_state == 'completed':
                return 'Completed'
            elif flow_state == 'inactive':
                return 'Inactive'

        # Fallback to is_active for backward compatibility
        is_active = patient_data.get('is_active')
        if is_active is not None:
            return 'Active' if is_active else 'Inactive'

        # Default if no status information available
        return 'Unknown'

    def generate_patient_report(
        self,
        patient_data: Dict[str, Any],
        report_data: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> Union[bytes, str]:
        """
        Generate comprehensive patient report.

        Args:
            patient_data: Patient information
            report_data: Report content data
            output_path: Optional file path to save PDF

        Returns:
            PDF bytes if no output_path, file path if saved
        """
        try:
            # Create buffer or file
            if output_path:
                doc = SimpleDocTemplate(output_path, pagesize=A4)
            else:
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4)

            # Build story
            story = []

            # Header
            story.append(Paragraph("MEDICAL PATIENT REPORT", self.styles['CustomHeader']))
            story.append(Spacer(1, 20))

            # Patient Information Section
            story.append(Paragraph("Patient Information", self.styles['CustomSubHeader']))

            patient_info = [
                ['Name:', patient_data.get('name', 'N/A')],
                ['ID:', str(patient_data.get('id', 'N/A'))],
                ['Date of Birth:', patient_data.get('date_of_birth', 'N/A')],
                ['Treatment Type:', patient_data.get('treatment_type', 'N/A')],
                ['Current Day:', str(patient_data.get('current_day', 'N/A'))],
                ['Status:', self._get_patient_status(patient_data)],
            ]

            patient_table = Table(patient_info, colWidths=[2*inch, 3*inch])
            patient_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E3F2FD')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))

            story.append(patient_table)
            story.append(Spacer(1, 20))

            # Treatment Progress Section
            if 'treatment_progress' in report_data:
                story.append(Paragraph("Treatment Progress", self.styles['CustomSubHeader']))
                progress = report_data['treatment_progress']

                progress_data = [
                    ['Metric', 'Value', 'Status'],
                    ['Days Completed', str(progress.get('days_completed', 0)), ''],
                    ['Adherence Rate', f"{progress.get('adherence_rate', 0):.1%}", self._get_status_symbol(progress.get('adherence_rate', 0), 0.8)],
                    ['Response Rate', f"{progress.get('response_rate', 0):.1%}", self._get_status_symbol(progress.get('response_rate', 0), 0.7)],
                    ['Quiz Completion', f"{progress.get('quiz_completion', 0):.1%}", self._get_status_symbol(progress.get('quiz_completion', 0), 0.8)],
                ]

                progress_table = Table(progress_data, colWidths=[2*inch, 1.5*inch, 1*inch])
                progress_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
                ]))

                story.append(progress_table)
                story.append(Spacer(1, 20))

            # Symptoms and Alerts Section
            if 'alerts' in report_data:
                story.append(Paragraph("Recent Alerts & Symptoms", self.styles['CustomSubHeader']))

                alerts = report_data['alerts']
                if alerts:
                    alert_data = [['Date', 'Severity', 'Type', 'Description']]
                    for alert in alerts[:10]:  # Show last 10 alerts
                        alert_data.append([
                            alert.get('created_at', '')[:10],  # Date only
                            alert.get('severity', 'N/A'),
                            alert.get('type', 'N/A'),
                            alert.get('message', 'N/A')[:50] + '...' if len(alert.get('message', '')) > 50 else alert.get('message', 'N/A')
                        ])

                    alert_table = Table(alert_data, colWidths=[1*inch, 1*inch, 1.5*inch, 2.5*inch])
                    alert_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D32F2F')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFEBEE')]),
                    ]))

                    story.append(alert_table)
                else:
                    story.append(Paragraph("No alerts recorded in the selected period.", self.styles['MedicalData']))

                story.append(Spacer(1, 20))

            # Analytics Section
            if 'analytics' in report_data:
                story.append(Paragraph("Analytics Summary", self.styles['CustomSubHeader']))
                analytics = report_data['analytics']

                analytics_content = [
                    f"• Total Messages: {analytics.get('total_messages', 0)}",
                    f"• Average Response Time: {analytics.get('avg_response_time', 0):.1f} hours",
                    f"• Engagement Score: {analytics.get('engagement_score', 0):.1f}/100",
                    f"• Quiz Completion Rate: {analytics.get('quiz_completion_rate', 0):.1%}",
                ]

                for content in analytics_content:
                    story.append(Paragraph(content, self.styles['MedicalData']))

                story.append(Spacer(1, 20))

            # Medical Disclaimer
            story.append(PageBreak())
            story.append(Paragraph("MEDICAL DISCLAIMER", self.styles['CustomSubHeader']))

            disclaimer_text = """
            This report is generated automatically based on patient data collected through digital health monitoring systems.
            The information contained herein is for medical professionals only and should be interpreted by qualified healthcare providers.
            This report does not replace clinical judgment or direct patient examination.

            Data presented may include patient-reported symptoms and automated system alerts.
            All clinical decisions should be based on comprehensive evaluation including direct patient assessment.

            For questions about this report or patient care, please contact the responsible healthcare provider.
            """

            story.append(Paragraph(disclaimer_text.strip(), self.styles['Normal']))
            story.append(Spacer(1, 30))

            # Footer
            story.append(Paragraph(
                f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')} | Confidential Medical Information",
                self.styles['Footer']
            ))

            # Build PDF
            doc.build(story)

            if output_path:
                return output_path
            else:
                buffer.seek(0)
                return buffer.getvalue()

        except Exception as e:
            logger.error(f"Error generating patient report: {str(e)}")
            raise PDFGeneratorError(f"Failed to generate patient report: {str(e)}")

    def generate_analytics_report(
        self,
        analytics_data: Dict[str, Any],
        time_period: str,
        output_path: Optional[str] = None
    ) -> Union[bytes, str]:
        """
        Generate analytics dashboard report.

        Args:
            analytics_data: Analytics data
            time_period: Time period for the report
            output_path: Optional file path to save PDF

        Returns:
            PDF bytes if no output_path, file path if saved
        """
        try:
            # Create buffer or file
            if output_path:
                doc = SimpleDocTemplate(output_path, pagesize=A4)
            else:
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4)

            story = []

            # Header
            story.append(Paragraph(f"ANALYTICS REPORT - {time_period.upper()}", self.styles['CustomHeader']))
            story.append(Spacer(1, 20))

            # Summary Statistics
            story.append(Paragraph("Summary Statistics", self.styles['CustomSubHeader']))

            summary_data = [
                ['Total Patients', str(analytics_data.get('total_patients', 0))],
                ['Active Patients', str(analytics_data.get('active_patients', 0))],
                ['Messages Sent', str(analytics_data.get('messages_sent', 0))],
                ['Response Rate', f"{analytics_data.get('response_rate', 0):.1%}"],
                ['Average Response Time', f"{analytics_data.get('avg_response_time', 0):.1f} hours"],
                ['Quiz Completion Rate', f"{analytics_data.get('quiz_completion_rate', 0):.1%}"],
            ]

            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F5E8')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))

            story.append(summary_table)
            story.append(Spacer(1, 30))

            # Build PDF
            doc.build(story)

            if output_path:
                return output_path
            else:
                buffer.seek(0)
                return buffer.getvalue()

        except Exception as e:
            logger.error(f"Error generating analytics report: {str(e)}")
            raise PDFGeneratorError(f"Failed to generate analytics report: {str(e)}")

    def generate_simple_report(
        self,
        title: str,
        content: str,
        output_path: Optional[str] = None
    ) -> Union[bytes, str]:
        """
        Generate simple text report.

        Args:
            title: Report title
            content: Report content
            output_path: Optional file path to save PDF

        Returns:
            PDF bytes if no output_path, file path if saved
        """
        try:
            if output_path:
                doc = SimpleDocTemplate(output_path, pagesize=A4)
            else:
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4)

            story = []
            story.append(Paragraph(title, self.styles['CustomHeader']))
            story.append(Spacer(1, 20))
            story.append(Paragraph(content, self.styles['Normal']))

            doc.build(story)

            if output_path:
                return output_path
            else:
                buffer.seek(0)
                return buffer.getvalue()

        except Exception as e:
            logger.error(f"Error generating simple report: {str(e)}")
            raise PDFGeneratorError(f"Failed to generate simple report: {str(e)}")

    def _get_status_symbol(self, value: float, threshold: float) -> str:
        """Get status symbol based on value and threshold."""
        return "" if value >= threshold else "�"

    @staticmethod
    def save_pdf_to_file(pdf_bytes: bytes, file_path: str) -> str:
        """Save PDF bytes to file."""
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, 'wb') as f:
                f.write(pdf_bytes)

            return file_path
        except Exception as e:
            logger.error(f"Error saving PDF to file: {str(e)}")
            raise PDFGeneratorError(f"Failed to save PDF: {str(e)}")

    @staticmethod
    def pdf_to_base64(pdf_bytes: bytes) -> str:
        """Convert PDF bytes to base64 string."""
        return base64.b64encode(pdf_bytes).decode('utf-8')


# Alternative simple PDF generator for when ReportLab is not available
class SimplePDFGenerator:
    """Fallback PDF generator without external dependencies."""

    def __init__(self):
        logger.warning("Using simple PDF generator. Install reportlab for advanced features.")

    def generate_patient_report(self, patient_data, report_data, output_path=None):
        """Generate simple text-based report."""
        content = f"""
PATIENT REPORT
==============

Patient Information:
- Name: {patient_data.get('name', 'N/A')}
- ID: {patient_data.get('id', 'N/A')}
- Treatment Type: {patient_data.get('treatment_type', 'N/A')}
- Current Day: {patient_data.get('current_day', 'N/A')}
- Status: {self._get_patient_status(patient_data)}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Note: This is a simplified report. Install reportlab for full PDF functionality.
        """

        if output_path:
            with open(output_path, 'w') as f:
                f.write(content)
            return output_path

        return content.encode('utf-8')

    def generate_analytics_report(self, analytics_data, time_period, output_path=None):
        """Generate simple analytics report."""
        content = f"""
ANALYTICS REPORT - {time_period.upper()}
========================================

Summary:
- Total Patients: {analytics_data.get('total_patients', 0)}
- Active Patients: {analytics_data.get('active_patients', 0)}
- Messages Sent: {analytics_data.get('messages_sent', 0)}
- Response Rate: {analytics_data.get('response_rate', 0):.1%}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """

        if output_path:
            with open(output_path, 'w') as f:
                f.write(content)
            return output_path

        return content.encode('utf-8')


# Factory function to get appropriate PDF generator
def get_pdf_generator() -> Union[PDFGenerator, SimplePDFGenerator]:
    """Get PDF generator instance based on available dependencies."""
    try:
        return PDFGenerator()
    except PDFGeneratorError:
        return SimplePDFGenerator()