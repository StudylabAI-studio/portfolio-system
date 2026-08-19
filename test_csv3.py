import csv
with open(r'C:\Users\teduk\Downloads\evaluation_results (5).csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    first_row = next(reader)
    with open('test_out.txt', 'w', encoding='utf-8') as out:
        out.write("Keys:\n")
        for k in first_row.keys():
            out.write(f"  {k}\n")
        out.write("\nHS Career JSON sample:\n")
        out.write(first_row.get('hs_career_json', '')[:500])
