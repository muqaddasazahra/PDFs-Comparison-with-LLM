import re
import difflib
import statistics
import base64
import hashlib
import copy
from collections import defaultdict
from itertools import combinations

def _normalize_text(s: str, remove_digits: bool = True, case_sensitive: bool = True) -> str:
    if s is None:
        return ""
    s = s.strip()
    if not case_sensitive:
        s = s.lower()
    s = re.sub(r'\s+', ' ', s)
    if remove_digits:
        s = re.sub(r'\d+', '', s)
    return s.strip()

def _normalize_text_pattern(s: str, case_sensitive: bool = True) -> str:
    if s is None:
        return ""
    s = s.strip()
    if not case_sensitive:
        s = s.lower()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'(?i)page\s+\d+\s+of\s+\d+', 'page X of Y', s)
    s = re.sub(r'(?i)page\s+\d+', 'page X', s)
    s = re.sub(r'\d+', 'X', s)
    return s.strip()

def _create_content_pattern_key(block: dict) -> str:
    text = _concat_block_text(block)
    pattern_text = _normalize_text_pattern(text, case_sensitive=True)
    non_empty_spans = len(_get_non_empty_text_spans(block))
    total_lines = len(block.get("lines", []))
    return f"pattern:{pattern_text}|spans:{non_empty_spans}|lines:{total_lines}"

def _concat_block_text(block: dict) -> str:
    texts = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "") or ""
            texts.append(text)
    return "".join(texts).strip()

def _get_non_empty_text_spans(block: dict) -> list:
    non_empty_spans = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "") or ""
            if text.strip():
                non_empty_spans.append(text.strip())
    return non_empty_spans

def _is_mostly_empty_block(block: dict, empty_threshold: float = 0.8) -> bool:
    total_spans = 0
    empty_spans = 0
    
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            total_spans += 1
            text = span.get("text", "") or ""
            if not text.strip():
                empty_spans += 1
    
    if total_spans == 0:
        return True
    
    return (empty_spans / total_spans) >= empty_threshold

def _is_header_footer_block(block: dict) -> bool:
    text = _concat_block_text(block)
    text_lower = text.lower()
    
    has_page_info = _has_page_pattern(text)
    
    header_footer_words = ['page', 'initial', 'date', 'signature', 'confidential', 'draft']
    has_header_words = any(word in text_lower for word in header_footer_words)
    
    non_empty_spans = _get_non_empty_text_spans(block)
    total_spans = sum(len(line.get("spans", [])) for line in block.get("lines", []))
    
    has_mixed_content = len(non_empty_spans) >= 1 and len(non_empty_spans) < total_spans
    
    return (has_page_info or has_header_words) and has_mixed_content

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

def _has_page_pattern(text: str) -> bool:
    text = text.lower()
    patterns = [
        r'page\s+\d+\s+of\s+\d+',
        r'page\s+\d+',
        r'\d+\s+of\s+\d+',
    ]
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False

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
    pattern_sim_threshold: float = 0.8,
    page_presence_threshold: float = 0.95,
    bbox_tol: float = 3.0,
    empty_block_threshold: float = 0.8
):
    pages = parsed_doc.get("pages", [])
    total_pages = max(1, len(pages))
    quant = float(bbox_tol)

    groups = defaultdict(list)
    pattern_groups = defaultdict(list)
    block_index_groups = defaultdict(list)
    
    for p_idx, page in enumerate(pages):
        for b_idx, block in enumerate(page.get("blocks", [])):
            bbox = block.get("bbox", [])
            if not bbox or len(bbox) != 4:
                qbbox = (0, 0, 0, 0)
            else:
                qbbox = tuple(int(round(coord / quant)) for coord in bbox)

            if block.get("type") == 0:  # text
                text = _concat_block_text(block)
                norm_text = _normalize_text(text, remove_digits=True)
                
                pattern_key = _create_content_pattern_key(block)
                pattern_groups[pattern_key].append({
                    "page_index": p_idx,
                    "block_index": b_idx,
                    "block": block,
                    "text": text,
                    "bbox": qbbox
                })
                
                content_key = norm_text
                
                is_mostly_empty = _is_mostly_empty_block(block, empty_block_threshold)
                if is_mostly_empty:
                    block_index_groups[b_idx].append({
                        "page_index": p_idx,
                        "block_index": b_idx,
                        "block": block,
                        "non_empty_spans": len(_get_non_empty_text_spans(block))
                    })
                    
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

    # First, handle empty blocks by block index
    for block_idx, empty_instances in block_index_groups.items():
        pages_with_empty = set(inst["page_index"] for inst in empty_instances)
        empty_presence_ratio = len(pages_with_empty) / total_pages
        
        if empty_presence_ratio >= page_presence_threshold:
            non_empty_counts = [inst["non_empty_spans"] for inst in empty_instances]
            
            if len(set(non_empty_counts)) <= 2 and max(non_empty_counts) <= 3:
                for inst in empty_instances:
                    to_remove[inst["page_index"]].append(inst["block_index"])

    # Second, handle blocks with same content pattern
    for pattern_key, pattern_instances in pattern_groups.items():
        pages_with_pattern = set(inst["page_index"] for inst in pattern_instances)
        pattern_presence_ratio = len(pages_with_pattern) / total_pages
        
        if pattern_presence_ratio >= page_presence_threshold:
            for inst in pattern_instances:
                if inst["block_index"] not in to_remove[inst["page_index"]]:
                    to_remove[inst["page_index"]].append(inst["block_index"])

    # Third, handle regular groups
    for key, instances in groups.items():
        block_type, qbbox, content_key = key
        pages_with = sorted(set(inst["page_index"] for inst in instances))
        presence_ratio = len(pages_with) / total_pages

        if presence_ratio >= page_presence_threshold:
            if block_type == 0:  # text
                should_remove = False
                
                texts_nodigits = [
                    _normalize_text(_concat_block_text(inst["block"]), remove_digits=True, case_sensitive=True)
                    for inst in instances
                ]

                pattern_texts = [
                    _normalize_text_pattern(_concat_block_text(inst["block"]), case_sensitive=True)
                    for inst in instances
                ]
                
                median_sim = _median_pairwise_similarity(texts_nodigits)
                pattern_sim = _median_pairwise_similarity(pattern_texts)
                
                mostly_empty_blocks = [
                    _is_mostly_empty_block(inst["block"], empty_block_threshold)
                    for inst in instances
                ]
                
                page_pattern_blocks = [
                    _has_page_pattern(_concat_block_text(inst["block"]))
                    for inst in instances
                ]
                header_footer_blocks = [
                    _is_header_footer_block(inst["block"])
                    for inst in instances
                ]
                
                if median_sim >= text_sim_threshold:
                    should_remove = True
                elif pattern_sim >= pattern_sim_threshold and (any(page_pattern_blocks) or any(header_footer_blocks)):
                    should_remove = True
                elif content_key and content_key.startswith("header_footer_") and pattern_sim >= 0.6:
                    should_remove = True
                
                if should_remove:
                    for inst in instances:
                        to_remove[inst["page_index"]].append(inst["block_index"])

            elif block_type == 1:  # image
                if content_key is not None:
                    for inst in instances:
                        to_remove[inst["page_index"]].append(inst["block_index"])

    # prune
    pruned = copy.deepcopy(parsed_doc)
    for p_idx, page in enumerate(pruned.get("pages", [])):
        blocks = page.get("blocks", [])
        remove_indices = sorted(set(to_remove.get(p_idx, [])), reverse=True)
        for ridx in remove_indices:
            if 0 <= ridx < len(blocks):
                del blocks[ridx]
        page["blocks"] = blocks

    return pruned

def parse_pdf_file(pdf_path, output_json_path, pages_to_extract):
    import pymupdf
    import json
    
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

    cleaned_output = remove_repeated_blocks(
        extracted_output,
        text_sim_threshold=0.95,
        pattern_sim_threshold=0.8,
        page_presence_threshold=0.95,
        bbox_tol=3.0,
        empty_block_threshold=0.8
    )

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_output, f, indent=4, ensure_ascii=False)

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
    
    parse_pdf_file(
        pdf_path="subcontract3.pdf",
        output_json_path="subcontract3.json",
        pages_to_extract=range(15, 34)
    )
    
    parse_pdf_file(
        pdf_path="ICMOrignal.pdf",
        output_json_path="ICMOrignal.json",
        pages_to_extract=range(4, 18)
    )
    
    parse_pdf_file(
        pdf_path="ICMNew.pdf",
        output_json_path="ICMNew.json",
        pages_to_extract=range(4, 19)
    )
    
    parse_pdf_file(
        pdf_path="ICMOriginal.pdf",
        output_json_path="ICMOriginal.json",
        pages_to_extract=range(4, 19)
    )
if __name__ == "__main__":
    main()