import pandas as pd
df = pd.read_csv(r'C:\Users\teduk\Documents\2026-07-28T13-01_export.csv', encoding='utf-8-sig')
with open('out15.txt', 'w', encoding='utf-8') as f:
    f.write(f"Total rows: {len(df)}\n")
    for i, row in df.iterrows():
        f.write(f"\nRow {i}: {row['生徒名']}\n")
        for k, v in row.items():
            if pd.notna(v):
                f.write(f"  {k}\n")
