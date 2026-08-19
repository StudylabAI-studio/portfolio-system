import csv
with open(r'C:\Users\teduk\Downloads\evaluation_results (5).csv', 'r', encoding='shift_jis') as f:
    reader = csv.DictReader(f)
    first_row = next(reader)
    print("Keys:")
    for k in first_row.keys():
        print(f"  {k}")
    print("\nHS Career JSON sample:")
    print(first_row.get('hs_career_json', '')[:500])
