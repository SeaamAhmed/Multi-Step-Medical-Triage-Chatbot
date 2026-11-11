import os, sys
from dotenv import load_dotenv

load_dotenv()

print("Python:", sys.version.split()[0])

for pkg in ["langchain", "langchain_google_genai", "langchain_chroma",
            "langchain_huggingface", "pydantic", "fastapi", "streamlit"]:
    try:
        __import__(pkg)
        print("OK     ", pkg)
    except Exception as e:
        print("MISSING", pkg, "->", e)

key = os.getenv("GOOGLE_API_KEY")
print("GOOGLE_API_KEY loaded:", bool(key))

if key:
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(model=os.getenv("MAIN_MODEL", "gemini-3.8-flash"))
    resp = llm.invoke("Reply with the single word: ready")
    print("Gemini says:", resp.text)