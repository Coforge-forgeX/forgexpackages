from io import BytesIO
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import logging
import requests
import base64
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak, ListFlowable, ListItem
from PIL import Image


def markdown_to_pdf(md_content: str, output_filename=None):
    """
    Convert Markdown content to a PDF document with table and mermaid diagram support
    
    Args:
        md_content: Markdown string content to convert
        output_filename: Name of the output .pdf file (if None, returns BytesIO)
    
    Returns:
        BytesIO object if output_filename is None, otherwise saves to file
    """
    # Convert markdown to HTML using markdown-it (same as docx)
    md = MarkdownIt("gfm-like")
    html_content = md.render(md_content)
    
    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, features="lxml")
    
    # Create PDF document
    if output_filename is None:
        pdf_stream = BytesIO()
        doc = SimpleDocTemplate(pdf_stream, pagesize=letter,
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
    else:
        doc = SimpleDocTemplate(output_filename, pagesize=letter,
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Process all top-level elements
    for element in soup.children:
        process_element(element, elements, styles)
    
    # Build PDF
    doc.build(elements)
    
    if output_filename is None:
        pdf_stream.seek(0)
        return pdf_stream
    else:
        print(f"PDF document saved as '{output_filename}'")
        return None


def calculate_image_size(image_stream, max_width=6.5, max_height=8.0):
    """
    Calculate appropriate image size maintaining aspect ratio
    
    Args:
        image_stream: BytesIO stream containing image
        max_width: Maximum width in inches (default 6.5 for letter size)
        max_height: Maximum height in inches (default 8.0)
    
    Returns:
        tuple: (width, height) in inches, or None if image can't be processed
    """
    try:
        image_stream.seek(0)
        img = Image.open(image_stream)
        img_width, img_height = img.size
        
        # Calculate aspect ratio
        aspect_ratio = img_width / img_height
        
        # Determine best fit
        if aspect_ratio > 1:  # Landscape
            width = min(max_width, max_width)
            height = width / aspect_ratio
            if height > max_height:
                height = max_height
                width = height * aspect_ratio
        else:  # Portrait or square
            height = min(max_height, max_height * 0.6)
            width = height * aspect_ratio
            if width > max_width:
                width = max_width
                height = width / aspect_ratio
        
        image_stream.seek(0)
        return width * inch, height * inch
    except Exception as e:
        print(f"Warning: Could not calculate image size: {e}")
        image_stream.seek(0)
        return 5 * inch, None


def process_element(element, elements, styles, list_level=0):
    """Recursively process HTML elements and add to PDF"""
    
    if isinstance(element, str):
        # Handle text nodes
        text = element.strip()
        if text:
            p = Paragraph(text, styles['Normal'])
            elements.append(p)
            elements.append(Spacer(1, 0.1*inch))
        return
    
    # Handle different HTML tags
    tag_name = element.name
    
    if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        # Headers
        level = int(tag_name[1])
        style_name = f'Heading{level}'
        text = element.get_text().strip()
        if text:
            p = Paragraph(text, styles[style_name])
            elements.append(p)
            elements.append(Spacer(1, 0.1*inch))
    
    elif tag_name == 'p':
        # Paragraphs
        text = element.get_text().strip()
        if text:
            p = Paragraph(text, styles['Normal'])
            elements.append(p)
            elements.append(Spacer(1, 0.05*inch))
    
    elif tag_name in ['ul', 'ol']:
        # Lists
        list_items = []
        for li in element.find_all('li', recursive=False):
            text = li.get_text().strip()
            if text:
                list_items.append(ListItem(Paragraph(text, styles['Normal'])))
        
        if list_items:
            if tag_name == 'ul':
                bullet_type = 'bullet'
            else:
                bullet_type = '1'
            
            list_flowable = ListFlowable(list_items, bulletType=bullet_type, 
                                        start=None, leftIndent=20)
            elements.append(list_flowable)
            elements.append(Spacer(1, 0.1*inch))
    
    elif tag_name == 'table':
        # Tables - process programmatically like docx
        process_table(element, elements, styles)
    
    elif tag_name == 'hr':
        # Horizontal rule
        elements.append(Spacer(1, 0.1*inch))
        # Draw a line using a table
        line_table = Table([['']], colWidths=[6.5*inch])
        line_table.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 1, colors.grey),
        ]))
        elements.append(line_table)
        elements.append(Spacer(1, 0.1*inch))
    
    elif tag_name == 'blockquote':
        # Blockquote
        text = element.get_text().strip()
        if text:
            quote_style = ParagraphStyle(
                'Quote',
                parent=styles['Normal'],
                leftIndent=20,
                fontStyle='italic',
                textColor=colors.HexColor('#666666')
            )
            p = Paragraph(text, quote_style)
            elements.append(p)
            elements.append(Spacer(1, 0.1*inch))
    
    elif tag_name == 'pre':
        code_tag = element.find('code')
        if code_tag:
            lang_class = code_tag.get('class', [])
            language = None
            if lang_class:
                for cls in lang_class:
                    if cls.startswith('language-'):
                        language = cls.replace('language-', '')
                        break
            
            code_text = code_tag.get_text()
            
            # Handle Mermaid diagrams
            if language == 'mermaid':
                try:
                    code_text_clean = code_text.strip()
                    encoded = base64.urlsafe_b64encode(code_text_clean.encode('utf-8')).decode('ascii')
                    url = f"https://mermaid.ink/img/{encoded}"
                    
                    response = requests.get(url, timeout=30)
                    print("Mermaid image URL:", url)
                    
                    if response.status_code == 200:
                        image_stream = BytesIO(response.content)
                        width, height = calculate_image_size(image_stream)
                        
                        if height:
                            img = RLImage(image_stream, width=width, height=height)
                        else:
                            img = RLImage(image_stream, width=width)
                        
                        elements.append(img)
                        elements.append(Spacer(1, 0.1*inch))
                    else:
                        raise Exception(f"Status {response.status_code}")
                except Exception as e:
                    logging.info(f"Error generating mermaid diagram: {e}")
                    # Fallback: show as code with link
                    code_style = ParagraphStyle(
                        'Code',
                        parent=styles['Normal'],
                        fontName='Courier',
                        fontSize=8,
                        leftIndent=10,
                        backgroundColor=colors.HexColor('#f4f4f4')
                    )
                    fallback_text = f'[Mermaid Diagram - Render Failed]<br/><link href="{url}" color="blue">Click here to view</link>'
                    p = Paragraph(fallback_text, code_style)
                    elements.append(p)
                    elements.append(Spacer(1, 0.1*inch))
            else:
                # Regular code block
                code_style = ParagraphStyle(
                    'Code',
                    parent=styles['Normal'],
                    fontName='Courier',
                    fontSize=8,
                    leftIndent=10,
                    backgroundColor=colors.HexColor('#f4f4f4')
                )
                
                if language:
                    label = Paragraph(f"[{language}]", styles['Normal'])
                    elements.append(label)
                
                # Split code into lines and wrap each
                for line in code_text.split('\n'):
                    p = Paragraph(line if line else '&nbsp;', code_style)
                    elements.append(p)
                
                elements.append(Spacer(1, 0.1*inch))
    
    elif tag_name == 'code':
        # Inline code (if not already handled by <pre>)
        if element.parent and element.parent.name != 'pre':
            pass  # Will be handled by parent paragraph
    
    elif tag_name in ['strong', 'b', 'em', 'i', 'u', 'a']:
        # Inline elements - will be handled by parent
        pass
    
    else:
        # For other tags, process children
        for child in element.children:
            process_element(child, elements, styles, list_level)


def process_table(table_element, elements, styles):
    """Process HTML table and add to PDF programmatically"""
    rows = table_element.find_all('tr')
    if not rows:
        return
    
    # Determine number of columns
    max_cols = 0
    for row in rows:
        cols = len(row.find_all(['td', 'th']))
        max_cols = max(max_cols, cols)
    
    if max_cols == 0:
        return
    
    # Build table data
    table_data = []
    for row in rows:
        row_data = []
        cells = row.find_all(['td', 'th'])
        for cell in cells:
            cell_text = cell.get_text().strip()
            # Create Paragraph for cell content to enable text wrapping
            cell_style = ParagraphStyle(
                'CellStyle',
                parent=styles['Normal'],
                fontSize=7,
                leading=9
            )
            cell_para = Paragraph(cell_text, cell_style)
            row_data.append(cell_para)
        
        # Pad row if needed
        while len(row_data) < max_cols:
            row_data.append('')
        
        table_data.append(row_data)
    
    # Calculate column widths dynamically
    available_width = 7.0 * inch  # Usable width on page
    
    # Set specific widths for first two columns (# and TC-ID)
    if max_cols >= 2:
        col_widths = [0.3*inch, 0.6*inch] + [None] * (max_cols - 2)
        remaining_width = available_width - 0.9*inch
        equal_width = remaining_width / (max_cols - 2) if max_cols > 2 else remaining_width
        col_widths = [0.3*inch, 0.6*inch] + [equal_width] * (max_cols - 2)
    else:
        col_widths = [available_width / max_cols] * max_cols
    
    # Create table
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    # Style the table
    table_style = TableStyle([
        # Headers (first row)
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        
        # All cells
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        
        # Zebra striping
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ])
    
    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 0.2*inch))