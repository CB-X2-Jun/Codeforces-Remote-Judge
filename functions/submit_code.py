import json
import requests
from bs4 import BeautifulSoup

CF_BASE = "https://codeforces.com"

def handler(event, context):
    try:
        body = json.loads(event['body'])
        jsessionid = body.get("jsessionid")
        username = body.get("username")
        problem_id = body.get("problem_id")
        language_id = body.get("language_id")
        source_code = body.get("source_code")
        if not all([jsessionid, username, problem_id, language_id, source_code]):
            return {"statusCode":200,"body":json.dumps({"error":"参数不完整"})}

        session = requests.Session()
        session.cookies.set("JSESSIONID", jsessionid, domain=".codeforces.com")
        # 提交
        submit_url = f"{CF_BASE}/problemset/submit"
        resp = session.get(submit_url)
        if "login" in resp.url:
            return {"statusCode":200,"body":json.dumps({"error":"JSESSIONID无效或未登录"})}

        problem_parts = problem_id.strip().upper()
        contest_id = ''.join(filter(str.isdigit, problem_parts))
        index = ''.join(filter(str.isalpha, problem_parts))
        data = {
            "action": "submitSolutionFormSubmitted",
            "submittedProblemCode": f"{contest_id}{index}",
            "programTypeId": language_id,
            "source": source_code,
            "csrf_token": BeautifulSoup(resp.text,"html.parser").find("input",{"name":"csrf_token"})["value"]
        }
        post_resp = session.post(submit_url, data=data)
        if post_resp.status_code != 200:
            return {"statusCode":200,"body":json.dumps({"error":"提交失败"})}

        # 获取最新提交
        status_url = f"{CF_BASE}/submissions/{username}"
        sresp = session.get(status_url)
        soup = BeautifulSoup(sresp.text,"html.parser")
        table = soup.find("table", class_="status-frame-datatable")
        first_row = table.find_all("tr")[1]
        cells = first_row.find_all("td")
        run_id = cells[0].text.strip()
        verdict = cells[5].text.strip()
        time = cells[6].text.strip()
        memory = cells[7].text.strip()

        result = {
            "run_id": run_id,
            "verdict": verdict,
            "time": time,
            "memory": memory
        }
        return {"statusCode":200, "body": json.dumps(result)}

    except Exception as e:
        return {"statusCode":200,"body": json.dumps({"error": str(e)})}
