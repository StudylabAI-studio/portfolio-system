import pandas as pd
try:
    df = pd.read_csv(r'C:\Users\teduk\Documents\2026-07-28T13-01_export.csv', encoding='utf-8-sig')
except UnicodeDecodeError:
    df = pd.read_csv(r'C:\Users\teduk\Documents\2026-07-28T13-01_export.csv', encoding='ms932')
with open('out13.txt', 'w', encoding='utf-8') as f:
    f.write("Columns: " + str(list(df.columns)) + "\n")
    f.write("Preview of first row:\n")
    for k, v in df.iloc[0].items():
        f.write(f"  {k}: {v}\n")
