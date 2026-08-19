import pandas as pd
df = pd.read_csv(r'C:\Users\teduk\Documents\2026-07-28T13-01_export.csv', encoding='utf-8-sig')
print(f"Total rows: {len(df)}")
for i, row in df.iterrows():
    print(f"\nRow {i}: {row['生徒名']}")
    # print columns that are NOT nan
    for k, v in row.items():
        if pd.notna(v):
            print(f"  {k}")
