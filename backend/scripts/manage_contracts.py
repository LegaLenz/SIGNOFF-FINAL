import os

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/standard_contracts")

total = 0
for folder in sorted(os.listdir(BASE_DIR)):
    folder_path = os.path.join(BASE_DIR, folder)
    if os.path.isdir(folder_path):
        count = len([f for f in os.listdir(folder_path) if f.endswith('.txt')])
        print(f"{folder}: {count}개")
        total += count

print("---")
print(f"총합: {total}개")