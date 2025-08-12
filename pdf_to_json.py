#Removes Duplicate blocks - page numbers in footers not removed
import json
import pymupdf
import sys
import re
import copy
import base64
import hashlib
import difflib
import statistics
from itertools import combinations
from collections import defaultdict, Counter

# ---------- Utility functions for repeated block detection ----------

def _normalize_text(s: str, remove_digits: bool = True) -> str:
    if s is None:
        return ""
    s = s.strip().lower()
    s = re.sub(r'\s+', ' ', s)
    if remove_digits:
        s = re.sub(r'\d+', '', s)
    return s.strip()

def _concat_block_text(block: dict) -> str:
    texts = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            texts.append(span.get("text", "") or "")
    return "".join(texts).strip()

def _median_pairwise_similarity(strs):
    strs = [s for s in strs if s is not None]
    if len(strs) <= 1:
        return 1.0
    sims = []
    for a, b in combinations(strs, 2):
        if not a and not b:
            sims.append(1.0)
        else:
            sims.append(difflib.SequenceMatcher(None, a, b).ratio())
    return statistics.median(sims) if sims else 1.0

def _image_hash_from_base64(base64_str: str):
    if not base64_str:
        return None
    try:
        b = base64.b64decode(base64_str)
        return hashlib.sha256(b).hexdigest()
    except Exception:
        return hashlib.sha256(base64_str.encode("utf-8")).hexdigest()
    
def remove_repeated_blocks(
    parsed_doc: dict,
    text_sim_threshold: float = 0.95,
    page_presence_threshold: float = 0.95,
    bbox_tol: float = 3.0
):
    pages = parsed_doc.get("pages", [])
    total_pages = max(1, len(pages))
    quant = float(bbox_tol)

    groups = defaultdict(list)
    for p_idx, page in enumerate(pages):
        for b_idx, block in enumerate(page.get("blocks", [])):
            bbox = block.get("bbox", [])
            if not bbox or len(bbox) != 4:
                qbbox = (0, 0, 0, 0)
            else:
                qbbox = tuple(int(round(coord / quant)) for coord in bbox)

            if block.get("type") == 0:  # text
                text = _concat_block_text(block)
                norm_text = _normalize_text(text, remove_digits=True)  # ignore numbers
                content_key = norm_text
            elif block.get("type") == 1:  # image
                base64_img = block.get("image") or block.get("image_bytes") or ""
                img_hash = _image_hash_from_base64(base64_img)
                content_key = img_hash
            else:
                content_key = None

            key = (block.get("type"), qbbox, content_key)
            groups[key].append({
                "page_index": p_idx,
                "block_index": b_idx,
                "block": block
            })

    to_remove = defaultdict(list)
    report = {"removed_groups": [], "kept_groups": []}

    for key, instances in groups.items():
        block_type, qbbox, content_key = key
        pages_with = sorted(set(inst["page_index"] for inst in instances))
        presence_ratio = len(pages_with) / total_pages

        if presence_ratio >= page_presence_threshold:
            if block_type == 0:  # text
                texts_nodigits = [
                    _normalize_text(_concat_block_text(inst["block"]), remove_digits=True)
                    for inst in instances
                ]
                median_sim = _median_pairwise_similarity(texts_nodigits)
                if median_sim >= text_sim_threshold:
                    for inst in instances:
                        to_remove[inst["page_index"]].append(inst["block_index"])
                    report["removed_groups"].append({
                        "key": key,
                        "type": "text",
                        "pages_seen": len(pages_with),
                        "presence_ratio": presence_ratio,
                        "median_similarity": median_sim,
                        "example_texts": texts_nodigits[:3],
                        "pages": [p + 1 for p in pages_with],  # human-friendly page numbers
                        "block_indexes": [inst["block_index"] for inst in instances]
                    })
                else:
                    report["kept_groups"].append({
                        "key": key,
                        "type": "text",
                        "pages_seen": len(pages_with),
                        "presence_ratio": presence_ratio,
                        "median_similarity": median_sim
                    })

            elif block_type == 1:  # image
                if content_key is not None:
                    for inst in instances:
                        to_remove[inst["page_index"]].append(inst["block_index"])
                    report["removed_groups"].append({
                        "key": key,
                        "type": "image",
                        "pages_seen": len(pages_with),
                        "presence_ratio": presence_ratio,
                        "hash": content_key,
                        "pages": [p + 1 for p in pages_with],
                        "block_indexes": [inst["block_index"] for inst in instances]
                    })
                else:
                    report["kept_groups"].append({
                        "key": key,
                        "type": "image",
                        "pages_seen": len(pages_with),
                        "presence_ratio": presence_ratio
                    })

        else:
            report["kept_groups"].append({
                "key": key,
                "type": "other" if block_type not in (0, 1) else ("text" if block_type == 0 else "image"),
                "pages_seen": len(pages_with),
                "presence_ratio": presence_ratio
            })

    # prune
    pruned = copy.deepcopy(parsed_doc)
    for p_idx, page in enumerate(pruned.get("pages", [])):
        blocks = page.get("blocks", [])
        remove_indices = sorted(set(to_remove.get(p_idx, [])), reverse=True)
        for ridx in remove_indices:
            if 0 <= ridx < len(blocks):
                del blocks[ridx]
        page["blocks"] = blocks

    return pruned, report


# ---------- PDF parsing and cleaning ----------

def parse_pdf_file(pdf_path, output_json_path, pages_to_extract):
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

    doc.close()

    # Remove repeated blocks
    cleaned_output, report = remove_repeated_blocks(extracted_output)

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_output, f, indent=4, ensure_ascii=False)

    # Save removal report
    report_path = output_json_path.replace(".json", "_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

def main():
    parse_pdf_file(
        pdf_path="contract.pdf",
        output_json_path="contract.json",
        pages_to_extract=range(6, 38)
    )

    parse_pdf_file(
        pdf_path="subcontarctor_contract.pdf",
        output_json_path="subcontarctor.json",
        pages_to_extract=range(4, 30)
    )

if __name__ == "__main__":
    main()

