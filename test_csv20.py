import pandas as pd
df = pd.read_csv(r'C:\Users\teduk\Downloads\evaluation_results (9).csv', encoding='utf-8-sig')
with open('out20.txt', 'w', encoding='utf-8') as f:
    f.write(f"Columns: {list(df.columns)}\n\n")
    for i, row in df.iterrows():
        f.write(f"Row {i}: {row.get('生徒名', 'UNKNOWN')}\n")
        for k, v in row.items():
            if pd.notna(v):
                f.write(f"  {k}: {v}\n")
        f.write("\n")
