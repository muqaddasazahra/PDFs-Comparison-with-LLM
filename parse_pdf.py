import fitz  # PyMuPDF
import pdfplumber
import json

def parse_pdf(pdf_path):
    # Initialize data structure
    pdf_data = {
        "text": [],
        "fonts": [],
        "layout": []
    }
    
    # Open PDF with PyMuPDF
    doc = fitz.open(pdf_path)
    
    # Extract text and layout with PyMuPDF
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Extract text
        text = page.get_text("text")
        pdf_data["text"].append({"page": page_num + 1, "content": text})
        
        # Extract font information and bounding boxes
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        font_info = {
                            "page": page_num + 1,
                            "font": span["font"],
                            "size": span["size"],
                            "text": span["text"],
                            "bbox": span["bbox"]  # Bounding box: (x0, y0, x1, y1)
                        }
                        pdf_data["fonts"].append(font_info)
                        pdf_data["layout"].append({
                            "page": page_num + 1,
                            "bbox": span["bbox"],
                            "text": span["text"]
                        })
    
    doc.close()
    
    # Extract additional layout details with pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Extract tables (if any)
            tables = page.extract_tables()
            if tables:
                pdf_data["layout"].append({
                    "page": page_num + 1,
                    "tables": tables
                })
    
    return pdf_data

def save_parsed_data(pdf_data, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(pdf_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    pdf1_path = "ICMOrignal.pdf"
    pdf2_path = "ICMNew.pdf"
    
    # Parse both PDFs
    pdf1_data = parse_pdf(pdf1_path)
    pdf2_data = parse_pdf(pdf2_path)
    
    # Save parsed data to JSON files
    save_parsed_data(pdf1_data, "ICMOrignal.json")
    save_parsed_data(pdf2_data, "ICMNew.json")