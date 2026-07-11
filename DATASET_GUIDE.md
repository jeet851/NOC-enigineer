# AIOps Agent Training Dataset Guide

This guide explains the structure of the training dataset provided in [`problem_dataset.json`](file:///c:/Users/gawan/OneDrive/Desktop/project/problem_dataset.json) and provides code and instructions for using it to train and fine-tune your own AI agents.

---

## 1. Dataset Schema

Each entry in the dataset represents a complete, high-fidelity operations incident simulation. The schema contains the following fields:

| Field Name | Type | Description |
|---|---|---|
| `id` | `string` | Unique identifier for the scenario (e.g. `AIOPS-001`). |
| `persona` | `string` | The AIOps agent persona key (e.g. `net_genius`, `lin_admin`, `sec_analyst`, `cloud_eng`, `win_admin`, `noc_eng`, `doc_specialist`, `auto_eng`). |
| `category` | `string` | The operational category / subsystem (e.g. `BGP Routing`, `Kubernetes DNS`). |
| `problem_statement` | `string` | A description of the issue as reported by a user or monitoring tool. |
| `initial_telemetry` | `object` | Raw metric alerts, host names, and alert sources mimicking enterprise monitoring (Zabbix, SolarWinds, Datadog). |
| `diagnostics` | `object` | The diagnostic commands executed by the agent and the simulated terminal outputs containing clues. |
| `solution` | `object` | Step-by-step repair actions along with code-based fixes (e.g. Cisco commands, PowerShell scripts, Bash commands, YAML playbooks, IAM JSON policies). |
| `rca` | `object` | A post-incident Root Cause Analysis report outlining the root cause, immediate fix, and prevention plans. |
| `fine_tuning_format` | `object` | Pre-formatted variants of the scenario ready for machine learning ingestion: |
| | `↳ instruction_tuning` | Alpaca-style format (`instruction`, `input`, `output`). Ideal for base models. |
| | `↳ chat_format` | OpenAI/Gemini message lists (`messages` with `role` and `content`). Ideal for chat models. |

---

## 2. Converting the Dataset for Training

To run fine-tuning, you must convert the JSON structure into the format expected by your training pipeline (typically JSON Lines / `.jsonl`).

Below is a Python utility script ([`prepare_training_data.py`](file:///c:/Users/gawan/OneDrive/Desktop/project/prepare_training_data.py)) that reads `problem_dataset.json` and generates training files:
1. **`alpaca_dataset.json`**: For standard instruction-tuning.
2. **`chat_dataset.jsonl`**: For chat-based fine-tuning (compatible with Llama-Factory, OpenAI, and Hugging Face SFTTrainer).

```python
import json

def convert_dataset():
    # Load raw dataset
    with open('problem_dataset.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
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
    print(f"✓ Created alpaca_dataset.json with {len(alpaca_samples)} instruction samples.")
    
    # Write Chat format file (.jsonl)
    with open('chat_dataset.jsonl', 'w', encoding='utf-8') as f:
        for sample in chat_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    print(f"✓ Created chat_dataset.jsonl with {len(chat_samples)} chat message samples.")

if __name__ == "__main__":
    convert_dataset()
```

Save and run this script using `python prepare_training_data.py`.

---

## 3. Training/Fine-Tuning Methodologies

### Method A: Hugging Face SFTTrainer (PEFT/QLoRA)
If you are fine-tuning an open-source model (like Llama-3, Mistral, or Qwen) on your own hardware, use the Hugging Face `trl` library.

**Sample training script snippet:**
```python
from datasets import load_dataset
from trl import SFTTrainer
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig

model_id = "meta-llama/Meta-Llama-3-8B-Instruct"
model = AutoModelForCausalLM.from_pretrained(model_id, load_in_8bit=True, device_map="auto")
tokenizer = AutoTokenizer.from_pretrained(model_id)

# Load the generated alpaca dataset
dataset = load_dataset("json", data_files="alpaca_dataset.json")

peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

training_args = TrainingArguments(
    output_dir="./aiops_agent_model",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    logging_steps=1,
    num_train_epochs=3,
    save_strategy="epoch",
)

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset["train"],
    peft_config=peft_config,
    dataset_text_field="text",  # Or write a custom template formatting function
    max_seq_length=1024,
    args=training_args,
)

trainer.train()
```

### Method B: OpenAI Fine-Tuning API
If you are training a proprietary OpenAI model (like `gpt-4o-mini` or `gpt-3.5-turbo`), upload `chat_dataset.jsonl` directly to the OpenAI Fine-Tuning platform:

1. **Upload your file**:
   ```bash
   curl https://api.openai.com/v1/files \
     -H "Authorization: Bearer $OPENAI_API_KEY" \
     -F "purpose=fine-tune" \
     -F "file=@chat_dataset.jsonl"
   ```
2. **Retrieve File ID** (e.g., `file-xxxxx`).
3. **Start Fine-Tuning Job**:
   ```bash
   curl https://api.openai.com/v1/fine_tuning/jobs \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $OPENAI_API_KEY" \
     -d '{
       "training_file": "file-xxxxx",
       "model": "gpt-4o-mini-2024-07-18"
     }'
   ```
