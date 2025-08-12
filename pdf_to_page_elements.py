import json
import re
import fitz  # PyMuPDF


# --- Helpers ---------------------------------------------------------------

def collapse_ws(s: str) -> str:
    """Normalize whitespace and spacing around dots/parentheses."""
    if not s:
        return ""
    s = s.replace("\xa0", " ")              # NBSP -> space
    s = re.sub(r"[ \t\r\f\v]+", " ", s)     # collapse runs of spaces
    # Normalize spaces around dots in the numbering portion: "6 . 1 . 3" -> "6.1.3"
    s = re.sub(r"\s*\.\s*", ".", s)
    # Also normalize spaces around a right parenthesis after the number: "6 )" -> "6)"
    s = re.sub(r"\s*\)\s*", ")", s)
    return s.strip()


# Accepts:
#  "5 text", "5. text", "5) text", "5 - text"
#  "6.1 text", "6.1. text", "6.1) text", "6.1 - text"
#  "6 . 1   text" (we normalize spaces around dots beforehand)
HEADING_RE = re.compile(
    r""" ^
         \s*
         (?P<num>\d+(?:[.)]?\d+)*)           # 5  | 5.1 | 5)1 (will be normalized)
         \s*
         (?:[.)-])?                          # optional trailing punctuation after the number
         \s*
         (?P<title>\S.+?)                    # title must start non-space and have at least one char
         \s*
       $ """,
    re.X
)

def normalize_number(num_str: str) -> str:
    """Turn '6 . 1.' / '6.1.' / '6)1' into '6.1'."""
    parts = re.findall(r"\d+", num_str or "")
    return ".".join(parts)

def line_text_from_spans(line: dict, gap_px: float = 0.1) -> str:
    """
    Rebuild a line's visible text from spans, preserving natural spacing.
    We insert a single space only if there is a visible horizontal gap.
    Very small gap_px keeps us from depending on precise bbox spacing.
    """
    spans = sorted(line.get("spans", []), key=lambda s: s.get("bbox", [0,0,0,0])[0])
    out, last_x1 = [], None
    for sp in spans:
        x0, _, x1, _ = sp.get("bbox", [0,0,0,0])
        t = (sp.get("text") or "")
        # Normalize NBSP inside each span early to avoid matching issues
        t = t.replace("\xa0", " ")
        if last_x1 is not None:
            if (x0 - last_x1) > gap_px and out and not out[-1].endswith(" "):
                out.append(" ")
        out.append(t)
        last_x1 = x1
    return "".join(out)

def extract_numbered_heading_from_line(line: dict):
    """
    Detect '5. text', '5 text', '6.1 text', etc., even when number and title
    are split across spans on the same line.
    """
    raw = line_text_from_spans(line)
    txt = collapse_ws(raw)

    # Extra safety: allow no space between '.' and title, e.g. "5.text"
    # We'll create a match string that tolerates missing spaces after punctuation.
    # The HEADING_RE already uses \s* around punctuation, so this helps.
    m = HEADING_RE.match(txt)
    if not m:
        return None

    num_raw = m.group("num")
    title = m.group("title").strip()

    num_norm = normalize_number(num_raw)
    parts = [int(p) for p in num_norm.split(".")] if num_norm else []
    level = max(1, len(parts))

    return {
        "number": num_norm,                 # "5" or "6.1.3"
        "number_parts": parts,              # [5] or [6,1,3]
        "level": level,                     # 1 = heading, 2+ = subheading
        "type": "heading" if level == 1 else "subheading",
        "title": title,                     # e.g., "Design and Documentation"
        "text": f"{num_norm} {title}",
        "bbox": line.get("bbox"),
        # for debugging:
        # "raw": raw, "normalized": txt
    }


# --- Main ------------------------------------------------------------------

def parse_pdf_file(pdf_path: str, output_json_path: str, pages_to_extract):
    """
    - Grabs PyMuPDF JSON.
    - Keeps essential span info only.
    - Extracts numbered headings (and subheadings like 6.1, 6.1.3) even if the number
      and title are split across spans on the same line.
    """
    doc = fitz.open(pdf_path)
    extracted_output = {"file": pdf_path, "pages": []}

    if isinstance(pages_to_extract, (range, list, tuple)):
        page_indices = list(pages_to_extract)
    else:
        page_indices = [pages_to_extract]

    for page_idx in page_indices:
        page = doc[page_idx]
        page_json = json.loads(page.get_text("json"))

        # Filter spans (keep essentials to reduce noise/size)
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
                                "text": span.get("text"),
                            })
                        block["lines"][i] = {
                            "bbox": line.get("bbox"),
                            "spans": filtered_spans
                        }

        # Extract headings/subheadings
        headings = []
        for block in page_json.get("blocks", []):
            for line in block.get("lines", []):
                h = extract_numbered_heading_from_line(line)
                if h:
                    headings.append(h)

        extracted_output["pages"].append({
            "page_number": page.number + 1,
            "width": page.rect.width,
            "height": page.rect.height,
            "headings": headings,
            # keep the filtered blocks if you need them downstream; remove if not
            "blocks": page_json.get("blocks", [])
        })

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(extracted_output, f, ensure_ascii=False, indent=2)

    print(f"Saved: {output_json_path}")


# --- Example usage ---------------------------------------------------------

def main():
    parse_pdf_file(
        pdf_path="file1.pdf",
        output_json_path="contract_out.json",
        pages_to_extract=range(6, 38)   # adjust as needed
    )

if __name__ == "__main__":
    main()
