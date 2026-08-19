import csv
with open(r'C:\Users\teduk\Downloads\evaluation_results (5).csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        print(f"Row {i}: Name={row.get('生徒名')}, Score={row.get('総合評価')}")
        faculties = []
        if 'hs_career_json' in row:
            import json
            try:
                data = json.loads(row['hs_career_json'])
                for item in data:
                    faculties.append(item.get('faculty', ''))
            except Exception as e:
                faculties.append(f"JSON Error: {e}")
        print(f"  Faculties: {faculties}")
