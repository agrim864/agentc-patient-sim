from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

print("GOOGLE_API_KEY present?", bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")))

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.4,
    max_retries=2,
)

prompt = (
    "You are a virtual patient. A doctor says: "
    "'I get chest pain when I walk upstairs.' "
    "Reply in 2 short sentences as the patient describing your symptoms."
)

resp = llm.invoke([("human", prompt)])
print("Type of resp:", type(resp))

if hasattr(resp, "text"):
    print("Text:", resp.text)
else:
    print("Content:", resp.content)
