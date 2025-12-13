import requests

BASE_URL = "http://127.0.0.1:8000"

def main():
    # 1) Health check
    r = requests.get(f"{BASE_URL}/api/health")
    print("Health:", r.status_code, r.text)

    # 2) Start a new session (patient case)
    r = requests.post(f"{BASE_URL}/api/start-session", json={})
    print("\nStart-session:", r.status_code, r.json())
    data = r.json()
    session_id = data["session_id"]
    print("Session ID:", session_id)

    # 3) Talk to the patient (you are the doctor)
    msg = "Hello, I am your doctor. What brings you in today?"
    r = requests.post(
        f"{BASE_URL}/api/chat",
        json={"session_id": session_id, "message": msg},
    )
    print("\nChat 1:", r.status_code)
    print(r.json())

    # 4) Ask a follow-up question
    msg2 = "Can you tell me more about your symptoms and since when they started?"
    r = requests.post(
        f"{BASE_URL}/api/chat",
        json={"session_id": session_id, "message": msg2},
    )
    print("\nChat 2:", r.status_code)
    print(r.json())

    # 5) (Optional) Try a treatment suggestion to trigger evaluator
    msg3 = "I think you have a mild infection. I will prescribe you a short course of antibiotics."
    r = requests.post(
        f"{BASE_URL}/api/chat",
        json={"session_id": session_id, "message": msg3},
    )
    print("\nChat 3 (treatment):", r.status_code)
    print(r.json())

    # 6) Ask for summary/feedback
    r = requests.get(f"{BASE_URL}/api/summary/{session_id}")
    print("\nSummary:", r.status_code)
    print(r.json())

if __name__ == "__main__":
    main()
