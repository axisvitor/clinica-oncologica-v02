"""
PDF generation utilities for medical reports.
Handles report layout, styling, and content generation using ReportLab.
"""
import io
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any, BinaryIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from pydantic import BaseModel, Field

from app.config import settings
from app.exceptions import ExternalServiceError


logger = logging.getLogger(__name__)


class ReportSection(BaseModel):
    """Report section data."""
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    subsections: List['ReportSection'] = Field(default_factory=list, description="Nested subsections")


class PatientReportData(BaseModel):
    """Patient report data structure."""
    patient_name: str = Field(..., description="Patient's full name")
    patient_id: str = Field(..., description="Patient ID")
    doctor_name: str = Field(..., description="Doctor's name")
    report_period: str = Field(..., description="Report period (e.g., 'Week 1-4')")
    generated_date: datetime = Field(default_factory=datetime.utcnow, description="Report generation date")
    
    # Report sections
    executive_summary: str = Field(..., description="Executive summary")
    treatment_progress: ReportSection = Field(..., description="Treatment progress section")
    symptoms_analysis: ReportSection = Field(..., description="Symptoms analysis section")
    medication_adherence: ReportSection = Field(..., description="Medication adherence section")
    recommendations: ReportSection = Field(..., description="Recommendations section")
    
    # Data tables
    quiz_responses: List[Dict[str, Any]] = Field(default_factory=list, description="Quiz response data")
    message_statistics: Dict[str, Any] = Field(default_factory=dict, description="Message statistics")
    alert_summary: List[Dict[str, Any]] = Field(default_factory=list, description="Alert summary")


class PDFGeneratorError(ExternalServiceError):
    """PDF generation specific error."""
    pass


class MedicalReportGenerator:
    """
    Medical report PDF generator.
    
    Creates professional medical reports with proper formatting,
    charts, tables, and medical styling.
    """
    
    def __init__(
        self,
        page_size=A4,
        margin_top: float = 1.0,
        margin_bottom: float = 1.0,
        margin_left: float = 1.0,
        margin_right: float = 1.0
    ):
        """
        Initialize PDF generator.
        
        Args:
            page_size: Page size (A4, letter, etc.)
            margin_top: Top margin in inches
            margin_bottom: Bottom margin in inches
            margin_left: Left margin in inches
            margin_right: Right margin in inches
        """
        self.page_size = page_size
        self.margin_top = margin_top * inch
        self.margin_bottom = margin_bottom * inch
        self.margin_left = margin_left * inch
        self.margin_right = margin_right * inch
        
        # Setup styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
        logger.info("Medical report generator initialized")
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for medical reports."""
        
        # Report title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.darkblue,
            borderWidth=1,
            borderColor=colors.darkblue,
            borderPadding=5
        ))
        
        # Subsection header style
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12,
            textColor=colors.darkgreen
        ))
        
        # Medical data style
        self.styles.add(ParagraphStyle(
            name='MedicalData',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            fontName='Helvetica'
        ))
        
        # Executive summary style
        self.styles.add(ParagraphStyle(
            name='ExecutiveSummary',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=12,
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            backColor=colors.lightgrey,
            borderWidth=1,
            borderColor=colors.grey,
            borderPadding=10
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.grey
        ))
    
    def _create_header(self, report_data: PatientReportData) -> List:
        """Create report header with patient and doctor information."""
        elements = []
        
        # Report title
        title = f"Medical Report - {report_data.patient_name}"
        elements.append(Paragraph(title, self.styles['ReportTitle']))
        elements.append(Spacer(1, 20))
        
        # Patient information table
        patient_info = [
            ['Patient Information', ''],
            ['Name:', report_data.patient_name],
            ['Patient ID:', report_data.patient_id],
            ['Doctor:', report_data.doctor_name],
            ['Report Period:', report_data.report_period],
            ['Generated:', report_data.generated_date.strftime('%B %d, %Y at %I:%M %p')]
        ]
        
        patient_table = Table(patient_info, colWidths=[2*inch, 4*inch])
        patient_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(patient_table)
        elements.append(Spacer(1, 30))
        
        return elements
    
    def _create_executive_summary(self, report_data: PatientReportData) -> List:
        """Create executive summary section."""
        elements = []
        
        elements.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        elements.append(Paragraph(report_data.executive_summary, self.styles['ExecutiveSummary']))
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_section(self, section: ReportSection, style_name: str = 'SectionHeader') -> List:
        """Create a report section with subsections."""
        elements = []
        
        # Section title
        elements.append(Paragraph(section.title, self.styles[style_name]))
        
        # Section content
        if section.content:
            elements.append(Paragraph(section.content, self.styles['MedicalData']))
            elements.append(Spacer(1, 10))
        
        # Subsections
        for subsection in section.subsections:
            sub_elements = self._create_section(subsection, 'SubsectionHeader')
            elements.extend(sub_elements)
        
        elements.append(Spacer(1, 15))
        return elements
    
    def _create_quiz_responses_table(self, quiz_responses: List[Dict[str, Any]]) -> List:
        """Create quiz responses summary table."""
        if not quiz_responses:
            return []
        
        elements = []
        elements.append(Paragraph("Quiz Responses Summary", self.styles['SectionHeader']))
        
        # Prepare table data
        table_data = [['Date', 'Quiz Type', 'Score', 'Key Responses']]
        
        for response in quiz_responses:
            table_data.append([
                response.get('date', 'N/A'),
                response.get('quiz_type', 'N/A'),
                response.get('score', 'N/A'),
                response.get('key_responses', 'N/A')
            ])
        
        # Create table
        quiz_table = Table(table_data, colWidths=[1.5*inch, 2*inch, 1*inch, 2.5*inch])
        quiz_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        elements.append(quiz_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_message_statistics(self, message_stats: Dict[str, Any]) -> List:
        """Create message statistics section."""
        if not message_stats:
            return []
        
        elements = []
        elements.append(Paragraph("Communication Statistics", self.styles['SectionHeader']))
        
        # Statistics table
        stats_data = [
            ['Metric', 'Value'],
            ['Total Messages Sent', str(message_stats.get('total_sent', 0))],
            ['Messages Received', str(message_stats.get('total_received', 0))],
            ['Response Rate', f"{message_stats.get('response_rate', 0):.1f}%"],
            ['Average Response Time', message_stats.get('avg_response_time', 'N/A')],
            ['Most Active Day', message_stats.get('most_active_day', 'N/A')]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_alert_summary(self, alerts: List[Dict[str, Any]]) -> List:
        """Create alert summary section."""
        if not alerts:
            return []
        
        elements = []
        elements.append(Paragraph("Alert Summary", self.styles['SectionHeader']))
        
        # Alert table
        alert_data = [['Date', 'Severity', 'Type', 'Description', 'Status']]
        
        for alert in alerts:
            alert_data.append([
                alert.get('date', 'N/A'),
                alert.get('severity', 'N/A'),
                alert.get('type', 'N/A'),
                alert.get('description', 'N/A')[:50] + '...' if len(alert.get('description', '')) > 50 else alert.get('description', 'N/A'),
                alert.get('status', 'N/A')
            ])
        
        alert_table = Table(alert_data, colWidths=[1*inch, 1*inch, 1.5*inch, 2.5*inch, 1*inch])
        alert_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.red),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        elements.append(alert_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_footer(self) -> List:
        """Create report footer."""
        elements = []
        
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
        elements.append(Spacer(1, 10))
        
        footer_text = f"""
        This report was generated automatically by the Hormonia Healthcare System.
        Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}.
        For questions about this report, please contact your healthcare provider.
        """
        
        elements.append(Paragraph(footer_text, self.styles['Footer']))
        
        return elements
    
    def generate_patient_report(
        self,
        report_data: PatientReportData,
        output_path: Optional[str] = None
    ) -> bytes:
        """
        Generate complete patient medical report PDF.
        
        Args:
            report_data: Patient report data
            output_path: Optional file path to save PDF
            
        Returns:
            PDF content as bytes
            
        Raises:
            PDFGeneratorError: On PDF generation failures
        """
        try:
            # Create PDF buffer
            buffer = io.BytesIO()
            
            # Create document
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self.page_size,
                topMargin=self.margin_top,
                bottomMargin=self.margin_bottom,
                leftMargin=self.margin_left,
                rightMargin=self.margin_right
            )
            
            # Build document elements
            elements = []
            
            # Header
            elements.extend(self._create_header(report_data))
            
            # Executive summary
            elements.extend(self._create_executive_summary(report_data))
            
            # Treatment progress
            elements.extend(self._create_section(report_data.treatment_progress))
            
            # Symptoms analysis
            elements.extend(self._create_section(report_data.symptoms_analysis))
            
            # Medication adherence
            elements.extend(self._create_section(report_data.medication_adherence))
            
            # Quiz responses table
            elements.extend(self._create_quiz_responses_table(report_data.quiz_responses))
            
            # Message statistics
            elements.extend(self._create_message_statistics(report_data.message_statistics))
            
            # Alert summary
            elements.extend(self._create_alert_summary(report_data.alert_summary))
            
            # Recommendations
            elements.extend(self._create_section(report_data.recommendations))
            
            # Footer
            elements.extend(self._create_footer())
            
            # Build PDF
            doc.build(elements)
            
            # Get PDF content
            pdf_content = buffer.getvalue()
            buffer.close()
            
            # Save to file if path provided
            if output_path:
                with open(output_path, 'wb') as f:
                    f.write(pdf_content)
                logger.info(f"PDF report saved to: {output_path}")
            
            logger.info(f"Generated PDF report for patient: {report_data.patient_name}")
            return pdf_content
            
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise PDFGeneratorError(f"Failed to generate PDF report: {str(e)}")
    
    def generate_summary_report(
        self,
        title: str,
        sections: List[ReportSection],
        metadata: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> bytes:
        """
        Generate a simple summary report.
        
        Args:
            title: Report title
            sections: List of report sections
            metadata: Report metadata
            output_path: Optional file path to save PDF
            
        Returns:
            PDF content as bytes
        """
        try:
            buffer = io.BytesIO()
            
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self.page_size,
                topMargin=self.margin_top,
                bottomMargin=self.margin_bottom,
                leftMargin=self.margin_left,
                rightMargin=self.margin_right
            )
            
            elements = []
            
            # Title
            elements.append(Paragraph(title, self.styles['ReportTitle']))
            elements.append(Spacer(1, 30))
            
            # Metadata
            if metadata:
                meta_data = [['Report Information', '']]
                for key, value in metadata.items():
                    meta_data.append([key.replace('_', ' ').title() + ':', str(value)])
                
                meta_table = Table(meta_data, colWidths=[2*inch, 4*inch])
                meta_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                
                elements.append(meta_table)
                elements.append(Spacer(1, 30))
            
            # Sections
            for section in sections:
                elements.extend(self._create_section(section))
            
            # Footer
            elements.extend(self._create_footer())
            
            # Build PDF
            doc.build(elements)
            
            pdf_content = buffer.getvalue()
            buffer.close()
            
            if output_path:
                with open(output_path, 'wb') as f:
                    f.write(pdf_content)
            
            return pdf_content
            
        except Exception as e:
            logger.error(f"Summary report generation failed: {e}")
            raise PDFGeneratorError(f"Failed to generate summary report: {str(e)}")


# Global instance
_pdf_generator: Optional[MedicalReportGenerator] = None


def get_pdf_generator() -> MedicalReportGenerator:
    """Get global PDF generator instance."""
    global _pdf_generator
    
    if _pdf_generator is None:
        _pdf_generator = MedicalReportGenerator()
    
    return _pdf_generator