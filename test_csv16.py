import pandas as pd
df = pd.read_csv(r'C:\Users\teduk\Documents\2026-07-28T13-01_export.csv', encoding='utf-8-sig')
print("Row 3 values:")
for k, v in df.iloc[3].items():
    print(f"{k}: {v}")
