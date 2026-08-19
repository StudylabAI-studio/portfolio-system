import csv
with open(r'C:\Users\teduk\Downloads\lifelogs_2026_07_28_09_39_11.csv', 'r', encoding='ms932') as f:
    reader = csv.reader(f)
    header = next(reader)
    with open('out8.txt', 'w', encoding='utf-8') as out:
        out.write(str(header))
