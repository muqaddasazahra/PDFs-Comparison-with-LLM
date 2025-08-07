import json
import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def load_json_data(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def query_grok(prompt, model="openai/gpt-oss-120b"):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000
    }
    response = requests.post(GROQ_API_URL, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def compare_pdfs(pdf1_data, pdf2_data):
    # Compare text content
    text_prompt = """
    Compare the skills and work experience of two PDFs. Here is the skill and experience from PDF1:
    {}
    Here is the skills and experience from PDF2:
    {}
    Summarize the differences and similarities in the text content.
    """.format(json.dumps(pdf1_data["text"], indent=2), json.dumps(pdf2_data["text"], indent=2))
    
    text_comparison = query_grok(text_prompt)
    print("Text Comparison:")
    print(text_comparison)
    print("\n" + "="*50 + "\n")
    
    # Compare fonts
    font_prompt = """
    Compare the font used in two files. Here is the font used in PDF1:
    {}
    Here is the font used in PDF2:
    {}
    Identify differences and similarities in font names, sizes, and usage.
    """.format(json.dumps(pdf1_data["fonts"], indent=2), json.dumps(pdf2_data["fonts"], indent=2))
    
    font_comparison = query_grok(font_prompt)
    print("Font Comparison:")
    print(font_comparison)
    print("\n" + "="*50 + "\n")
    
    # Compare layout
    layout_prompt = """
    Compare the layout of two PDFs.  Here is the layout in PDF1:
    {}
    Here is the layout used in PDF2:
    {}
    Analyze differences and similarities in text positioning (bounding boxes) and table presence.
    """.format(json.dumps(pdf1_data["layout"], indent=2), json.dumps(pdf2_data["layout"], indent=2))
    
    layout_comparison = query_grok(layout_prompt)
    print("Layout Comparison:")
    print(layout_comparison)

if __name__ == "__main__":
    # Load parsed data
    pdf1_data = load_json_data("pdf1_data.json")
    pdf2_data = load_json_data("pdf2_data.json")
    
    # Compare PDFs
    compare_pdfs(pdf1_data, pdf2_data)