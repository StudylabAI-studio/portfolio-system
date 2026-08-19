import pandas as pd
df = pd.read_csv(r'C:\Users\teduk\Downloads\lifelogs_2026_07_28_09_39_11.csv', encoding='ms932')
with open('out10.txt', 'w', encoding='utf-8') as f:
    f.write("Columns: " + str(list(df.columns)) + "\n")
    f.write("First row lifelog content:\n")
    f.write(str(df.iloc[0]['ライフログ内容']))
