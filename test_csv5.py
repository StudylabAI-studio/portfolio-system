import csv, json
with open(r'C:\Users\teduk\Downloads\evaluation_results (5).csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        name = row.get('生徒名')
        js_str = row.get('hs_career_json', '[]')
        try:
            data = json.loads(js_str)
            facs = [d.get('faculty', '') for d in data]
            print(f"{name}: {facs}")
        except Exception as e:
            print(f"{name}: JSON Error")
