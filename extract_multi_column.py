import pymupdf4llm
import pathlib
import json
import pymupdf
import sys

md_text=pymupdf4llm.to_markdown("contract.pdf", pages=range(8,39))
pathlib.Path("two_sided_output.md").write_bytes(md_text.encode())

md_text_chunks=pymupdf4llm.to_markdown("contract.pdf", pages=[5,6], page_chunks=True,extract_words=True )
with open("two_sided_output_in_chunks.json","w") as f:
   json.dump(md_text_chunks, f, indent=4, ensure_ascii=False) 
   


doc = pymupdf.open("contract.pdf")
out = open("output.txt", "wb") 
for page in doc: 
    text = page.get_text().encode("utf8") 
    out.write(text) 
    out.write(bytes((12,))) 
out.close()


#Extract two column data using pymupdf
pdf_path = "contract.pdf"
doc = pymupdf.open(pdf_path)
pages_to_extract = [6, 39]  # zero-based

extracted_data = []

for page_num in pages_to_extract:
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
                            "bbox": span["bbox"]            
                        }
                        extracted_data.append(font_info)

# Save extracted font info to JSON
with open("pymupdf_font_info.json", "w", encoding="utf-8") as f:
    json.dump(extracted_data, f, indent=4, ensure_ascii=False)

doc.close()
      
   
   
#Extract two column data using pymupdf (json method)

def parse_pdf_file(pdf_path,output_json_path,pages_to_extract):
    doc = pymupdf.open(pdf_path)

    extracted_output = []

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

        extracted_output.append(page_json)

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(extracted_output, f, indent=4, ensure_ascii=False)


    doc.close()
    
#######################Extract two column data using pymupdf ( html method)####################
pdf_path = "contract.pdf"
doc = pymupdf.open(pdf_path)
pages_to_extract = [6, 39]  

extracted_html = ""

for page_num in pages_to_extract:
    page = doc[page_num]
    extracted_html += page.get_text("html") + "\n"

with open("pymupdf_info.html", "w", encoding="utf-8") as f:
    f.write(extracted_html)

doc.close()

#######################Extract two column data using pymupdf ( jso nmethod)####################
pdf_path = "contract.pdf"
doc = pymupdf.open(pdf_path)
pages_to_extract = [6, 39]  

extracted_html = ""

for page_num in pages_to_extract:
    page = doc[page_num]
    page_json = json.loads(page.get_text("json"))

with open("structure.json", "w", encoding="utf-8") as f:
    json.dump(page_json, f, indent=4, ensure_ascii=False)


doc.close()
   
   
######################################################################################

def main():
    parse_pdf_file(
        pdf_path="subcontarctor_contract.pdf",
        output_json_path="subcontarctor_contract.pdf.json",
        pages_to_extract=range(4, 30)
    )

    parse_pdf_file(
        pdf_path="contract.pdf",
        output_json_path="contract.json",
        pages_to_extract=range(6, 38)  
    )


if __name__ == "__main__":
    main()
   
