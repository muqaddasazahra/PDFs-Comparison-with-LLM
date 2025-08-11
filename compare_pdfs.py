import json
import os
import re
import html
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def load_json(file_path):
    """Load JSON data from file with error handling"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading {file_path}: {str(e)}")
        return None

def extract_json_from_response(response_text):
    """
    Extract JSON from LLM response that may contain Markdown code blocks or extra text
    """
    if isinstance(response_text, dict):
        return response_text
    
    # Try to find JSON in Markdown code blocks
    json_match = re.search(r'```(?:json)?\n(.*?)\n```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # If no code block found, try to extract JSON from the entire response
        json_str = response_text
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Try to find the first valid JSON object in the string
        json_objects = re.findall(r'\{.*\}', json_str, re.DOTALL)
        for obj in json_objects:
            try:
                return json.loads(obj)
            except json.JSONDecodeError:
                continue
        return None

def compare_with_groq(data1, data2, category, groq_client, model="deepseek-r1-distill-llama-70b"):
    """Compare document elements using Groq API"""
    prompt = f"""
    You are an expert document comparison tool. Compare two sets of {category} data from two PDFs and identify:
    1. Added elements (present in the second set but not the first)
    2. Removed elements (present in the first set but not the second)
    3. Font changes (same text but different font or size)
    4. Position changes (same text but different bounding box coordinates)
    
    Return ONLY valid JSON in this exact format:
    {{
        "added": [],
        "removed": [],
        "font_changes": [],
        "position_changes": []
    }}
    """
 
    comparison_data = {
        "original_data": data1,
        "new_data": data2
    }
    
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise document comparison assistant. Provide ONLY valid JSON output."},
                {"role": "user", "content": prompt + json.dumps(comparison_data, indent=2)}
            ],
            temperature=0,
            max_tokens=4096
        )
        
        result_text = response.choices[0].message.content.strip()
        result = extract_json_from_response(result_text)
        
        if not result:
            print(f"Warning: Could not extract valid JSON for {category} from LLM response")
            result = {
                "added": [],
                "removed": [],
                "font_changes": [],
                "position_changes": []
            }
            
        return result
        
    except Exception as e:
        print(f"Error comparing {category}: {str(e)}")
        return {
            "added": [],
            "removed": [],
            "font_changes": [],
            "position_changes": []
        }

def compare_tables_with_groq(tables1, tables2, groq_client, model="llama-3.1-8b-instant"):
    """Compare tables using Groq API"""
    prompt = """
    Compare two sets of table data from two PDFs and identify:
    1. Added tables (present in the second set but not the first)
    2. Removed tables (present in the first set but not the second)
    
    Return ONLY valid JSON in this exact format:
    {
        "added": [],
        "removed": []
    }
    """
    
    comparison_data = {
        "original_tables": tables1,
        "new_tables": tables2
    }
    
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise document comparison assistant. Provide ONLY valid JSON output."},
                {"role": "user", "content": prompt + json.dumps(comparison_data, indent=2)}
            ],
            temperature=0,
            max_tokens=4096
        )
        
        result_text = response.choices[0].message.content.strip()
        result = extract_json_from_response(result_text)
        
        if not result:
            print("Warning: Could not extract valid JSON for tables from LLM response")
            result = {"added": [], "removed": []}
            
        return result
        
    except Exception as e:
        print(f"Error comparing tables: {str(e)}")
        return {"added": [], "removed": []}

def generate_html_report(comparison_results, output_file):
    """Generate a well-formatted HTML report from comparison results"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # HTML template with CSS styling
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PDF Comparison Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1, h2, h3 {{
                color: #2c3e50;
            }}
            .report-header {{
                background-color: #f8f9fa;
                padding: 20px;
                border-radius: 5px;
                margin-bottom: 30px;
            }}
            .section {{
                margin-bottom: 30px;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
            }}
            .changes-container {{
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }}
            .change-type {{
                flex: 1;
                min-width: 300px;
                border: 1px solid #eee;
                border-radius: 5px;
                padding: 15px;
            }}
            .added {{
                background-color: #e8f5e9;
            }}
            .removed {{
                background-color: #ffebee;
            }}
            .modified {{
                background-color: #e3f2fd;
            }}
            .item {{
                margin-bottom: 10px;
                padding: 10px;
                border-left: 4px solid #2c3e50;
                background-color: white;
            }}
            .page-indicator {{
                font-weight: bold;
                color: #7f8c8d;
            }}
            .text-content {{
                margin: 5px 0;
            }}
            .metadata {{
                font-size: 0.9em;
                color: #7f8c8d;
            }}
            .summary {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .summary-item {{
                display: inline-block;
                margin-right: 20px;
                font-size: 1.1em;
            }}
            .count {{
                font-weight: bold;
                color: #2c3e50;
            }}
        </style>
    </head>
    <body>
        <div class="report-header">
            <h1>PDF Comparison Report</h1>
            <p>Generated on: {timestamp}</p>
        </div>
    """
    
    # Generate summary statistics
    summary_stats = {
        "headings": {
            "added": len(comparison_results.get("headings", {}).get("added", [])),
            "removed": len(comparison_results.get("headings", {}).get("removed", [])),
            "font_changes": len(comparison_results.get("headings", {}).get("font_changes", [])),
            "position_changes": len(comparison_results.get("headings", {}).get("position_changes", []))
        },
        "subheadings": {
            "added": len(comparison_results.get("subheadings", {}).get("added", [])),
            "removed": len(comparison_results.get("subheadings", {}).get("removed", [])),
            "font_changes": len(comparison_results.get("subheadings", {}).get("font_changes", [])),
            "position_changes": len(comparison_results.get("subheadings", {}).get("position_changes", []))
        },
        "body": {
            "added": len(comparison_results.get("body", {}).get("added", [])),
            "removed": len(comparison_results.get("body", {}).get("removed", [])),
            "font_changes": len(comparison_results.get("body", {}).get("font_changes", [])),
            "position_changes": len(comparison_results.get("body", {}).get("position_changes", []))
        },
        "tables": {
            "added": len(comparison_results.get("tables", {}).get("added", [])),
            "removed": len(comparison_results.get("tables", {}).get("removed", []))
        }
        
    }
    
    # Add summary section
    html_template += """
    <div class="summary">
        <h2>Summary of Changes</h2>
        <div class="changes-container">
            <div class="change-type">
                <h3>Headings</h3>
                <p><span class="summary-item">Added: <span class="count">""" + str(summary_stats["headings"]["added"]) + """</span></span></p>
                <p><span class="summary-item">Removed: <span class="count">""" + str(summary_stats["headings"]["removed"]) + """</span></span></p>
                <p><span class="summary-item">Font Changes: <span class="count">""" + str(summary_stats["headings"]["font_changes"]) + """</span></span></p>
                <p><span class="summary-item">Position Changes: <span class="count">""" + str(summary_stats["headings"]["position_changes"]) + """</span></span></p>
            </div>
            <div class="change-type">
                <h3>Subheadings</h3>
                <p><span class="summary-item">Added: <span class="count">""" + str(summary_stats["subheadings"]["added"]) + """</span></span></p>
                <p><span class="summary-item">Removed: <span class="count">""" + str(summary_stats["subheadings"]["removed"]) + """</span></span></p>
                <p><span class="summary-item">Font Changes: <span class="count">""" + str(summary_stats["subheadings"]["font_changes"]) + """</span></span></p>
                <p><span class="summary-item">Position Changes: <span class="count">""" + str(summary_stats["subheadings"]["position_changes"]) + """</span></span></p>
            </div>
            <div class="change-type">
                <h3>Body</h3>
                <p><span class="summary-item">Added: <span class="count">""" + str(summary_stats["body"]["added"]) + """</span></span></p>
                <p><span class="summary-item">Removed: <span class="count">""" + str(summary_stats["body"]["removed"]) + """</span></span></p>
                <p><span class="summary-item">Font Changes: <span class="count">""" + str(summary_stats["body"]["font_changes"]) + """</span></span></p>
                <p><span class="summary-item">Position Changes: <span class="count">""" + str(summary_stats["body"]["position_changes"]) + """</span></span></p>
            </div>

            <div class="change-type">
                <h3>Tables</h3>
                <p><span class="summary-item">Added: <span class="count">""" + str(summary_stats["tables"]["added"]) + """</span></span></p>
                <p><span class="summary-item">Removed: <span class="count">""" + str(summary_stats["tables"]["removed"]) + """</span></span></p>
            </div>
        </div>
    </div>
    """
    
    for category in ["headings", "subheadings", "body", "tables"]:
        html_template += f"""
        <div class="section">
            <h2>{category.capitalize()} Changes</h2>
            <div class="changes-container">
        """
        
        if category == "tables":
            for change_type in ["added", "removed"]:
                changes = comparison_results.get(category, {}).get(change_type, [])
                if changes:
                    html_template += f"""
                    <div class="change-type {'added' if change_type == 'added' else 'removed'}">
                        <h3>{change_type.capitalize()} Tables</h3>
                    """
                    for table in changes:
                        html_template += f"""
                        <div class="item">
                            <div class="page-indicator">Page {table.get('page', 'N/A')}</div>
                            <div class="table-content">
                                <pre>{html.escape(json.dumps(table.get('tables', []), indent=2))}</pre>
                            </div>
                        </div>
                        """
                    html_template += "</div>"
        else:
            for change_type in ["added", "removed", "font_changes", "position_changes"]:
                changes = comparison_results.get(category, {}).get(change_type, [])
                if changes:
                    html_template += f"""
                    <div class="change-type {'added' if change_type == 'added' else 'removed' if change_type == 'removed' else 'modified'}">
                        <h3>{' '.join(change_type.split('_')).title()}</h3>
                    """
                    for item in changes:
                        html_template += """
                        <div class="item">
                            <div class="page-indicator">Page """ + str(item.get('page', 'N/A')) + """</div>
                            <div class="text-content">""" + html.escape(str(item.get('text', ''))) + """</div>
                        """
                        if change_type == "font_changes":
                            html_template += """
                            <div class="metadata">
                                Font changed from """ + html.escape(f"{item.get('old_font', '')} ({item.get('old_size', '')}pt)") + """
                                to """ + html.escape(f"{item.get('new_font', '')} ({item.get('new_size', '')}pt)") + """
                            </div>
                            """
                        elif change_type == "position_changes":
                            html_template += """
                            <div class="metadata">
                                Position changed from """ + html.escape(str(item.get('old_bbox', []))) + """
                                to """ + html.escape(str(item.get('new_bbox', []))) + """
                            </div>
                            """
                        else:
                            html_template += """
                            <div class="metadata">
                                Font: """ + html.escape(str(item.get('font', 'N/A'))) + """ (""" + str(item.get('size', 'N/A')) + """pt)<br>
                                Bounding Box: """ + html.escape(str(item.get('bbox', []))) + """
                            </div>
                            """
                        html_template += "</div>"
                    html_template += "</div>"
        
        html_template += """
            </div>
        </div>
        """

    
    # Close HTML
    html_template += """
    </body>
    </html>
    """
    
    # Save HTML file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_template)
    
    return html_template

def compare_pdfs(pdf1_dir, pdf2_dir, json_output_file, html_output_file, groq_api_key):
    """Main comparison function"""
    groq_client = Groq(api_key=groq_api_key)
    categories = ["headings", "subheadings", "body" ,"tables"]  # Only these three categories
    all_differences = {}
    
    for category in categories:
        file1 = os.path.join(pdf1_dir, f"ICMOrignal_{category}.json")
        file2 = os.path.join(pdf2_dir, f"ICMNew_{category}.json")
        
        if os.path.exists(file1) and os.path.exists(file2):
            data1 = load_json(file1)
            data2 = load_json(file2)
            
            if data1 is not None and data2 is not None:
                if category == "tables":
                    all_differences[category] = compare_tables_with_groq(data1, data2, groq_client)
                else:
                    all_differences[category] = compare_with_groq(data1, data2, category, groq_client)
    
    # Save JSON results
    with open(json_output_file, "w", encoding="utf-8") as f:
        json.dump(all_differences, f, indent=4, ensure_ascii=False)
    
    # Generate HTML report
    html_report = generate_html_report(all_differences, html_output_file)
    
    return all_differences, html_report

if __name__ == "__main__":
    pdf1_dir = "parsed_output"
    pdf2_dir = "parsed_output"
    json_output_file = "comparison_results.json"
    html_output_file = "comparison_report.html"
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")
    
    differences, report = compare_pdfs(
        pdf1_dir, pdf2_dir, 
        json_output_file, html_output_file, 
        groq_api_key
    )
    
    print(f"Comparison complete. Results saved to {json_output_file} and {html_output_file}")