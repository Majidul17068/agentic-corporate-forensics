import os
import pandas as pd

SOURCE_PATH = "/Users/majidmurad/Desktop/research-lab/untitled folder/SAML-D.csv"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "SAML-D-subset.csv")

def main():
    if not os.path.exists(SOURCE_PATH):
        print(f"[Error] Could not find the dataset at {SOURCE_PATH}")
        return

    print("Reading dataset... (this may take a few seconds as the file is large)")
    df = pd.read_csv(SOURCE_PATH)
    print(f"Original dataset shape: {df.shape}")

    laundering_df = df[df['Is_laundering'] == 1]
    print(f"Total laundering rows found: {len(laundering_df)}")

    sample_laundering = laundering_df.head(20)
    
    suspicious_accounts = set(sample_laundering['Sender_account'].unique()).union(
        set(sample_laundering['Receiver_account'].unique())
    )
    print(f"Identified {len(suspicious_accounts)} unique target accounts involved in laundering networks.")

    subset_df = df[
        df['Sender_account'].isin(suspicious_accounts) | 
        df['Receiver_account'].isin(suspicious_accounts)
    ]
    
    if len(subset_df) > 1000:
        subset_df = subset_df.head(1000)

    print(f"Generated subset shape: {subset_df.shape}")
    print(f"Laundering transactions in subset: {subset_df['Is_laundering'].sum()}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    subset_df.to_csv(OUTPUT_PATH, index=False)
    print(f"Lightweight subset successfully saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
