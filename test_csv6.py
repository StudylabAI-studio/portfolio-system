import csv
with open(r'C:\Users\teduk\Downloads\lifelogs_2026_07_28_09_39_11.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    print(next(reader))
