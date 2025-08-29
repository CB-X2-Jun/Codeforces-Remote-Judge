import requests
from bs4 import BeautifulSoup
import time
import json

def handler(event, context):
    body = json.loads(event['body'])
    jsessionid = body['jsessionid']
    username = body['username']
    problem_id = body['problem_id']
    language_id = body['language']
    source_code = body['source']

    session = requests.Session()
    session.cookies.set('JSESSIONID', jsessionid, domain='codeforces.com')

    # 获取 csrf_token
    submit_page = session.get('https://codeforces.com/problemset/submit')
    soup = BeautifulSoup(submit_page.text, 'html.parser')
    csrf_tag = soup.find('input', {'name':'csrf_token'})
    if not csrf_tag:
        return {"statusCode": 400, "body": json.dumps({"error":"无法获取 csrf_token"})}
    csrf_token = csrf_tag['value']

    # 分解题号
    contest_id, problem_index = '', ''
    if problem_id[:-1].isdigit() and problem_id[-1].isalpha():
        contest_id = problem_id[:-1]
        problem_index = problem_id[-1].upper()

    data = {
        'csrf_token': csrf_token,
        'action': 'submitSolutionFormSubmitted',
        'submittedProblemIndex': problem_index,
        'programTypeId': language_id,
        'source': source_code,
        'tabSize': '4',
        'contestId': contest_id
    }

    r = session.post('https://codeforces.com/problemset/submit', data=data)
    if r.status_code != 200:
        return {"statusCode": 400, "body": json.dumps({"error":"提交失败"})}

    # 轮询状态
    runid = ''
    verdict = ''
    use_time = ''
    memory = ''
    status_url = f'https://codeforces.com/submissions/{username}'
    interval = 1.5
    max_wait = 30
    waited = 0
    while waited < max_wait:
        s = session.get(status_url)
        s.encoding = 'utf-8'
        st_soup = BeautifulSoup(s.text, 'html.parser')
        table = st_soup.find('table', class_='status-frame-datatable')
        if table:
            first_row = table.find('tr')
            if first_row:
                cols = first_row.find_all('td')
                if len(cols) >= 6:
                    runid = cols[0].get_text(strip=True)
                    verdict = cols[3].get_text(strip=True)
                    use_time = cols[4].get_text(strip=True)
                    memory = cols[5].get_text(strip=True)
                    if verdict not in ['Running', 'In queue', 'Compiling']:
                        break
        time.sleep(interval)
        waited += interval

    return {
        "statusCode": 200,
        "body": json.dumps({
            "problem": problem_id,
            "runid": runid,
            "verdict": verdict,
            "time": use_time,
            "memory": memory
        })
    }
