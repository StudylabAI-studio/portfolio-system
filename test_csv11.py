import pandas as pd
df = pd.read_csv(r'C:\Users\teduk\Downloads\lifelogs_2026_07_28_09_39_11.csv', encoding='ms932')
first_user_id = df.iloc[0]['ユーザーID']
user_df = df[df['ユーザーID'] == first_user_id]
with open('out11.txt', 'w', encoding='utf-8') as f:
    for i, row in user_df.iterrows():
        f.write(f"--- LOG {i} ---\n")
        f.write(str(row['ライフログ内容']) + "\n")
