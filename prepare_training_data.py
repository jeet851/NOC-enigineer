import json

def convert_dataset():
    # Load raw dataset
    try:
        with open('problem_dataset.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: problem_dataset.json not found in current directory.")
        return
    except json.JSONDecodeError as e:
        print(f"Error parsing problem_dataset.json: {e}")
        return
    
    alpaca_samples = []
    chat_samples = []
    
    for item in data:
        ft = item.get("fine_tuning_format", {})
        
        # 1. Extract Alpaca Instruction format
        inst_tuning = ft.get("instruction_tuning", {})
        if inst_tuning:
            alpaca_samples.append({
                "instruction": inst_tuning.get("instruction"),
                "input": inst_tuning.get("input"),
                "output": inst_tuning.get("output")
            })
            
        # 2. Extract Chat format
        chat = ft.get("chat_format", {})
        if chat:
            chat_samples.append(chat)
            
    # Write Alpaca format file
    with open('alpaca_dataset.json', 'w', encoding='utf-8') as f:
        json.dump(alpaca_samples, f, indent=2, ensure_ascii=False)
    print(f"[*] Created alpaca_dataset.json with {len(alpaca_samples)} instruction samples.")
    
    # Write Chat format file (.jsonl)
    with open('chat_dataset.jsonl', 'w', encoding='utf-8') as f:
        for sample in chat_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    print(f"[*] Created chat_dataset.jsonl with {len(chat_samples)} chat message samples.")

if __name__ == "__main__":
    convert_dataset()
