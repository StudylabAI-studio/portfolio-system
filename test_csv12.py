import pandas as pd
df = pd.read_csv(r'C:\Users\teduk\Downloads\lifelogs_2026_07_28_09_39_11.csv', encoding='ms932')
with open('out12.txt', 'w', encoding='utf-8') as f:
    for user_id, group in df.groupby('ユーザーID'):
        f.write(f"--- User: {user_id} ---\n")
        for i, row in group.iterrows():
            f.write(str(row['ライフログ内容']).replace('\n', ' ')[:100] + "\n")
