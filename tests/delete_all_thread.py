import requests

BASE_URL = "http://127.0.0.1:2024"

def get_all_threads():
    resp = requests.post(f"{BASE_URL}/threads/search", json={})
    resp.raise_for_status()
    data = resp.json()
    # Giả sử trả về list thread, mỗi thread có 'thread_id'
    return [t["thread_id"] for t in data if "thread_id" in t]

def delete_thread(thread_id):
    resp = requests.delete(f"{BASE_URL}/threads/{thread_id}")
    if resp.status_code == 204:
        print(f"Deleted thread {thread_id}")
    else:
        print(f"Failed to delete {thread_id}: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    threads = get_all_threads()
    print(f"Found {len(threads)} threads.")
    for tid in threads:
        delete_thread(tid)