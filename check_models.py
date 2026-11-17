# check_models.py
import time
from dotenv import load_dotenv
load_dotenv()
from langchain_google_genai import ChatGoogleGenerativeAI

for m in ["gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash",
          "gemini-3.5-flash-lite", "gemini-2.5-flash-lite"]:
    t = time.time()
    try:
        llm = ChatGoogleGenerativeAI(model=m, timeout=30, max_retries=0)
        out = llm.invoke("Reply with the single word: ready").text
        print(f"OK    {m:25s} {time.time() - t:4.1f}s  {out.strip()[:20]}")
    except Exception as e:
        print(f"FAIL  {m:25s} {time.time() - t:4.1f}s  {str(e)[:70]}")