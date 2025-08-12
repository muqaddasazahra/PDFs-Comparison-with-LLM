import json
import pymupdf
import sys


def parse_pdf_file(pdf_path,output_json_path,pages_to_extract):
    doc = pymupdf.open(pdf_path)

    extracted_output = {"pages": []} 

    for page_num in pages_to_extract:
        page = doc[page_num]
        page_json = json.loads(page.get_text("json"))
        
        for block in page_json.get("blocks", []):
            if "lines" in block:
                for i, line in enumerate(block["lines"]):
                    if "spans" in line:
                        filtered_spans = []
                        for span in line["spans"]:
                            filtered_spans.append({
                                "font": span.get("font"),
                                "size": span.get("size"),
                                "color": span.get("color"),
                                "origin": span.get("origin"),
                                "bbox": span.get("bbox"),
                                "text": span.get("text")
                            })
                        block["lines"][i] = {
                            "bbox": line.get("bbox"),
                            "spans": filtered_spans
                        }
                        

        extracted_output["pages"].append({
                "page_number": page_num + 1, 
                "width": page_json.get("width"),
                "height": page_json.get("height"),
                "blocks": page_json.get("blocks", [])
            })     

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(extracted_output, f, indent=4, ensure_ascii=False)


    doc.close()
    

def main():
    args=sys.argv
    parse_pdf_file(
        pdf_path="contract.pdf",
        output_json_path="contract.json",
        pages_to_extract = range(6,38)

    )
    
    parse_pdf_file(
        pdf_path="subcontarctor_contract.pdf",
        output_json_path="subcontarctor.json",
        pages_to_extract = range(4,30)

    )


if __name__ == "__main__":
    main()
   