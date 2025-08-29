import json
import requests
import time
from bs4 import BeautifulSoup

def handler(event, context):
    try:
        data = json.loads(event.get("body") or "{}")
        jsessionid = data.get("jsessionid")
        username = data.get("username")
        problem = data.get("problem")
        language = data.get("language")
        source = data.get("source")

        if not all([jsessionid, username, problem, language, source]):
            return {
                "statusCode": 400,
                "headers":{"Content-Type":"application/json"},
                "body": json.dumps({"error":"缺少参数"})
            }

        session = requests.Session()
        session.cookies.set("JSESSIONID", jsessionid, domain="codeforces.com")

        # Step 1: 获取提交页面，带 CSRF token
        submit_page = session.get("https://codeforces.com/problemset/submit")
        soup = BeautifulSoup(submit_page.text, "html.parser")
        csrf = soup.find("input", {"name":"csrf_token"})["value"]

        # Step 2: 提交代码
        submit_data = {
            "csrf_token": csrf,
            "action": "submitSolutionFormSubmitted",
            "submittedProblemIndex": problem.split("/")[1], # e.g., 1/A -> A
            "programTypeId": language,
            "source": source,
        }
        session.post("https://codeforces.com/problemset/submit", data=submit_data)

        # Step 3: 轮询状态
        status_url = f"https://codeforces.com/submissions/{username}"
        verdict = ""
        runid = ""
        interval = 1.0
        max_wait = 30.0
        waited = 0.0

        while waited < max_wait:
            r = session.get(status_url)
            s = BeautifulSoup(r.text, "html.parser")
            table = s.find("table", {"class":"status-frame-datatable"})
            if table:
                first_row = table.find("tr")
                if first_row:
                    cells = first_row.find_all("td")
                    runid = cells[0].text.strip()
                    verdict = cells[5].text.strip()
                    if verdict not in ["In queue", "Running"]:
                        break
            time.sleep(interval)
            waited += interval
            interval = min(interval*1.5, 5.0)

        return {
            "statusCode": 200,
            "headers":{"Content-Type":"application/json"},
            "body": json.dumps({
                "runid": runid,
                "verdict": verdict
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers":{"Content-Type":"application/json"},
            "body": json.dumps({"error": str(e)})
        }
