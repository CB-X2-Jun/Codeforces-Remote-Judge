import requests, json, os
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

def handler(event, context):
    # 区分 GET(轮询) 和 POST(提交)
    if event['httpMethod'] == 'POST':
        try:
            data = json.loads(event['body'])
            jsessionid = data['jsessionid']
            username = data['username']
            problem = data['problem']
            language = data['language']
            source = data['source']
        except Exception as e:
            return {'statusCode':400, 'body':json.dumps({'error':f'参数解析失败: {e}'})}

        session = requests.Session()
        session.cookies.set('JSESSIONID', jsessionid, domain='.codeforces.com')
        headers = {'User-Agent':'Mozilla/5.0'}

        try:
            # 1. 获取提交页面
            s = session.get('https://codeforces.com/problemset/submit', headers=headers)
            s.raise_for_status()
            soup = BeautifulSoup(s.text, 'html.parser')

            # 2. 获取 csrf_token
            token_input = soup.find('input', {'name':'csrf_token'})
            if not token_input:
                return {'statusCode':500, 'body':json.dumps({'error':'无法获取 csrf_token'})}
            csrf_token = token_input['value']

            # 3. POST 提交
            submit_url = 'https://codeforces.com/problemset/submit?csrf_token=' + quote_plus(csrf_token)
            payload = {
                'csrf_token': csrf_token,
                'action':'submitSolutionFormSubmitted',
                'submittedProblemIndex': problem.upper(),
                'programTypeId': language,
                'source': source,
            }
            r = session.post(submit_url, data=payload, headers=headers)
            r.raise_for_status()

            # 4. 获取最新 RunID
            status_url = f'https://codeforces.com/submissions/{username}'
            s2 = session.get(status_url, headers=headers)
            s2.raise_for_status()
            soup2 = BeautifulSoup(s2.text, 'html.parser')
            tr = soup2.find('tr', class_='accepted') or soup2.find('tr')
            runid = tr.find('td').get_text(strip=True) if tr else '未知'
            return {'statusCode':200, 'body':json.dumps({'runid':runid})}

        except Exception as e:
            return {'statusCode':500, 'body':json.dumps({'error':str(e)})}

    else:  # GET 轮询状态
        try:
            qs = event.get('queryStringParameters') or {}
            username = qs.get('username')
            problem = qs.get('problem')
            if not username or not problem:
                return {'statusCode':400,'body':json.dumps({'error':'缺少参数'})}

            session = requests.Session()
            # TODO: 使用共享 JSESSIONID 或让前端每次都 POST 提交再轮询
            # 简化演示，只返回 pending
            return {'statusCode':200,'body':json.dumps({'verdict':'Pending'})}

        except Exception as e:
            return {'statusCode':500, 'body':json.dumps({'error':str(e)})}
