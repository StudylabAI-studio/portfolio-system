import pandas as pd
df = pd.read_csv(r'C:\Users\teduk\Downloads\lifelogs_2026_07_28_09_39_11.csv', encoding='ms932')
print("Columns:", list(df.columns))
print("First row lifelog content:")
print(df.iloc[0]['ライフログ内容'])
