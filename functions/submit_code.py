import json
import requests
from bs4 import BeautifulSoup

CF_BASE = "https://codeforces.com"

def handler(event, context):
    try:
        body = json.loads(event['body'])
        jsessionid = body.get('jsessionid')
        username = body.get('username')
        problem_id = body.get('problem_id')
        language = body.get('language', '42')
        source = body.get('source', '')

        if not (jsessionid and username and problem_id and source):
            return {"statusCode": 400, "body": json.dumps({"error": "缺少必要参数"})}

        session = requests.Session()
        session.cookies.set('JSESSIONID', jsessionid, domain=".codeforces.com")
        session.headers.update({'User-Agent': 'Mozilla/5.0'})

        submit_page = session.get(f"{CF_BASE}/problemset/submit")
        if "Login" in submit_page.text or "csrf_token" not in submit_page.text:
            return {"statusCode": 401, "body": json.dumps({"error": "JSESSIONID 无效或未登录"})}

        soup = BeautifulSoup(submit_page.text, 'html.parser')
        token_input = soup.find('input', {'name': 'csrf_token'})
        if not token_input:
            return {"statusCode": 500, "body": json.dumps({"error": "无法获取 csrf_token"})}
        csrf_token = token_input['value']

        data = {
            "csrf_token": csrf_token,
            "action": "submitSolutionFormSubmitted",
            "submittedProblemCode": problem_id,
            "programTypeId": language,
            "source": source
        }
        submit_resp = session.post(f"{CF_BASE}/problemset/submit", data=data)
        if submit_resp.status_code != 200:
            return {"statusCode": 500, "body": json.dumps({"error": f"提交失败，HTTP {submit_resp.status_code}"})}

        status_resp = session.get(f"{CF_BASE}/submissions/{username}")
        soup = BeautifulSoup(status_resp.text, 'html.parser')
        row = soup.find('table', class_='status-frame-datatable').find('tr', class_='')
        if not row:
            return {"statusCode": 500, "body": json.dumps({"error": "无法解析状态行"})}

        cols = row.find_all('td')
        runid = cols[0].get_text(strip=True)
        problem = cols[3].get_text(strip=True)
        verdict = cols[5].get_text(strip=True)
        time_used = cols[6].get_text(strip=True)
        memory_used = cols[7].get_text(strip=True)

        return {"statusCode": 200, "body": json.dumps({
            "runid": runid,
            "problem": problem,
            "verdict": verdict,
            "time": time_used,
            "memory": memory_used
        })}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
