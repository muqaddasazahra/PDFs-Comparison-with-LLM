import fitz  # PyMuPDF
import pdfplumber
import json
import os

def parse_pdf(pdf_path):
    pdf_data = {
        "headings": [],
        "subheadings": [],
        "body": [],
        "tables": [],
        "layout": []
    }
    
    
    doc = fitz.open(pdf_path)
    
    HEADING_THRESHOLD = 14.0  
    SUBHEADING_THRESHOLD = 12.0  
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:  
                    if "spans" in line: 
                        for span in line["spans"]:
                            font_info = {
                                "page": page_num + 1,
                                "font": span["font"],
                                "size": span["size"],
                                "text": span["text"].strip(),
                                "bbox": span["bbox"]  # (x0, y0, x1, y1)
                            }
                            if span["size"] > HEADING_THRESHOLD:
                                pdf_data["headings"].append(font_info)
                            elif span["size"] > SUBHEADING_THRESHOLD:
                                pdf_data["subheadings"].append(font_info)
                            else:
                                pdf_data["body"].append(font_info)
                            pdf_data["layout"].append({
                                "page": page_num + 1,
                                "bbox": span["bbox"],
                                "text": span["text"].strip()
                            })
    
    doc.close()
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                pdf_data["tables"].append({
                    "page": page_num + 1,
                    "tables": tables
                })
    
    return pdf_data

def save_parsed_data(pdf_data, output_dir, pdf_name):
    
    os.makedirs(output_dir, exist_ok=True)
    
    categories = ["headings", "subheadings", "body", "tables", "layout"]
    for category in categories:
        with open(os.path.join(output_dir, f"{pdf_name}_{category}.json"), "w", encoding="utf-8") as f:
            json.dump(pdf_data[category], f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    pdf1_path = "ICMOrignal.pdf"
    pdf2_path = "ICMNew.pdf"
    output_dir = "parsed_output"
    
    # Parse both PDFs
    pdf1_data = parse_pdf(pdf1_path)
    pdf2_data = parse_pdf(pdf2_path)
    
    # Save parsed data
    save_parsed_data(pdf1_data, output_dir, "ICMOrignal")
    save_parsed_data(pdf2_data, output_dir, "ICMNew")