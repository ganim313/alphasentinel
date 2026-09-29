import sys
import os
from datetime import date
from jugaad_data.nse import bhavcopy_save
import pandas as pd

def main():
    try:
        trade_date = date(2024, 8, 30) # A recent friday
        file_path = bhavcopy_save(trade_date, ".")
        if file_path and os.path.exists(file_path):
            df = pd.read_csv(file_path)
            print("Columns in raw bhavcopy:")
            print(df.columns.tolist())
            print(df.head())
            os.remove(file_path)
        else:
            print("Failed to download bhavcopy.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
