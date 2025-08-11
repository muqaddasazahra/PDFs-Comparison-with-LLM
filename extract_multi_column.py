import pymupdf4llm
import pathlib
import json

md_text=pymupdf4llm.to_markdown("contract.pdf", pages=[5,6])
pathlib.Path("two_sided_output.md").write_bytes(md_text.encode())

md_text_chunks=pymupdf4llm.to_markdown("contract.pdf", pages=[5,6], page_chunks=True,extract_words=True )
with open("two_sided_output_in_chunks.json","w") as f:
   json.dump(md_text_chunks, f, indent=4, ensure_ascii=False) 
   

llama_reader = pymupdf4llm.LlamaMarkdownReader()
llama_docs = llama_reader.load_data("contract.pdf")

   
   
