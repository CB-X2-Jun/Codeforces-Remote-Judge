import json
import requests
from bs4 import BeautifulSoup
import time

def handler(event, context):
    try:
        data = json.loads(event['body'])
        jsessionid = data.get('jsessionid')
        problem = data.get('problem')
        language = data.get('language')
        source = data.get('source')

        if not all([jsessionid, problem, language, source]):
            return {
                "statusCode": 400,
                "headers": {"Content-Type":"application/json"},
                "body": json.dumps({"error":"缺少参数"})
            }

        session = requests.Session()
        session.cookies.set('JSESSIONID', jsessionid, domain='.codeforces.com')

        submit_url = "https://codeforces.com/problemset/submit"
        payload = {
            "submittedProblemIndex": problem,
            "programTypeId": language,
            "source": source
        }

        headers = {
            "User-Agent":"Mozilla/5.0",
            "Referer": submit_url
        }

        r = session.post(submit_url, data=payload, headers=headers)
        if r.status_code != 200:
            return {
                "statusCode": 500,
                "headers": {"Content-Type":"application/json"},
                "body": json.dumps({"error":"提交失败"})
            }

        # 获取提交ID（runID）
        # Codeforces 状态页
        status_url = f"https://codeforces.com/submissions"
        runid = None
        for _ in range(10):
            sr = session.get(status_url, headers=headers)
            if sr.status_code != 200:
                continue
            sr.encoding = 'utf-8'
            soup = BeautifulSoup(sr.text, 'html.parser')
            rows = soup.select('table.status-frame-datatable tr')
            for row in rows[1:]:
                cols = row.find_all('td')
                if len(cols) < 7:
                    continue
                p_index = cols[3].get_text(strip=True)
                if p_index == problem:
                    runid = cols[0].get_text(strip=True)
                    verdict = cols[5].get_text(strip=True)
                    break
            if runid:
                break
            time.sleep(1)

        if not runid:
            return {
                "statusCode": 500,
                "headers": {"Content-Type":"application/json"},
                "body": json.dumps({"error":"未找到RunID"})
            }

        # 轮询获取判定状态
        final_verdict = None
        for _ in range(30):
            sr = session.get(status_url, headers=headers)
            sr.encoding = 'utf-8'
            soup = BeautifulSoup(sr.text, 'html.parser')
            rows = soup.select('table.status-frame-datatable tr')
            for row in rows[1:]:
                cols = row.find_all('td')
                if len(cols) < 7:
                    continue
                rid = cols[0].get_text(strip=True)
                if rid == runid:
                    final_verdict = cols[5].get_text(strip=True)
                    time_used = cols[3].get_text(strip=True)
                    memory_used = cols[4].get_text(strip=True)
                    break
            if final_verdict and final_verdict not in ['Running', 'In queue']:
                break
            time.sleep(1)

        return {
            "statusCode": 200,
            "headers": {"Content-Type":"application/json"},
            "body": json.dumps({
                "runid": runid,
                "verdict": final_verdict,
                "time": time_used if 'time_used' in locals() else '',
                "memory": memory_used if 'memory_used' in locals() else ''
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type":"application/json"},
            "body": json.dumps({"error": str(e)})
        }
