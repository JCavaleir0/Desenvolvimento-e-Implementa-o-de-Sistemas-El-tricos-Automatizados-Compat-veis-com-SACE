from LLM import run_analysis
import time
from datetime import datetime

INTERVALO = 30

while True:
    print(f"\n[{datetime.now()}] LOOP ATIVO")

    try:
        run_analysis()
    except Exception as e:
        print(f"Erro: {e}")

    print("Waiting...\n")
    time.sleep(INTERVALO)

    
 
""" from LLM1 import run_analysis
import time
from datetime import datetime

INTERVALO = 60

while True:
    print(f"\n[{datetime.now()}] LOOP ATIVO")

    try:
        run_analysis()
    except Exception as e:
        print(f"Erro: {e}")

    print("Waiting...\n")
    time.sleep(INTERVALO)  """